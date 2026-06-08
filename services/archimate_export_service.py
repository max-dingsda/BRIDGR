from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
import uuid
import xml.etree.ElementTree as ET

from core.app_config import AppConfig, resolve_project_path
from core.neo4j_utils import Neo4jClient

_ARCHIMATE_NS = "http://www.opengroup.org/xsd/archimate/3.0/"
_XSI_NS = "http://www.w3.org/2001/XMLSchema-instance"
_XML_LANG_NS = "http://www.w3.org/XML/1998/namespace"

_EXPORT_LABELS = {"Prozess", "Anwendung", "Schnittstelle", "Server", "OrgEinheit", "Rolle"}
_EXPORT_RELATIONS = {
    "DIENT", "BETEILIGT_AN", "KANN_EINNEHMEN", "FOLGT_AUF",
    "USES_INTERFACE", "RUNS_ON", "VERANTWORTET",
}


@dataclass(slots=True)
class ArchiMateExportResult:
    elements_exported: int
    relations_exported: int
    output_path: str


def export_graph_as_archimate(config: AppConfig, mapping: dict) -> ArchiMateExportResult:
    from services.runtime_service import get_session_neo4j_client

    neo4j_client = get_session_neo4j_client(config)
    return _build_archimate_export(neo4j_client, config, mapping)


def _build_archimate_export(
    neo4j_client: Neo4jClient,
    config: AppConfig,
    mapping: dict,
) -> ArchiMateExportResult:
    nodes = _read_nodes(neo4j_client)
    relations = _read_relations(neo4j_client)

    export_elem_map: dict[str, str] = mapping.get("elements", {}).get("export", {})
    export_rel_map: dict[str, str] = mapping.get("relationships", {}).get("export", {})

    ET.register_namespace("", _ARCHIMATE_NS)
    ET.register_namespace("xsi", _XSI_NS)

    model_id = f"id-{uuid.uuid4().hex[:12]}"
    model = ET.Element(
        f"{{{_ARCHIMATE_NS}}}model",
        attrib={
            f"{{{_XSI_NS}}}schemaLocation": (
                "http://www.opengroup.org/xsd/archimate/3.0/ "
                "http://www.opengroup.org/xsd/archimate/3.0/archimate3_Diagram.xsd"
            ),
            "identifier": model_id,
            "version": "3.0",
        },
    )
    model_name = ET.SubElement(model, f"{{{_ARCHIMATE_NS}}}name")
    model_name.set(f"{{{_XML_LANG_NS}}}lang", "de")
    model_name.text = "BRIDGR Export"

    elements_el = ET.SubElement(model, f"{{{_ARCHIMATE_NS}}}elements")
    relationships_el = ET.SubElement(model, f"{{{_ARCHIMATE_NS}}}relationships")

    # name → archimate identifier (for relation source/target references)
    name_label_to_id: dict[tuple[str, str], str] = {}
    elements_exported = 0

    for node in nodes:
        label = node.get("label", "")
        name = node.get("name", "")
        if not label or not name or label not in _EXPORT_LABELS:
            continue

        archimate_type = node.get("archimate_type") or export_elem_map.get(label)
        if not archimate_type:
            continue

        elem_id = node.get("archimate_id") or f"id-{uuid.uuid4().hex[:12]}"
        name_label_to_id[(name, label)] = elem_id

        elem_el = ET.SubElement(
            elements_el,
            f"{{{_ARCHIMATE_NS}}}element",
            attrib={
                f"{{{_XSI_NS}}}type": archimate_type,
                "identifier": elem_id,
            },
        )
        name_el = ET.SubElement(elem_el, f"{{{_ARCHIMATE_NS}}}name")
        name_el.set(f"{{{_XML_LANG_NS}}}lang", "de")
        name_el.text = name
        elements_exported += 1

    relations_exported = 0
    for rel in relations:
        src_label = rel.get("src_label", "")
        src_name = rel.get("src_name", "")
        tgt_label = rel.get("tgt_label", "")
        tgt_name = rel.get("tgt_name", "")
        bridgr_rel_type = rel.get("rel_type", "")

        if bridgr_rel_type not in _EXPORT_RELATIONS:
            continue

        src_id = name_label_to_id.get((src_name, src_label))
        tgt_id = name_label_to_id.get((tgt_name, tgt_label))
        if not src_id or not tgt_id:
            continue

        pair_key = f"{src_label}->{tgt_label}"
        archimate_rel_type = rel.get("archimate_rel_type") or export_rel_map.get(pair_key)
        if not archimate_rel_type:
            continue
        archimate_rel_type = _normalize_rel_type(archimate_rel_type)

        rel_id = f"id-{uuid.uuid4().hex[:12]}"
        ET.SubElement(
            relationships_el,
            f"{{{_ARCHIMATE_NS}}}relationship",
            attrib={
                f"{{{_XSI_NS}}}type": archimate_rel_type,
                "identifier": rel_id,
                "source": src_id,
                "target": tgt_id,
            },
        )
        relations_exported += 1

    output_dir = resolve_project_path(config.output_path)
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    output_path = output_dir / f"archimate_export_{timestamp}.xml"

    ET.indent(model, space="  ")
    tree = ET.ElementTree(model)
    tree.write(output_path, encoding="utf-8", xml_declaration=True)

    return ArchiMateExportResult(
        elements_exported=elements_exported,
        relations_exported=relations_exported,
        output_path=str(output_path),
    )


def _normalize_rel_type(rel_type: str) -> str:
    """Ensure relationship type uses the schema-correct short name (no 'Relationship' suffix).
    Handles values stored before this fix was applied."""
    if rel_type.endswith("Relationship"):
        return rel_type[: -len("Relationship")]
    return rel_type


def _read_nodes(client: Neo4jClient) -> list[dict]:
    return client.execute_read(
        """
        MATCH (n)
        WHERE n.name IS NOT NULL
          AND any(lbl IN labels(n) WHERE lbl IN
            ['Prozess','Anwendung','Schnittstelle','Server','OrgEinheit','Rolle'])
        RETURN labels(n)[0] AS label,
               n.name AS name,
               n.archimate_id AS archimate_id,
               n.archimate_type AS archimate_type
        """,
        {},
    )


def _read_relations(client: Neo4jClient) -> list[dict]:
    return client.execute_read(
        """
        MATCH (s)-[r]->(t)
        WHERE s.name IS NOT NULL AND t.name IS NOT NULL
          AND type(r) IN
            ['DIENT','BETEILIGT_AN','KANN_EINNEHMEN','FOLGT_AUF',
             'USES_INTERFACE','RUNS_ON','VERANTWORTET']
        RETURN labels(s)[0] AS src_label,
               s.name AS src_name,
               labels(t)[0] AS tgt_label,
               t.name AS tgt_name,
               type(r) AS rel_type,
               r.archimate_rel_type AS archimate_rel_type
        """,
        {},
    )

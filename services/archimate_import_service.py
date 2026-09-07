from __future__ import annotations

import json
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from pathlib import Path
import xml.etree.ElementTree as ET

from core.app_config import AppConfig, resolve_project_path
from core.neo4j_utils import Neo4jClient
from skills.graph_writer import GraphWriter

_ARCHIMATE_NS_30 = "http://www.opengroup.org/xsd/archimate/3.0/"
_ARCHIMATE_NS_31 = "http://www.opengroup.org/xsd/archimate/3.1/"
_XSI_NS = "http://www.w3.org/2001/XMLSchema-instance"

ARCHIMATE_ELEMENT_TYPES: list[str] = sorted([
    # Business layer
    "BusinessActor", "BusinessCollaboration", "BusinessEvent", "BusinessFunction",
    "BusinessInterface", "BusinessInteraction", "BusinessObject", "BusinessProcess",
    "BusinessRole", "BusinessService", "Contract", "Product", "Representation",
    # Application layer
    "ApplicationCollaboration", "ApplicationComponent", "ApplicationEvent",
    "ApplicationFunction", "ApplicationInterface", "ApplicationInteraction",
    "ApplicationProcess", "ApplicationService", "DataObject",
    # Technology layer
    "Artifact", "CommunicationNetwork", "Device", "Node", "Path", "SystemSoftware",
    "TechnologyCollaboration", "TechnologyEvent", "TechnologyFunction",
    "TechnologyInterface", "TechnologyInteraction", "TechnologyProcess",
    "TechnologyService",
    # Strategy layer
    "Capability", "CourseOfAction", "Resource", "ValueStream",
    # Motivation layer
    "Assessment", "Constraint", "Driver", "Goal", "Meaning", "Outcome",
    "Principle", "Requirement", "Risk", "Stakeholder", "Value",
    # Other
    "Grouping", "Location",
])

ARCHIMATE_RELATION_TYPES: list[str] = [
    "Association", "Assignment", "Aggregation", "Composition",
    "Realization", "Serving", "Access", "Influence",
    "Triggering", "Flow", "Specialization",
]

_BRIDGR_LABELS = {
    "Process", "Application", "Interface", "Server", "OrgUnit", "Role",
    "Capability", "Resource", "Goal", "Requirement", "Context", "Stakeholder",
    "Risk", "DataObject", "Infrastructure",
}

_DEFAULT_MAPPING_PATH = "data/archimate_mapping.json"


@dataclass(slots=True)
class ArchiMateElement:
    archimate_id: str
    archimate_type: str
    name: str
    bridgr_label: str


@dataclass(slots=True)
class ArchiMateRelation:
    archimate_id: str
    archimate_rel_type: str
    source_archimate_id: str
    target_archimate_id: str


@dataclass(slots=True)
class ArchiMateImportResult:
    elements_imported: int = 0
    elements_as_candidates: int = 0
    elements_skipped: int = 0
    relations_imported: int = 0
    relations_skipped: int = 0
    skipped_types: dict[str, int] = field(default_factory=dict)
    skipped_relations: list[dict] = field(default_factory=list)


def load_archimate_mapping(path: Path | None = None) -> dict:
    mapping_path = path or resolve_project_path(_DEFAULT_MAPPING_PATH)
    if not mapping_path.exists():
        return _default_mapping()
    with mapping_path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def confirm_archimate_candidate_node(
    neo4j_client: Neo4jClient,
    label: str,
    candidate_name: str,
    target_name: str,
    archimate_id: str,
) -> None:
    with neo4j_client.transaction():
        from core.graph_schema import QUERY_NODE_SCHEMA, QUERY_RELATIONSHIP_PATTERNS
        if label not in QUERY_NODE_SCHEMA:
            raise ValueError(f"Unbekanntes Label: {label}")
        outgoing = {p.relationship_type for p in QUERY_RELATIONSHIP_PATTERNS if p.source_label == label}
        incoming = {p.relationship_type for p in QUERY_RELATIONSHIP_PATTERNS if p.target_label == label}
        for rel_type in outgoing:
            neo4j_client.execute_write(
                f"""
                MATCH (kandidat:{label} {{name: $candidate_name}})-[:{rel_type}]->(other)
                MATCH (ziel:{label} {{name: $target_name}})
                MERGE (ziel)-[:{rel_type}]->(other)
                """,
                {"candidate_name": candidate_name, "target_name": target_name},
            )
        for rel_type in incoming:
            neo4j_client.execute_write(
                f"""
                MATCH (other)-[:{rel_type}]->(kandidat:{label} {{name: $candidate_name}})
                MATCH (ziel:{label} {{name: $target_name}})
                MERGE (other)-[:{rel_type}]->(ziel)
                """,
                {"candidate_name": candidate_name, "target_name": target_name},
            )
        neo4j_client.execute_write(
            f"MATCH (n:{label} {{name: $target_name}}) SET n.archimate_id = $archimate_id",
            {"target_name": target_name, "archimate_id": archimate_id},
        )
        neo4j_client.execute_write(
            f"MATCH (n:{label} {{name: $candidate_name}}) DETACH DELETE n",
            {"candidate_name": candidate_name},
        )


def save_archimate_mapping(mapping: dict, path: Path | None = None) -> None:
    mapping_path = path or resolve_project_path(_DEFAULT_MAPPING_PATH)
    with mapping_path.open("w", encoding="utf-8") as fh:
        json.dump(mapping, fh, indent=2, ensure_ascii=False)
        fh.write("\n")


def persist_archimate_import(config: AppConfig, source_path: Path) -> ArchiMateImportResult:
    from services.runtime_service import get_session_neo4j_client, write_debug_log

    mapping = load_archimate_mapping()
    elements, relations, parse_skipped_types = _parse_archimate_xml(source_path, mapping)
    neo4j_client = get_session_neo4j_client(config)
    result = _import_to_neo4j(neo4j_client, elements, relations, mapping, source_path.name)
    for archimate_type, count in parse_skipped_types.items():
        result.skipped_types[archimate_type] = result.skipped_types.get(archimate_type, 0) + count
    write_debug_log(
        config,
        "archimate_import",
        {
            "source": source_path.name,
            "elements_imported": result.elements_imported,
            "elements_as_candidates": result.elements_as_candidates,
            "elements_skipped": result.elements_skipped,
            "relations_imported": result.relations_imported,
            "relations_skipped": result.relations_skipped,
            "skipped_types": result.skipped_types,
        },
    )
    return result


def _detect_namespace(root: ET.Element) -> str:
    tag = root.tag
    if tag.startswith(f"{{{_ARCHIMATE_NS_31}}}"):
        return _ARCHIMATE_NS_31
    return _ARCHIMATE_NS_30


def _parse_archimate_xml(
    source_path: Path,
    mapping: dict,
) -> tuple[list[ArchiMateElement], list[ArchiMateRelation], dict[str, int]]:
    try:
        tree = ET.parse(source_path)
    except ET.ParseError as exc:
        raise ValueError(f"Invalid ArchiMate XML: {exc}") from exc

    root = tree.getroot()
    ns = _detect_namespace(root)
    import_map: dict[str, str] = mapping.get("elements", {}).get("import", {})
    ignore_set: set[str] = set(mapping.get("elements", {}).get("ignore", []))
    language_preference: list[str] = mapping.get("language_preference", ["de", "german", "en", "english"])

    elements: list[ArchiMateElement] = []
    skipped_types: dict[str, int] = {}
    for elem in root.iter(f"{{{ns}}}element"):
        archimate_id = elem.get("identifier", "")
        raw_type = elem.get(f"{{{_XSI_NS}}}type", "")
        archimate_type = raw_type.split(":")[-1] if ":" in raw_type else raw_type

        names = [
            (name_el.get("{http://www.w3.org/XML/1998/namespace}lang", ""), name_el.text or "")
            for name_el in elem.findall(f"{{{ns}}}name")
        ]
        name = _select_name(names, language_preference)
        if not name or not archimate_id:
            continue

        bridgr_label = import_map.get(archimate_type)
        if bridgr_label is None:
            if archimate_type not in ignore_set:
                skipped_types[archimate_type] = skipped_types.get(archimate_type, 0) + 1
            continue

        elements.append(ArchiMateElement(
            archimate_id=archimate_id,
            archimate_type=archimate_type,
            name=name,
            bridgr_label=bridgr_label,
        ))

    relations: list[ArchiMateRelation] = []
    for rel in root.iter(f"{{{ns}}}relationship"):
        archimate_id = rel.get("identifier", "")
        raw_type = rel.get(f"{{{_XSI_NS}}}type", "")
        rel_type = raw_type.split(":")[-1] if ":" in raw_type else raw_type
        source_id = rel.get("source", "")
        target_id = rel.get("target", "")
        if not all([archimate_id, rel_type, source_id, target_id]):
            continue
        relations.append(ArchiMateRelation(
            archimate_id=archimate_id,
            archimate_rel_type=rel_type,
            source_archimate_id=source_id,
            target_archimate_id=target_id,
        ))

    return elements, relations, skipped_types


def _select_name(names: list[tuple[str, str]], language_preference: list[str]) -> str:
    lang_aliases = {"german": "de", "english": "en", "french": "fr", "spanish": "es"}
    normalized_pref = [lang_aliases.get(p.lower(), p.lower()) for p in language_preference]

    for pref in normalized_pref:
        for lang, text in names:
            normalized_lang = lang_aliases.get(lang.lower(), lang.lower())
            if normalized_lang == pref and text.strip():
                return text.strip()

    for _, text in names:
        if text.strip():
            return text.strip()
    return ""


def _import_to_neo4j(
    client: Neo4jClient,
    elements: list[ArchiMateElement],
    relations: list[ArchiMateRelation],
    mapping: dict,
    source_filename: str,
) -> ArchiMateImportResult:
    with client.transaction():
        result = ArchiMateImportResult()
        writer = GraphWriter()
        threshold: float = mapping.get("fuzzy_match_threshold", 0.85)
        rel_import_map: dict[str, list[str]] = mapping.get("relationships", {}).get("import", {})
        bridgr_map: dict[str, str] = mapping.get("relationships", {}).get("bridgr_relation", {})

        # Snapshot of existing names per label taken BEFORE this import run.
        # Fuzzy matching uses only this snapshot so that nodes created during
        # the current import cannot match each other.
        all_labels = {elem.bridgr_label for elem in elements}
        pre_existing_names: dict[str, list[str]] = {
            label: [
                r["name"]
                for r in client.execute_read_unvalidated(
                    f"MATCH (n:{label}) WHERE n.name IS NOT NULL RETURN n.name AS name", {}
                )
            ]
            for label in all_labels
        }

        # archimate_id → resolved name (for nodes successfully imported/merged)
        id_to_name: dict[str, str] = {}
        # archimate_id → bridgr_label
        id_to_label: dict[str, str] = {}
        # archimate_id → original archimate name (all elements, incl. candidates)
        id_to_archimate_name: dict[str, str] = {e.archimate_id: e.name for e in elements}

        skipped_types: dict[str, int] = {}

        for elem in elements:
            resolved_name = _resolve_identity(
                client, elem, threshold, mapping,
                pre_existing_names.get(elem.bridgr_label, []),
            )
            is_candidate = resolved_name is None
            if is_candidate:
                resolved_name = elem.name
                result.elements_as_candidates += 1
            else:
                result.elements_imported += 1

            writer.merge_archimate_node(
                client,
                label=elem.bridgr_label,
                name=resolved_name,
                archimate_id=elem.archimate_id,
                archimate_source=source_filename,
                archimate_type=elem.archimate_type,
            )
            id_to_name[elem.archimate_id] = resolved_name
            id_to_label[elem.archimate_id] = elem.bridgr_label

        for rel in relations:
            source_name = id_to_name.get(rel.source_archimate_id)
            target_name = id_to_name.get(rel.target_archimate_id)
            source_label = id_to_label.get(rel.source_archimate_id)
            target_label = id_to_label.get(rel.target_archimate_id)

            if not source_name or not target_name or not source_label or not target_label:
                result.relations_skipped += 1
                src_display = source_name or f"~{id_to_archimate_name.get(rel.source_archimate_id, '?')} (Kandidat)"
                tgt_display = target_name or f"~{id_to_archimate_name.get(rel.target_archimate_id, '?')} (Kandidat)"
                result.skipped_relations.append({
                    "source": src_display,
                    "target": tgt_display,
                    "rel_type": rel.archimate_rel_type,
                    "reason": "unresolvable_endpoint",
                })
                continue

            pair_key = f"{source_label}->{target_label}"
            accepted_types = rel_import_map.get(pair_key, [])
            if rel.archimate_rel_type not in accepted_types:
                result.relations_skipped += 1
                skipped_types[rel.archimate_rel_type] = skipped_types.get(rel.archimate_rel_type, 0) + 1
                result.skipped_relations.append({
                    "source": source_name,
                    "target": target_name,
                    "rel_type": rel.archimate_rel_type,
                    "reason": "type_not_accepted",
                })
                continue

            bridgr_relation = _label_pair_to_relation(source_label, target_label, bridgr_map)
            if bridgr_relation is None:
                result.relations_skipped += 1
                result.skipped_relations.append({
                    "source": source_name,
                    "target": target_name,
                    "rel_type": rel.archimate_rel_type,
                    "reason": "no_bridgr_relation",
                })
                continue

            writer.merge_archimate_relation(
                client,
                source_name=source_name,
                source_label=source_label,
                target_name=target_name,
                target_label=target_label,
                bridgr_relation=bridgr_relation,
                archimate_rel_type=rel.archimate_rel_type,
            )
            result.relations_imported += 1

        result.skipped_types = skipped_types
        return result


def _resolve_identity(
    client: Neo4jClient,
    element: ArchiMateElement,
    threshold: float,
    mapping: dict,
    pre_existing_names: list[str],
) -> str | None:
    # 1. archimate_id lookup (Re-Import)
    rows = client.execute_read_unvalidated(
        f"MATCH (n:{element.bridgr_label} {{archimate_id: $archimate_id}}) RETURN n.name AS name",
        {"archimate_id": element.archimate_id},
    )
    if rows:
        return rows[0]["name"]

    # 2. Exact name match against pre-existing nodes
    rows = client.execute_read_unvalidated(
        f"MATCH (n:{element.bridgr_label} {{name: $name}}) RETURN n.name AS name",
        {"name": element.name},
    )
    if rows:
        return rows[0]["name"]

    # 3. Fuzzy match — only against names that existed BEFORE this import run.
    # This prevents nodes created during the current import from matching each other.
    matched, score = _fuzzy_match_name(element.name, pre_existing_names, threshold)
    if matched is not None:
        _add_pending_candidate(element, matched, score)
        return None

    # 4. New node
    return element.name


def _fuzzy_match_name(name: str, candidates: list[str], threshold: float) -> tuple[str | None, float]:
    best_name: str | None = None
    best_score = 0.0
    for candidate in candidates:
        score = SequenceMatcher(None, name.lower(), candidate.lower()).ratio()
        if score > best_score:
            best_score = score
            best_name = candidate
    if best_score >= threshold:
        return best_name, best_score
    return None, best_score


def _add_pending_candidate(element: ArchiMateElement, matched_name: str, score: float) -> None:
    mapping_path = resolve_project_path(_DEFAULT_MAPPING_PATH)
    if not mapping_path.exists():
        return
    with mapping_path.open("r", encoding="utf-8") as fh:
        mapping = json.load(fh)
    candidates: list[dict] = mapping.setdefault("pending_candidates", [])
    already_exists = any(
        c.get("archimate_id") == element.archimate_id for c in candidates
    )
    if not already_exists:
        candidates.append({
            "archimate_id": element.archimate_id,
            "archimate_type": element.archimate_type,
            "archimate_name": element.name,
            "bridgr_label": element.bridgr_label,
            "suggested_match": matched_name,
            "score": round(score, 3),
        })
        mapping["pending_candidates"] = candidates
        save_archimate_mapping(mapping)


def _label_pair_to_relation(source_label: str, target_label: str, bridgr_map: dict) -> str | None:
    return bridgr_map.get(f"{source_label}->{target_label}")


def _default_mapping() -> dict:
    return {
        "language_preference": ["de", "german", "en", "english"],
        "fuzzy_match_threshold": 0.85,
        "elements": {
            "import": {
                "BusinessProcess":      "Process",
                "ApplicationComponent": "Application",
                "ApplicationInterface": "Interface",
                "Node":                 "Server",
                "BusinessActor":        "OrgUnit",
                "BusinessRole":         "Role",
            },
            "export": {
                "Process":       "BusinessProcess",
                "Application":     "ApplicationComponent",
                "Interface": "ApplicationInterface",
                "Server":        "Node",
                "OrgUnit":    "BusinessActor",
                "Role":         "BusinessRole",
            },
        },
        "relationships": {
            "import": {
                "Application->Process":        ["Serving", "Realization"],
                "Role->Process":            ["Assignment"],
                "OrgUnit->Role":         ["Assignment"],
                "Process->Process":          ["Triggering", "Flow"],
                "Application->Interface":  ["Composition", "Aggregation"],
                "Application->Server":         ["Realization", "Assignment"],
                "Interface->Server":     ["Realization"],
                "OrgUnit->Application":     ["Association", "Assignment"],
                "OrgUnit->Interface": ["Association", "Assignment"],
                "OrgUnit->Server":        ["Association", "Assignment"],
                "OrgUnit->Process":       ["Assignment"],
            },
            "export": {
                "Application->Process":        "Serving",
                "Role->Process":            "Assignment",
                "OrgUnit->Role":         "Assignment",
                "Process->Process":          "Triggering",
                "Application->Interface":  "Composition",
                "Application->Server":         "Realization",
                "Interface->Server":     "Realization",
                "OrgUnit->Application":     "Assignment",
                "OrgUnit->Interface": "Assignment",
                "OrgUnit->Server":        "Assignment",
                "OrgUnit->Process":       "Assignment",
            },
            "bridgr_relation": {
                "Application->Process":        "SERVES",
                "Role->Process":            "PARTICIPATES_IN",
                "OrgUnit->Role":         "CAN_ASSUME",
                "Process->Process":          "FOLLOWS",
                "Application->Interface":  "USES_INTERFACE",
                "Application->Server":         "RUNS_ON",
                "Interface->Server":     "RUNS_ON",
                "OrgUnit->Application":     "RESPONSIBLE_FOR",
                "OrgUnit->Interface": "RESPONSIBLE_FOR",
                "OrgUnit->Server":        "RESPONSIBLE_FOR",
                "OrgUnit->Process":       "RESPONSIBLE_FOR",
            },
        },
        "pending_candidates": [],
    }

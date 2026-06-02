from __future__ import annotations

import json
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from pathlib import Path
import xml.etree.ElementTree as ET

from app_config import AppConfig, resolve_project_path
from neo4j_utils import Neo4jClient
from skills.graph_writer import GraphWriter

_ARCHIMATE_NS = "http://www.opengroup.org/xsd/archimate/3.0/"
_XSI_NS = "http://www.w3.org/2001/XMLSchema-instance"

ARCHIMATE_ELEMENT_TYPES: list[str] = [
    "BusinessActor", "BusinessRole", "BusinessCollaboration", "BusinessInterface",
    "BusinessProcess", "BusinessFunction", "BusinessInteraction", "BusinessEvent",
    "BusinessService", "BusinessObject", "Contract", "Product", "Representation",
    "ApplicationComponent", "ApplicationCollaboration", "ApplicationInterface",
    "ApplicationFunction", "ApplicationInteraction", "ApplicationProcess",
    "ApplicationEvent", "ApplicationService", "DataObject",
    "Node", "Device", "SystemSoftware", "TechnologyCollaboration",
    "TechnologyInterface", "Path", "CommunicationNetwork",
    "TechnologyFunction", "TechnologyProcess", "TechnologyInteraction",
    "TechnologyEvent", "TechnologyService", "Artifact",
    "Capability", "CourseOfAction", "ValueStream", "Resource",
    "Grouping", "Location",
]

ARCHIMATE_RELATION_TYPES: list[str] = [
    "AssociationRelationship", "AssignmentRelationship", "AggregationRelationship",
    "CompositionRelationship", "RealizationRelationship", "ServingRelationship",
    "AccessRelationship", "InfluenceRelationship", "TriggeringRelationship",
    "FlowRelationship", "SpecializationRelationship",
]

_BRIDGR_LABELS = {"Prozess", "Anwendung", "Schnittstelle", "Server", "OrgEinheit", "Rolle"}

_DEFAULT_MAPPING_PATH = "archimate_mapping.json"


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


def load_archimate_mapping(path: Path | None = None) -> dict:
    mapping_path = path or resolve_project_path(_DEFAULT_MAPPING_PATH)
    if not mapping_path.exists():
        return _default_mapping()
    with mapping_path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def save_archimate_mapping(mapping: dict, path: Path | None = None) -> None:
    mapping_path = path or resolve_project_path(_DEFAULT_MAPPING_PATH)
    with mapping_path.open("w", encoding="utf-8") as fh:
        json.dump(mapping, fh, indent=2, ensure_ascii=False)
        fh.write("\n")


def persist_archimate_import(config: AppConfig, source_path: Path) -> ArchiMateImportResult:
    from services.runtime_service import get_session_neo4j_client, write_debug_log

    mapping = load_archimate_mapping()
    elements, relations = _parse_archimate_xml(source_path, mapping)
    neo4j_client = get_session_neo4j_client(config)
    result = _import_to_neo4j(neo4j_client, elements, relations, mapping, source_path.name)
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


def _parse_archimate_xml(
    source_path: Path,
    mapping: dict,
) -> tuple[list[ArchiMateElement], list[ArchiMateRelation]]:
    try:
        tree = ET.parse(source_path)
    except ET.ParseError as exc:
        raise ValueError(f"Invalid ArchiMate XML: {exc}") from exc

    root = tree.getroot()
    import_map: dict[str, str] = mapping.get("elements", {}).get("import", {})
    language_preference: list[str] = mapping.get("language_preference", ["de", "german", "en", "english"])

    elements: list[ArchiMateElement] = []
    for elem in root.iter(f"{{{_ARCHIMATE_NS}}}element"):
        archimate_id = elem.get("identifier", "")
        raw_type = elem.get(f"{{{_XSI_NS}}}type", "")
        archimate_type = raw_type.split(":")[-1] if ":" in raw_type else raw_type

        names = [
            (name_el.get("{http://www.w3.org/XML/1998/namespace}lang", ""), name_el.text or "")
            for name_el in elem.findall(f"{{{_ARCHIMATE_NS}}}name")
        ]
        name = _select_name(names, language_preference)
        if not name or not archimate_id:
            continue

        bridgr_label = import_map.get(archimate_type)
        if bridgr_label is None:
            continue

        elements.append(ArchiMateElement(
            archimate_id=archimate_id,
            archimate_type=archimate_type,
            name=name,
            bridgr_label=bridgr_label,
        ))

    relations: list[ArchiMateRelation] = []
    for rel in root.iter(f"{{{_ARCHIMATE_NS}}}relationship"):
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

    return elements, relations


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
    result = ArchiMateImportResult()
    writer = GraphWriter()
    threshold: float = mapping.get("fuzzy_match_threshold", 0.85)
    rel_import_map: dict[str, list[str]] = mapping.get("relationships", {}).get("import", {})

    # archimate_id → resolved name (for nodes successfully imported/merged)
    id_to_name: dict[str, str] = {}
    # archimate_id → bridgr_label
    id_to_label: dict[str, str] = {}

    skipped_types: dict[str, int] = {}

    for elem in elements:
        resolved_name = _resolve_identity(client, elem, threshold, mapping)
        if resolved_name is None:
            result.elements_as_candidates += 1
            continue

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
        result.elements_imported += 1

    for rel in relations:
        source_name = id_to_name.get(rel.source_archimate_id)
        target_name = id_to_name.get(rel.target_archimate_id)
        source_label = id_to_label.get(rel.source_archimate_id)
        target_label = id_to_label.get(rel.target_archimate_id)

        if not source_name or not target_name or not source_label or not target_label:
            result.relations_skipped += 1
            continue

        pair_key = f"{source_label}->{target_label}"
        accepted_types = rel_import_map.get(pair_key, [])
        if rel.archimate_rel_type not in accepted_types:
            result.relations_skipped += 1
            skipped_types[rel.archimate_rel_type] = skipped_types.get(rel.archimate_rel_type, 0) + 1
            continue

        bridgr_relation = _label_pair_to_relation(source_label, target_label)
        if bridgr_relation is None:
            result.relations_skipped += 1
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
) -> str | None:
    # 1. archimate_id lookup (Re-Import)
    rows = client.execute_read(
        f"MATCH (n:{element.bridgr_label} {{archimate_id: $archimate_id}}) RETURN n.name AS name",
        {"archimate_id": element.archimate_id},
    )
    if rows:
        return rows[0]["name"]

    # 2. Exact name match
    rows = client.execute_read(
        f"MATCH (n:{element.bridgr_label} {{name: $name}}) RETURN n.name AS name",
        {"name": element.name},
    )
    if rows:
        return rows[0]["name"]

    # 3. Fuzzy match against all names of this label
    rows = client.execute_read(
        f"MATCH (n:{element.bridgr_label}) WHERE n.name IS NOT NULL RETURN n.name AS name",
        {},
    )
    candidates = [r["name"] for r in rows]
    matched, score = _fuzzy_match_name(element.name, candidates, threshold)
    if matched is not None:
        _add_pending_candidate(element, matched, score)
        return None

    # 4. New node — return the element name to create it
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


def _label_pair_to_relation(source_label: str, target_label: str) -> str | None:
    _RELATION_MAP: dict[tuple[str, str], str] = {
        ("Anwendung", "Prozess"):       "DIENT",
        ("Rolle", "Prozess"):           "BETEILIGT_AN",
        ("OrgEinheit", "Rolle"):        "KANN_EINNEHMEN",
        ("Prozess", "Prozess"):         "FOLGT_AUF",
        ("Anwendung", "Schnittstelle"): "USES_INTERFACE",
        ("Anwendung", "Server"):        "RUNS_ON",
        ("Schnittstelle", "Server"):    "RUNS_ON",
        ("OrgEinheit", "Anwendung"):    "VERANTWORTET",
        ("OrgEinheit", "Schnittstelle"):"VERANTWORTET",
        ("OrgEinheit", "Server"):       "VERANTWORTET",
    }
    return _RELATION_MAP.get((source_label, target_label))


def _default_mapping() -> dict:
    return {
        "language_preference": ["de", "german", "en", "english"],
        "fuzzy_match_threshold": 0.85,
        "elements": {
            "import": {
                "BusinessProcess":      "Prozess",
                "ApplicationComponent": "Anwendung",
                "ApplicationInterface": "Schnittstelle",
                "Node":                 "Server",
                "BusinessActor":        "OrgEinheit",
                "BusinessRole":         "Rolle",
            },
            "export": {
                "Prozess":       "BusinessProcess",
                "Anwendung":     "ApplicationComponent",
                "Schnittstelle": "ApplicationInterface",
                "Server":        "Node",
                "OrgEinheit":    "BusinessActor",
                "Rolle":         "BusinessRole",
            },
        },
        "relationships": {
            "import": {
                "Anwendung->Prozess":        ["ServingRelationship", "RealizationRelationship"],
                "Rolle->Prozess":            ["AssignmentRelationship"],
                "OrgEinheit->Rolle":         ["AssignmentRelationship"],
                "Prozess->Prozess":          ["TriggeringRelationship", "FlowRelationship"],
                "Anwendung->Schnittstelle":  ["CompositionRelationship", "AggregationRelationship"],
                "Anwendung->Server":         ["RealizationRelationship", "AssignmentRelationship"],
                "Schnittstelle->Server":     ["RealizationRelationship"],
                "OrgEinheit->Anwendung":     ["AssociationRelationship", "AssignmentRelationship"],
                "OrgEinheit->Schnittstelle": ["AssociationRelationship"],
                "OrgEinheit->Server":        ["AssociationRelationship"],
            },
            "export": {
                "Anwendung->Prozess":        "ServingRelationship",
                "Rolle->Prozess":            "AssignmentRelationship",
                "OrgEinheit->Rolle":         "AssignmentRelationship",
                "Prozess->Prozess":          "TriggeringRelationship",
                "Anwendung->Schnittstelle":  "CompositionRelationship",
                "Anwendung->Server":         "RealizationRelationship",
                "Schnittstelle->Server":     "RealizationRelationship",
                "OrgEinheit->Anwendung":     "AssociationRelationship",
                "OrgEinheit->Schnittstelle": "AssociationRelationship",
                "OrgEinheit->Server":        "AssociationRelationship",
            },
        },
        "pending_candidates": [],
    }

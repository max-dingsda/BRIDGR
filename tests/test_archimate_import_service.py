from __future__ import annotations

import json
from pathlib import Path

import pytest

from services.archimate_import_service import (
    _parse_archimate_xml,
    _select_name,
    _fuzzy_match_name,
    _import_to_neo4j,
    _label_pair_to_relation,
    confirm_archimate_candidate_node,
    load_archimate_mapping,
)


_MINIMAL_XML = """\
<?xml version="1.0" encoding="UTF-8"?>
<model xmlns="http://www.opengroup.org/xsd/archimate/3.0/"
       xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
       identifier="id-model-1" version="3.0">
  <name xml:lang="de">Test</name>
  <elements>
    <element identifier="id-1" xsi:type="BusinessProcess">
      <name xml:lang="de">Posteingang</name>
    </element>
    <element identifier="id-2" xsi:type="ApplicationComponent">
      <name xml:lang="de">SAP SD</name>
    </element>
  </elements>
  <relationships>
    <relationship identifier="id-3" xsi:type="Serving"
                  source="id-2" target="id-1"/>
  </relationships>
</model>
"""

_MULTILANG_XML = """\
<?xml version="1.0" encoding="UTF-8"?>
<model xmlns="http://www.opengroup.org/xsd/archimate/3.0/"
       xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
       identifier="id-model-2" version="3.0">
  <elements>
    <element identifier="id-10" xsi:type="BusinessProcess">
      <name xml:lang="en">Incoming Mail</name>
      <name xml:lang="de">Posteingang</name>
    </element>
    <element identifier="id-11" xsi:type="BusinessProcess">
      <name xml:lang="german">Bestellabwicklung</name>
    </element>
  </elements>
  <relationships/>
</model>
"""

_UNKNOWN_TYPE_XML = """\
<?xml version="1.0" encoding="UTF-8"?>
<model xmlns="http://www.opengroup.org/xsd/archimate/3.0/"
       xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
       identifier="id-model-3" version="3.0">
  <elements>
    <element identifier="id-20" xsi:type="Capability">
      <name xml:lang="de">Lieferfähigkeit</name>
    </element>
    <element identifier="id-21" xsi:type="BusinessProcess">
      <name xml:lang="de">Process A</name>
    </element>
  </elements>
  <relationships/>
</model>
"""

_DEFAULT_MAPPING = {
    "language_preference": ["de", "german", "en", "english"],
    "fuzzy_match_threshold": 0.85,
    "elements": {
        "import": {
            "BusinessProcess": "Process",
            "ApplicationComponent": "Application",
            "BusinessActor": "OrgUnit",
        },
        "export": {},
    },
    "relationships": {
        "import": {
            "Application->Process": ["Serving"],
            "Process->Process": ["Triggering", "Flow"],
            "OrgUnit->Process": ["Assignment"],
        },
        "export": {},
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


class RecordingNeo4jClient:
    def execute_read(self, query, parameters=None):
        return self.execute_read_unvalidated(query, parameters)

    def __init__(self, read_results: dict[str, list[dict]] | None = None) -> None:
        self.queries: list[tuple[str, dict | None]] = []
        self._read_results = read_results or {}

    def ensure_constraints(self) -> None:
        pass

    def execute_write(self, query: str, parameters=None):
        self.queries.append((query, parameters))
        return []

    def execute_read_unvalidated(self, query: str, parameters=None):
        for key, result in self._read_results.items():
            if key in query:
                return result
        return []

    def transaction(self):
        from contextlib import nullcontext
        return nullcontext(self)

    serialized_writes = transaction

    def stage_artifact(self, path, payload):
        from processing.run_artifacts import atomic_write_json
        atomic_write_json(path, payload)

    def read_staged_artifact(self, path):
        return None


# --- _select_name ---

def test_select_name_prefers_german() -> None:
    names = [("en", "Incoming Mail"), ("de", "Posteingang")]
    assert _select_name(names, ["de", "en"]) == "Posteingang"


def test_select_name_german_full_word_equivalent() -> None:
    names = [("german", "Bestellabwicklung"), ("en", "Order Processing")]
    assert _select_name(names, ["de", "german", "en"]) == "Bestellabwicklung"


def test_select_name_fallback_to_first_available() -> None:
    names = [("fr", "Courrier entrant")]
    assert _select_name(names, ["de", "en"]) == "Courrier entrant"


def test_select_name_empty_returns_empty() -> None:
    assert _select_name([], ["de"]) == ""


# --- _parse_archimate_xml ---

def test_parse_minimal_xml(tmp_path: Path) -> None:
    xml_file = tmp_path / "model.xml"
    xml_file.write_text(_MINIMAL_XML, encoding="utf-8")
    elements, relations, skipped = _parse_archimate_xml(xml_file, _DEFAULT_MAPPING)
    assert len(elements) == 2
    assert elements[0].archimate_id == "id-1"
    assert elements[0].archimate_type == "BusinessProcess"
    assert elements[0].name == "Posteingang"
    assert elements[0].bridgr_label == "Process"
    assert len(relations) == 1
    assert relations[0].archimate_rel_type == "Serving"
    assert relations[0].source_archimate_id == "id-2"
    assert relations[0].target_archimate_id == "id-1"


def test_parse_multilang_prefers_german(tmp_path: Path) -> None:
    xml_file = tmp_path / "multi.xml"
    xml_file.write_text(_MULTILANG_XML, encoding="utf-8")
    elements, _, _skipped = _parse_archimate_xml(xml_file, _DEFAULT_MAPPING)
    assert elements[0].name == "Posteingang"
    assert elements[1].name == "Bestellabwicklung"


def test_parse_unknown_type_skipped(tmp_path: Path) -> None:
    xml_file = tmp_path / "unknown.xml"
    xml_file.write_text(_UNKNOWN_TYPE_XML, encoding="utf-8")
    elements, _, skipped = _parse_archimate_xml(xml_file, _DEFAULT_MAPPING)
    # Capability not in import mapping → skipped with warning; BusinessProcess included
    assert len(elements) == 1
    assert elements[0].name == "Process A"
    assert "Capability" in skipped


def test_parse_invalid_xml_raises(tmp_path: Path) -> None:
    xml_file = tmp_path / "bad.xml"
    xml_file.write_text("not xml at all", encoding="utf-8")
    with pytest.raises(ValueError, match="Invalid ArchiMate XML"):
        _parse_archimate_xml(xml_file, _DEFAULT_MAPPING)


# --- _fuzzy_match_name ---

def test_fuzzy_match_finds_close_name() -> None:
    matched, score = _fuzzy_match_name("Posteingnag", ["Posteingang", "Bestellabwicklung"], 0.8)
    assert matched == "Posteingang"
    assert score >= 0.8


def test_fuzzy_match_below_threshold_returns_none() -> None:
    matched, _ = _fuzzy_match_name("xyz", ["Posteingang"], 0.8)
    assert matched is None


def test_fuzzy_match_exact_returns_full_score() -> None:
    matched, score = _fuzzy_match_name("Posteingang", ["Posteingang"], 0.85)
    assert matched == "Posteingang"
    assert score == 1.0


# --- _label_pair_to_relation ---

_BRIDGR_MAP = _DEFAULT_MAPPING["relationships"]["bridgr_relation"]


def test_label_pair_to_relation_known() -> None:
    assert _label_pair_to_relation("Application", "Process", _BRIDGR_MAP) == "SERVES"
    assert _label_pair_to_relation("Process", "Process", _BRIDGR_MAP) == "FOLLOWS"
    assert _label_pair_to_relation("OrgUnit", "Application", _BRIDGR_MAP) == "RESPONSIBLE_FOR"


def test_label_pair_org_prozess_returns_verantwortet() -> None:
    assert _label_pair_to_relation("OrgUnit", "Process", _BRIDGR_MAP) == "RESPONSIBLE_FOR"


def test_label_pair_to_relation_unknown_returns_none() -> None:
    assert _label_pair_to_relation("Process", "Application", _BRIDGR_MAP) is None


def test_label_pair_to_relation_empty_map_returns_none() -> None:
    assert _label_pair_to_relation("Application", "Process", {}) is None


def test_label_pair_to_relation_reads_custom_map() -> None:
    custom = {"Application->Process": "CUSTOM_REL"}
    assert _label_pair_to_relation("Application", "Process", custom) == "CUSTOM_REL"


# --- _import_to_neo4j ---

def test_import_exact_name_match_merges_existing(tmp_path: Path) -> None:
    from services.archimate_import_service import ArchiMateElement, ArchiMateRelation

    element = ArchiMateElement(
        archimate_id="id-1",
        archimate_type="BusinessProcess",
        name="Posteingang",
        bridgr_label="Process",
    )
    client = RecordingNeo4jClient(
        read_results={"archimate_id": [], "n.name": [{"name": "Posteingang"}]}
    )
    result = _import_to_neo4j(client, [element], [], _DEFAULT_MAPPING, "test.xml")
    assert result.elements_imported == 1
    merge_queries = [q for q, _ in client.queries if "MERGE" in q and "Process" in q]
    assert len(merge_queries) == 1


def test_import_archimate_id_lookup_on_reimport() -> None:
    from services.archimate_import_service import ArchiMateElement

    element = ArchiMateElement(
        archimate_id="id-42",
        archimate_type="BusinessProcess",
        name="Posteingang",
        bridgr_label="Process",
    )
    client = RecordingNeo4jClient(
        read_results={"archimate_id": [{"name": "Posteingang"}]}
    )
    result = _import_to_neo4j(client, [element], [], _DEFAULT_MAPPING, "test.xml")
    assert result.elements_imported == 1


def test_import_new_node_created_when_no_match() -> None:
    from services.archimate_import_service import ArchiMateElement

    element = ArchiMateElement(
        archimate_id="id-99",
        archimate_type="BusinessProcess",
        name="Neuer Process",
        bridgr_label="Process",
    )
    client = RecordingNeo4jClient(read_results={})
    result = _import_to_neo4j(client, [element], [], _DEFAULT_MAPPING, "test.xml")
    assert result.elements_imported == 1
    merge_queries = [q for q, _ in client.queries if "MERGE" in q and "Process" in q]
    assert len(merge_queries) == 1


def test_import_relation_imported_when_both_endpoints_resolved() -> None:
    from services.archimate_import_service import ArchiMateElement, ArchiMateRelation

    elements = [
        ArchiMateElement("id-1", "BusinessProcess", "Posteingang", "Process"),
        ArchiMateElement("id-2", "ApplicationComponent", "SAP SD", "Application"),
    ]
    relation = ArchiMateRelation("id-3", "Serving", "id-2", "id-1")
    client = RecordingNeo4jClient(read_results={})
    result = _import_to_neo4j(client, elements, [relation], _DEFAULT_MAPPING, "test.xml")
    assert result.elements_imported == 2
    assert result.relations_imported == 1
    assert result.relations_skipped == 0


def test_import_relation_skipped_when_type_not_accepted() -> None:
    from services.archimate_import_service import ArchiMateElement, ArchiMateRelation

    elements = [
        ArchiMateElement("id-1", "BusinessProcess", "Posteingang", "Process"),
        ArchiMateElement("id-2", "ApplicationComponent", "SAP SD", "Application"),
    ]
    relation = ArchiMateRelation("id-3", "Aggregation", "id-2", "id-1")
    client = RecordingNeo4jClient(read_results={})
    result = _import_to_neo4j(client, elements, [relation], _DEFAULT_MAPPING, "test.xml")
    assert result.relations_skipped == 1
    assert result.relations_imported == 0


def test_import_relation_skipped_when_endpoint_unresolved() -> None:
    from services.archimate_import_service import ArchiMateElement, ArchiMateRelation

    elements = [
        ArchiMateElement("id-1", "BusinessProcess", "Posteingang", "Process"),
    ]
    relation = ArchiMateRelation("id-3", "ServingRelationship", "id-unknown", "id-1")
    client = RecordingNeo4jClient(read_results={})
    result = _import_to_neo4j(client, elements, [relation], _DEFAULT_MAPPING, "test.xml")
    assert result.relations_skipped == 1


def test_import_org_prozess_assignment_creates_verantwortet() -> None:
    """OrgUnit->Process via Assignment must produce a RESPONSIBLE_FOR relation."""
    from services.archimate_import_service import ArchiMateElement, ArchiMateRelation

    elements = [
        ArchiMateElement("id-org", "BusinessActor", "Sales", "OrgUnit"),
        ArchiMateElement("id-proc", "BusinessProcess", "Auftragsabwicklung", "Process"),
    ]
    relation = ArchiMateRelation("id-rel", "Assignment", "id-org", "id-proc")
    client = RecordingNeo4jClient(read_results={})
    result = _import_to_neo4j(client, elements, [relation], _DEFAULT_MAPPING, "test.xml")
    assert result.relations_imported == 1
    assert result.relations_skipped == 0
    verantwortet_queries = [q for q, _ in client.queries if "RESPONSIBLE_FOR" in q]
    assert len(verantwortet_queries) == 1


def test_import_org_prozess_skipped_without_bridgr_relation_entry() -> None:
    """Without bridgr_relation entry, OrgUnit->Process is skipped even if import type matches."""
    from services.archimate_import_service import ArchiMateElement, ArchiMateRelation

    mapping_no_bridgr = {
        **_DEFAULT_MAPPING,
        "relationships": {
            **_DEFAULT_MAPPING["relationships"],
            "bridgr_relation": {},  # empty — no BRIDGR relation defined
        },
    }
    elements = [
        ArchiMateElement("id-org", "BusinessActor", "Sales", "OrgUnit"),
        ArchiMateElement("id-proc", "BusinessProcess", "Auftragsabwicklung", "Process"),
    ]
    relation = ArchiMateRelation("id-rel", "Assignment", "id-org", "id-proc")
    client = RecordingNeo4jClient(read_results={})
    result = _import_to_neo4j(client, elements, [relation], mapping_no_bridgr, "test.xml")
    assert result.relations_skipped == 1
    assert result.relations_imported == 0


# --- confirm_archimate_candidate_node ---

def test_confirm_archimate_candidate_node_transfers_relations_and_deletes_candidate() -> None:
    client = RecordingNeo4jClient(read_results={})

    confirm_archimate_candidate_node(
        client,
        label="Application",
        candidate_name="SAP S/4HANA FI",
        target_name="SAP S/4HANA CO",
        archimate_id="id-abc123",
    )

    written_queries = [q for q, _ in client.queries]
    assert any("DETACH DELETE" in q for q in written_queries)
    assert any("SET n.archimate_id" in q for q in written_queries)
    assert any("MERGE" in q for q in written_queries)


def test_confirm_archimate_candidate_node_raises_for_unknown_label() -> None:
    client = RecordingNeo4jClient(read_results={})

    with pytest.raises(ValueError, match="Unbekanntes Label"):
        confirm_archimate_candidate_node(
            client,
            label="UnbekanntesSonderLabel",
            candidate_name="X",
            target_name="Y",
            archimate_id="id-1",
        )


def test_confirm_archimate_candidate_node_sets_archimate_id_on_target() -> None:
    client = RecordingNeo4jClient(read_results={})

    confirm_archimate_candidate_node(
        client,
        label="Server",
        candidate_name="ns-dev-045",
        target_name="ns-dev-046",
        archimate_id="id-srv-99",
    )

    set_queries = [(q, p) for q, p in client.queries if "SET n.archimate_id" in q]
    assert len(set_queries) == 1
    assert set_queries[0][1].get("archimate_id") == "id-srv-99"
    assert set_queries[0][1].get("target_name") == "ns-dev-046"


# --- skipped_relations detail ---

def test_skipped_relation_unresolved_endpoint_recorded() -> None:
    from services.archimate_import_service import ArchiMateElement, ArchiMateRelation

    elements = [
        ArchiMateElement("id-1", "BusinessProcess", "Posteingang", "Process"),
    ]
    relation = ArchiMateRelation("id-3", "Serving", "id-unknown", "id-1")
    client = RecordingNeo4jClient(read_results={})
    result = _import_to_neo4j(client, elements, [relation], _DEFAULT_MAPPING, "test.xml")
    assert result.relations_skipped == 1
    assert len(result.skipped_relations) == 1
    entry = result.skipped_relations[0]
    assert entry["reason"] == "unresolvable_endpoint"
    assert entry["rel_type"] == "Serving"
    assert entry["target"] == "Posteingang"
    assert "Kandidat" in entry["source"]


def test_skipped_relation_type_not_accepted_recorded() -> None:
    from services.archimate_import_service import ArchiMateElement, ArchiMateRelation

    elements = [
        ArchiMateElement("id-1", "BusinessProcess", "Posteingang", "Process"),
        ArchiMateElement("id-2", "ApplicationComponent", "SAP SD", "Application"),
    ]
    relation = ArchiMateRelation("id-3", "Aggregation", "id-2", "id-1")
    client = RecordingNeo4jClient(read_results={})
    result = _import_to_neo4j(client, elements, [relation], _DEFAULT_MAPPING, "test.xml")
    assert result.relations_skipped == 1
    assert len(result.skipped_relations) == 1
    entry = result.skipped_relations[0]
    assert entry["reason"] == "type_not_accepted"
    assert entry["rel_type"] == "Aggregation"
    assert entry["source"] == "SAP SD"
    assert entry["target"] == "Posteingang"


def test_skipped_relation_no_bridgr_mapping_recorded() -> None:
    from services.archimate_import_service import ArchiMateElement, ArchiMateRelation

    mapping_no_bridgr = {
        **_DEFAULT_MAPPING,
        "relationships": {
            **_DEFAULT_MAPPING["relationships"],
            "bridgr_relation": {},
        },
    }
    elements = [
        ArchiMateElement("id-org", "BusinessActor", "Sales", "OrgUnit"),
        ArchiMateElement("id-proc", "BusinessProcess", "Auftragsabwicklung", "Process"),
    ]
    relation = ArchiMateRelation("id-rel", "Assignment", "id-org", "id-proc")
    client = RecordingNeo4jClient(read_results={})
    result = _import_to_neo4j(client, elements, [relation], mapping_no_bridgr, "test.xml")
    assert result.relations_skipped == 1
    assert len(result.skipped_relations) == 1
    entry = result.skipped_relations[0]
    assert entry["reason"] == "no_bridgr_relation"
    assert entry["source"] == "Sales"
    assert entry["target"] == "Auftragsabwicklung"


def test_skipped_relations_empty_when_all_imported() -> None:
    from services.archimate_import_service import ArchiMateElement, ArchiMateRelation

    elements = [
        ArchiMateElement("id-1", "BusinessProcess", "Posteingang", "Process"),
        ArchiMateElement("id-2", "ApplicationComponent", "SAP SD", "Application"),
    ]
    relation = ArchiMateRelation("id-3", "Serving", "id-2", "id-1")
    client = RecordingNeo4jClient(read_results={})
    result = _import_to_neo4j(client, elements, [relation], _DEFAULT_MAPPING, "test.xml")
    assert result.relations_imported == 1
    assert result.skipped_relations == []


# --- load_archimate_mapping ---

def test_load_archimate_mapping_returns_defaults_when_file_missing(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    import core.app_config as app_config
    monkeypatch.setattr(app_config, "PROJECT_ROOT", tmp_path)
    mapping = load_archimate_mapping()
    assert "elements" in mapping
    assert "relationships" in mapping
    assert "pending_candidates" in mapping


def test_load_archimate_mapping_reads_existing_file(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    import core.app_config as app_config
    monkeypatch.setattr(app_config, "PROJECT_ROOT", tmp_path)
    mapping_path = tmp_path / "data" / "archimate_mapping.json"
    mapping_path.parent.mkdir(parents=True, exist_ok=True)
    mapping_path.write_text(json.dumps({"custom": True}), encoding="utf-8")
    mapping = load_archimate_mapping(mapping_path)
    assert mapping.get("custom") is True


# --- three-state ignore logic ---

_IGNORE_XML = """\
<?xml version="1.0" encoding="UTF-8"?>
<model xmlns="http://www.opengroup.org/xsd/archimate/3.0/"
       xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
       identifier="id-model-ignore" version="3.0">
  <elements>
    <element identifier="id-30" xsi:type="Grouping">
      <name xml:lang="de">Meine Gruppe</name>
    </element>
    <element identifier="id-31" xsi:type="BusinessProcess">
      <name xml:lang="de">Regulaerer Process</name>
    </element>
  </elements>
  <relationships/>
</model>
"""

_MAPPING_WITH_IGNORE = {
    **_DEFAULT_MAPPING,
    "elements": {
        **_DEFAULT_MAPPING["elements"],
        "ignore": ["Grouping", "Location", "WorkPackage"],
    },
}


def test_ignore_list_skips_silently(tmp_path: Path) -> None:
    """Elements with type in ignore list are skipped without adding to skipped_types."""
    xml_file = tmp_path / "ignore.xml"
    xml_file.write_text(_IGNORE_XML, encoding="utf-8")
    elements, _, skipped = _parse_archimate_xml(xml_file, _MAPPING_WITH_IGNORE)
    assert len(elements) == 1
    assert elements[0].name == "Regulaerer Process"
    assert "Grouping" not in skipped


def test_uncategorized_type_in_skipped_types(tmp_path: Path) -> None:
    """Elements with type in neither import nor ignore appear in skipped_types."""
    xml_file = tmp_path / "unknown.xml"
    xml_file.write_text(_UNKNOWN_TYPE_XML, encoding="utf-8")
    # _DEFAULT_MAPPING has no ignore list, Capability not in import → must appear in skipped
    _, _, skipped = _parse_archimate_xml(xml_file, _DEFAULT_MAPPING)
    assert "Capability" in skipped
    assert skipped["Capability"] == 1


def test_new_label_faehigkeit_imported(tmp_path: Path) -> None:
    """Capability type maps to Capability label when present in import mapping."""
    mapping_with_capability = {
        **_DEFAULT_MAPPING,
        "elements": {
            **_DEFAULT_MAPPING["elements"],
            "import": {
                **_DEFAULT_MAPPING["elements"]["import"],
                "Capability": "Capability",
            },
        },
    }
    xml_file = tmp_path / "fähigkeit.xml"
    xml_file.write_text(_UNKNOWN_TYPE_XML, encoding="utf-8")
    elements, _, skipped = _parse_archimate_xml(xml_file, mapping_with_capability)
    faehigkeit_elements = [e for e in elements if e.bridgr_label == "Capability"]
    assert len(faehigkeit_elements) == 1
    assert faehigkeit_elements[0].archimate_type == "Capability"
    assert "Capability" not in skipped


def test_new_label_risiko_imported(tmp_path: Path) -> None:
    """Risk type maps to Risk label."""
    _RISK_XML = """\
<?xml version="1.0" encoding="UTF-8"?>
<model xmlns="http://www.opengroup.org/xsd/archimate/3.0/"
       xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
       identifier="id-model-risk" version="3.0">
  <elements>
    <element identifier="id-risk-1" xsi:type="Risk">
      <name xml:lang="de">Datenverlust</name>
    </element>
  </elements>
  <relationships/>
</model>
"""
    mapping_with_risk = {
        **_DEFAULT_MAPPING,
        "elements": {
            **_DEFAULT_MAPPING["elements"],
            "import": {
                **_DEFAULT_MAPPING["elements"]["import"],
                "Risk": "Risk",
            },
        },
    }
    xml_file = tmp_path / "risk.xml"
    xml_file.write_text(_RISK_XML, encoding="utf-8")
    elements, _, skipped = _parse_archimate_xml(xml_file, mapping_with_risk)
    assert len(elements) == 1
    assert elements[0].bridgr_label == "Risk"
    assert elements[0].archimate_type == "Risk"
    assert "Risk" not in skipped


# --- ArchiMate 3.1 namespace support ---

_MINIMAL_XML_31 = """\
<?xml version="1.0" encoding="UTF-8"?>
<model xmlns="http://www.opengroup.org/xsd/archimate/3.1/"
       xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
       identifier="id-model-31" version="3.1">
  <name xml:lang="de">Test 3.1</name>
  <elements>
    <element identifier="id-p1" xsi:type="BusinessProcess">
      <name xml:lang="de">Rechnungsstellung</name>
    </element>
    <element identifier="id-a1" xsi:type="ApplicationComponent">
      <name xml:lang="de">SAP FI</name>
    </element>
  </elements>
  <relationships>
    <relationship identifier="id-r1" xsi:type="Serving"
                  source="id-a1" target="id-p1"/>
  </relationships>
</model>
"""


def test_parse_archimate_31_namespace(tmp_path: Path) -> None:
    xml_file = tmp_path / "model31.xml"
    xml_file.write_text(_MINIMAL_XML_31, encoding="utf-8")
    elements, relations, skipped = _parse_archimate_xml(xml_file, _DEFAULT_MAPPING)
    assert len(elements) == 2
    names = {e.name for e in elements}
    assert "Rechnungsstellung" in names
    assert "SAP FI" in names
    assert len(relations) == 1
    assert relations[0].archimate_rel_type == "Serving"
    assert skipped == {}


def test_parse_archimate_30_namespace_still_works(tmp_path: Path) -> None:
    xml_file = tmp_path / "model30.xml"
    xml_file.write_text(_MINIMAL_XML, encoding="utf-8")
    elements, relations, _ = _parse_archimate_xml(xml_file, _DEFAULT_MAPPING)
    assert len(elements) == 2
    assert len(relations) == 1


# --- Motivation layer type mappings ---

_MOTIVATION_MAPPING = {
    **_DEFAULT_MAPPING,
    "elements": {
        **_DEFAULT_MAPPING["elements"],
        "import": {
            **_DEFAULT_MAPPING["elements"]["import"],
            "Goal": "Goal",
            "Outcome": "Goal",
            "Meaning": "Goal",
            "Value": "Goal",
            "Principle": "Requirement",
            "Requirement": "Requirement",
            "Constraint": "Requirement",
            "Driver": "Context",
            "Assessment": "Context",
            "Stakeholder": "Stakeholder",
        },
    },
}

_MOTIVATION_XML = """\
<?xml version="1.0" encoding="UTF-8"?>
<model xmlns="http://www.opengroup.org/xsd/archimate/3.0/"
       xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
       identifier="id-motivation" version="3.0">
  <elements>
    <element identifier="id-g1" xsi:type="Goal">
      <name xml:lang="de">Kundenzufriedenheit steigern</name>
    </element>
    <element identifier="id-r1" xsi:type="Requirement">
      <name xml:lang="de">Antwortzeit unter 2 Sekunden</name>
    </element>
    <element identifier="id-d1" xsi:type="Driver">
      <name xml:lang="de">Wettbewerbsdruck</name>
    </element>
    <element identifier="id-s1" xsi:type="Stakeholder">
      <name xml:lang="de">IT-Leitung</name>
    </element>
    <element identifier="id-a1" xsi:type="Assessment">
      <name xml:lang="de">SWOT-Analyse 2026</name>
    </element>
    <element identifier="id-c1" xsi:type="Constraint">
      <name xml:lang="de">DSGVO-Konformität</name>
    </element>
  </elements>
  <relationships/>
</model>
"""


def test_motivation_types_mapped_to_correct_labels(tmp_path: Path) -> None:
    xml_file = tmp_path / "motivation.xml"
    xml_file.write_text(_MOTIVATION_XML, encoding="utf-8")
    elements, _, skipped = _parse_archimate_xml(xml_file, _MOTIVATION_MAPPING)
    label_map = {e.archimate_type: e.bridgr_label for e in elements}
    assert label_map["Goal"] == "Goal"
    assert label_map["Requirement"] == "Requirement"
    assert label_map["Driver"] == "Context"
    assert label_map["Stakeholder"] == "Stakeholder"
    assert label_map["Assessment"] == "Context"
    assert label_map["Constraint"] == "Requirement"
    assert skipped == {}


def test_goal_maps_to_ziel(tmp_path: Path) -> None:
    xml = """\
<?xml version="1.0" encoding="UTF-8"?>
<model xmlns="http://www.opengroup.org/xsd/archimate/3.0/"
       xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
       identifier="id-g" version="3.0">
  <elements>
    <element identifier="id-1" xsi:type="Goal">
      <name xml:lang="de">Effizienz steigern</name>
    </element>
  </elements>
  <relationships/>
</model>
"""
    xml_file = tmp_path / "goal.xml"
    xml_file.write_text(xml, encoding="utf-8")
    elements, _, _ = _parse_archimate_xml(xml_file, _MOTIVATION_MAPPING)
    assert elements[0].bridgr_label == "Goal"
    assert elements[0].archimate_type == "Goal"


def test_business_actor_maps_to_orgeinheit(tmp_path: Path) -> None:
    xml = """\
<?xml version="1.0" encoding="UTF-8"?>
<model xmlns="http://www.opengroup.org/xsd/archimate/3.0/"
       xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
       identifier="id-ba" version="3.0">
  <elements>
    <element identifier="id-1" xsi:type="BusinessActor">
      <name xml:lang="de">Vertriebsabteilung</name>
    </element>
  </elements>
  <relationships/>
</model>
"""
    xml_file = tmp_path / "actor.xml"
    xml_file.write_text(xml, encoding="utf-8")
    elements, _, _ = _parse_archimate_xml(xml_file, _DEFAULT_MAPPING)
    assert len(elements) == 1
    assert elements[0].bridgr_label == "OrgUnit"
    assert elements[0].archimate_type == "BusinessActor"


# --- Motivation layer relation imports ---

_MOTIVATION_WITH_RELS_XML = """\
<?xml version="1.0" encoding="UTF-8"?>
<model xmlns="http://www.opengroup.org/xsd/archimate/3.0/"
       xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
       identifier="id-mrels" version="3.0">
  <elements>
    <element identifier="id-k1" xsi:type="Driver">
      <name xml:lang="de">Regulierung</name>
    </element>
    <element identifier="id-z1" xsi:type="Goal">
      <name xml:lang="de">Compliance</name>
    </element>
    <element identifier="id-anf1" xsi:type="Requirement">
      <name xml:lang="de">Datenschutzpflicht</name>
    </element>
    <element identifier="id-sh1" xsi:type="Stakeholder">
      <name xml:lang="de">Datenschutzbeauftragter</name>
    </element>
  </elements>
  <relationships>
    <relationship identifier="id-r1" xsi:type="Influence" source="id-k1" target="id-z1"/>
    <relationship identifier="id-r2" xsi:type="Realization" source="id-anf1" target="id-z1"/>
    <relationship identifier="id-r3" xsi:type="Association" source="id-sh1" target="id-z1"/>
  </relationships>
</model>
"""

_MOTIVATION_MAPPING_WITH_RELS = {
    **_MOTIVATION_MAPPING,
    "relationships": {
        "import": {
            "Context->Goal": ["Influence", "Association"],
            "Requirement->Goal": ["Realization", "Association"],
            "Stakeholder->Goal": ["Association"],
        },
        "export": {},
        "bridgr_relation": {
            "Context->Goal": "INFLUENCES",
            "Requirement->Goal": "REALIZES",
            "Stakeholder->Goal": "CONNECTED_TO",
        },
    },
}


def test_motivation_relations_imported(tmp_path: Path) -> None:
    xml_file = tmp_path / "mrels.xml"
    xml_file.write_text(_MOTIVATION_WITH_RELS_XML, encoding="utf-8")
    client = RecordingNeo4jClient(read_results={})
    elements, relations, _ = _parse_archimate_xml(xml_file, _MOTIVATION_MAPPING_WITH_RELS)
    result = _import_to_neo4j(client, elements, relations, _MOTIVATION_MAPPING_WITH_RELS, "mrels.xml")
    assert result.elements_imported == 4
    assert result.relations_imported == 3
    assert result.relations_skipped == 0
    beeinflusst_qs = [q for q, _ in client.queries if "INFLUENCES" in q]
    realisiert_qs = [q for q, _ in client.queries if "REALIZES" in q]
    verbunden_qs = [q for q, _ in client.queries if "CONNECTED_TO" in q]
    assert len(beeinflusst_qs) == 1
    assert len(realisiert_qs) == 1
    assert len(verbunden_qs) == 1

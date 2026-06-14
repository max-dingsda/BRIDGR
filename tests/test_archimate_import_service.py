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
      <name xml:lang="de">Prozess A</name>
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
            "BusinessProcess": "Prozess",
            "ApplicationComponent": "Anwendung",
            "BusinessActor": "OrgEinheit",
        },
        "export": {},
    },
    "relationships": {
        "import": {
            "Anwendung->Prozess": ["Serving"],
            "Prozess->Prozess": ["Triggering", "Flow"],
            "OrgEinheit->Prozess": ["Assignment"],
        },
        "export": {},
        "bridgr_relation": {
            "Anwendung->Prozess":        "DIENT",
            "Rolle->Prozess":            "BETEILIGT_AN",
            "OrgEinheit->Rolle":         "KANN_EINNEHMEN",
            "Prozess->Prozess":          "FOLGT_AUF",
            "Anwendung->Schnittstelle":  "USES_INTERFACE",
            "Anwendung->Server":         "RUNS_ON",
            "Schnittstelle->Server":     "RUNS_ON",
            "OrgEinheit->Anwendung":     "VERANTWORTET",
            "OrgEinheit->Schnittstelle": "VERANTWORTET",
            "OrgEinheit->Server":        "VERANTWORTET",
            "OrgEinheit->Prozess":       "VERANTWORTET",
        },
    },
    "pending_candidates": [],
}


class RecordingNeo4jClient:
    def __init__(self, read_results: dict[str, list[dict]] | None = None) -> None:
        self.queries: list[tuple[str, dict | None]] = []
        self._read_results = read_results or {}

    def ensure_constraints(self) -> None:
        pass

    def execute_write(self, query: str, parameters=None):
        self.queries.append((query, parameters))
        return []

    def execute_read(self, query: str, parameters=None):
        for key, result in self._read_results.items():
            if key in query:
                return result
        return []


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
    assert elements[0].bridgr_label == "Prozess"
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
    assert elements[0].name == "Prozess A"
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
    assert _label_pair_to_relation("Anwendung", "Prozess", _BRIDGR_MAP) == "DIENT"
    assert _label_pair_to_relation("Prozess", "Prozess", _BRIDGR_MAP) == "FOLGT_AUF"
    assert _label_pair_to_relation("OrgEinheit", "Anwendung", _BRIDGR_MAP) == "VERANTWORTET"


def test_label_pair_org_prozess_returns_verantwortet() -> None:
    assert _label_pair_to_relation("OrgEinheit", "Prozess", _BRIDGR_MAP) == "VERANTWORTET"


def test_label_pair_to_relation_unknown_returns_none() -> None:
    assert _label_pair_to_relation("Prozess", "Anwendung", _BRIDGR_MAP) is None


def test_label_pair_to_relation_empty_map_returns_none() -> None:
    assert _label_pair_to_relation("Anwendung", "Prozess", {}) is None


def test_label_pair_to_relation_reads_custom_map() -> None:
    custom = {"Anwendung->Prozess": "CUSTOM_REL"}
    assert _label_pair_to_relation("Anwendung", "Prozess", custom) == "CUSTOM_REL"


# --- _import_to_neo4j ---

def test_import_exact_name_match_merges_existing(tmp_path: Path) -> None:
    from services.archimate_import_service import ArchiMateElement, ArchiMateRelation

    element = ArchiMateElement(
        archimate_id="id-1",
        archimate_type="BusinessProcess",
        name="Posteingang",
        bridgr_label="Prozess",
    )
    client = RecordingNeo4jClient(
        read_results={"archimate_id": [], "n.name": [{"name": "Posteingang"}]}
    )
    result = _import_to_neo4j(client, [element], [], _DEFAULT_MAPPING, "test.xml")
    assert result.elements_imported == 1
    merge_queries = [q for q, _ in client.queries if "MERGE" in q and "Prozess" in q]
    assert len(merge_queries) == 1


def test_import_archimate_id_lookup_on_reimport() -> None:
    from services.archimate_import_service import ArchiMateElement

    element = ArchiMateElement(
        archimate_id="id-42",
        archimate_type="BusinessProcess",
        name="Posteingang",
        bridgr_label="Prozess",
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
        name="Neuer Prozess",
        bridgr_label="Prozess",
    )
    client = RecordingNeo4jClient(read_results={})
    result = _import_to_neo4j(client, [element], [], _DEFAULT_MAPPING, "test.xml")
    assert result.elements_imported == 1
    merge_queries = [q for q, _ in client.queries if "MERGE" in q and "Prozess" in q]
    assert len(merge_queries) == 1


def test_import_relation_imported_when_both_endpoints_resolved() -> None:
    from services.archimate_import_service import ArchiMateElement, ArchiMateRelation

    elements = [
        ArchiMateElement("id-1", "BusinessProcess", "Posteingang", "Prozess"),
        ArchiMateElement("id-2", "ApplicationComponent", "SAP SD", "Anwendung"),
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
        ArchiMateElement("id-1", "BusinessProcess", "Posteingang", "Prozess"),
        ArchiMateElement("id-2", "ApplicationComponent", "SAP SD", "Anwendung"),
    ]
    relation = ArchiMateRelation("id-3", "Aggregation", "id-2", "id-1")
    client = RecordingNeo4jClient(read_results={})
    result = _import_to_neo4j(client, elements, [relation], _DEFAULT_MAPPING, "test.xml")
    assert result.relations_skipped == 1
    assert result.relations_imported == 0


def test_import_relation_skipped_when_endpoint_unresolved() -> None:
    from services.archimate_import_service import ArchiMateElement, ArchiMateRelation

    elements = [
        ArchiMateElement("id-1", "BusinessProcess", "Posteingang", "Prozess"),
    ]
    relation = ArchiMateRelation("id-3", "ServingRelationship", "id-unknown", "id-1")
    client = RecordingNeo4jClient(read_results={})
    result = _import_to_neo4j(client, elements, [relation], _DEFAULT_MAPPING, "test.xml")
    assert result.relations_skipped == 1


def test_import_org_prozess_assignment_creates_verantwortet() -> None:
    """OrgEinheit->Prozess via Assignment must produce a VERANTWORTET relation."""
    from services.archimate_import_service import ArchiMateElement, ArchiMateRelation

    elements = [
        ArchiMateElement("id-org", "BusinessActor", "Sales", "OrgEinheit"),
        ArchiMateElement("id-proc", "BusinessProcess", "Auftragsabwicklung", "Prozess"),
    ]
    relation = ArchiMateRelation("id-rel", "Assignment", "id-org", "id-proc")
    client = RecordingNeo4jClient(read_results={})
    result = _import_to_neo4j(client, elements, [relation], _DEFAULT_MAPPING, "test.xml")
    assert result.relations_imported == 1
    assert result.relations_skipped == 0
    verantwortet_queries = [q for q, _ in client.queries if "VERANTWORTET" in q]
    assert len(verantwortet_queries) == 1


def test_import_org_prozess_skipped_without_bridgr_relation_entry() -> None:
    """Without bridgr_relation entry, OrgEinheit->Prozess is skipped even if import type matches."""
    from services.archimate_import_service import ArchiMateElement, ArchiMateRelation

    mapping_no_bridgr = {
        **_DEFAULT_MAPPING,
        "relationships": {
            **_DEFAULT_MAPPING["relationships"],
            "bridgr_relation": {},  # empty — no BRIDGR relation defined
        },
    }
    elements = [
        ArchiMateElement("id-org", "BusinessActor", "Sales", "OrgEinheit"),
        ArchiMateElement("id-proc", "BusinessProcess", "Auftragsabwicklung", "Prozess"),
    ]
    relation = ArchiMateRelation("id-rel", "Assignment", "id-org", "id-proc")
    client = RecordingNeo4jClient(read_results={})
    result = _import_to_neo4j(client, elements, [relation], mapping_no_bridgr, "test.xml")
    assert result.relations_skipped == 1
    assert result.relations_imported == 0


# --- skipped_relations detail ---

def test_skipped_relation_unresolved_endpoint_recorded() -> None:
    from services.archimate_import_service import ArchiMateElement, ArchiMateRelation

    elements = [
        ArchiMateElement("id-1", "BusinessProcess", "Posteingang", "Prozess"),
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
    assert entry["source"] == "?"


def test_skipped_relation_type_not_accepted_recorded() -> None:
    from services.archimate_import_service import ArchiMateElement, ArchiMateRelation

    elements = [
        ArchiMateElement("id-1", "BusinessProcess", "Posteingang", "Prozess"),
        ArchiMateElement("id-2", "ApplicationComponent", "SAP SD", "Anwendung"),
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
        ArchiMateElement("id-org", "BusinessActor", "Sales", "OrgEinheit"),
        ArchiMateElement("id-proc", "BusinessProcess", "Auftragsabwicklung", "Prozess"),
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
        ArchiMateElement("id-1", "BusinessProcess", "Posteingang", "Prozess"),
        ArchiMateElement("id-2", "ApplicationComponent", "SAP SD", "Anwendung"),
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
      <name xml:lang="de">Regulaerer Prozess</name>
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
    assert elements[0].name == "Regulaerer Prozess"
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
    """Capability type maps to Faehigkeit label when present in import mapping."""
    mapping_with_capability = {
        **_DEFAULT_MAPPING,
        "elements": {
            **_DEFAULT_MAPPING["elements"],
            "import": {
                **_DEFAULT_MAPPING["elements"]["import"],
                "Capability": "Faehigkeit",
            },
        },
    }
    xml_file = tmp_path / "fähigkeit.xml"
    xml_file.write_text(_UNKNOWN_TYPE_XML, encoding="utf-8")
    elements, _, skipped = _parse_archimate_xml(xml_file, mapping_with_capability)
    faehigkeit_elements = [e for e in elements if e.bridgr_label == "Faehigkeit"]
    assert len(faehigkeit_elements) == 1
    assert faehigkeit_elements[0].archimate_type == "Capability"
    assert "Capability" not in skipped


def test_new_label_risiko_imported(tmp_path: Path) -> None:
    """Risk type maps to Risiko label."""
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
                "Risk": "Risiko",
            },
        },
    }
    xml_file = tmp_path / "risk.xml"
    xml_file.write_text(_RISK_XML, encoding="utf-8")
    elements, _, skipped = _parse_archimate_xml(xml_file, mapping_with_risk)
    assert len(elements) == 1
    assert elements[0].bridgr_label == "Risiko"
    assert elements[0].archimate_type == "Risk"
    assert "Risk" not in skipped

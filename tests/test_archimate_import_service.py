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
        },
        "export": {},
    },
    "relationships": {
        "import": {
            "Anwendung->Prozess": ["Serving"],
            "Prozess->Prozess": ["Triggering", "Flow"],
        },
        "export": {},
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
    elements, relations = _parse_archimate_xml(xml_file, _DEFAULT_MAPPING)
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
    elements, _ = _parse_archimate_xml(xml_file, _DEFAULT_MAPPING)
    assert elements[0].name == "Posteingang"
    assert elements[1].name == "Bestellabwicklung"


def test_parse_unknown_type_skipped(tmp_path: Path) -> None:
    xml_file = tmp_path / "unknown.xml"
    xml_file.write_text(_UNKNOWN_TYPE_XML, encoding="utf-8")
    elements, _ = _parse_archimate_xml(xml_file, _DEFAULT_MAPPING)
    # Capability not in import mapping → skipped; BusinessProcess included
    assert len(elements) == 1
    assert elements[0].name == "Prozess A"


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

def test_label_pair_to_relation_known() -> None:
    assert _label_pair_to_relation("Anwendung", "Prozess") == "DIENT"
    assert _label_pair_to_relation("Prozess", "Prozess") == "FOLGT_AUF"
    assert _label_pair_to_relation("OrgEinheit", "Anwendung") == "VERANTWORTET"


def test_label_pair_to_relation_unknown_returns_none() -> None:
    assert _label_pair_to_relation("Prozess", "Anwendung") is None


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

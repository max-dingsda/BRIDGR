from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

from app_config import AppConfig
from services.archimate_export_service import _build_archimate_export

_ARCHIMATE_NS = "http://www.opengroup.org/xsd/archimate/3.0/"
_XSI_NS = "http://www.w3.org/2001/XMLSchema-instance"

_DEFAULT_MAPPING = {
    "elements": {
        "export": {
            "Prozess":       "BusinessProcess",
            "Anwendung":     "ApplicationComponent",
            "Schnittstelle": "ApplicationInterface",
            "Server":        "Node",
            "OrgEinheit":    "BusinessActor",
            "Rolle":         "BusinessRole",
        }
    },
    "relationships": {
        "export": {
            "Anwendung->Prozess": "ServingRelationship",
            "Prozess->Prozess":   "TriggeringRelationship",
        }
    },
}


class FakeNeo4jClient:
    def __init__(self, nodes: list[dict], relations: list[dict]) -> None:
        self._nodes = nodes
        self._relations = relations

    def execute_read(self, query: str, parameters=None):
        if "archimate_id" in query or "archimate_type" in query:
            return self._nodes
        return self._relations

    def execute_write(self, query: str, parameters=None):
        return []


def _run(tmp_path: Path, nodes: list[dict], relations: list[dict]):
    config = AppConfig(output_path=str(tmp_path / "Output"))
    client = FakeNeo4jClient(nodes, relations)
    return _build_archimate_export(client, config, _DEFAULT_MAPPING)


def _parse_export(output_path: str) -> ET.Element:
    tree = ET.parse(output_path)
    return tree.getroot()


def test_export_produces_valid_xml_with_correct_namespace(tmp_path: Path) -> None:
    nodes = [{"label": "Prozess", "name": "Posteingang", "archimate_id": None, "archimate_type": None}]
    result = _run(tmp_path, nodes, [])
    assert result.elements_exported == 1
    root = _parse_export(result.output_path)
    assert _ARCHIMATE_NS in root.tag


def test_export_uses_canonical_type_when_no_archimate_type(tmp_path: Path) -> None:
    nodes = [{"label": "Prozess", "name": "Posteingang", "archimate_id": None, "archimate_type": None}]
    result = _run(tmp_path, nodes, [])
    root = _parse_export(result.output_path)
    elements = root.find(f"{{{_ARCHIMATE_NS}}}elements")
    elem = elements.find(f"{{{_ARCHIMATE_NS}}}element")
    assert elem.get(f"{{{_XSI_NS}}}type") == "BusinessProcess"


def test_export_uses_original_type_for_roundtrip(tmp_path: Path) -> None:
    nodes = [
        {"label": "Prozess", "name": "Posteingang", "archimate_id": "id-1", "archimate_type": "BusinessFunction"},
    ]
    result = _run(tmp_path, nodes, [])
    root = _parse_export(result.output_path)
    elements = root.find(f"{{{_ARCHIMATE_NS}}}elements")
    elem = elements.find(f"{{{_ARCHIMATE_NS}}}element")
    assert elem.get(f"{{{_XSI_NS}}}type") == "BusinessFunction"


def test_export_skips_node_without_export_mapping(tmp_path: Path) -> None:
    nodes = [{"label": "Alias", "name": "SomeAlias", "archimate_id": None, "archimate_type": None}]
    result = _run(tmp_path, nodes, [])
    assert result.elements_exported == 0


def test_export_relation_uses_canonical_type(tmp_path: Path) -> None:
    nodes = [
        {"label": "Anwendung", "name": "SAP SD",      "archimate_id": None, "archimate_type": None},
        {"label": "Prozess",   "name": "Posteingang",  "archimate_id": None, "archimate_type": None},
    ]
    relations = [
        {"src_label": "Anwendung", "src_name": "SAP SD",
         "tgt_label": "Prozess",   "tgt_name": "Posteingang",
         "rel_type": "DIENT",      "archimate_rel_type": None},
    ]
    result = _run(tmp_path, nodes, relations)
    assert result.relations_exported == 1
    root = _parse_export(result.output_path)
    rels_el = root.find(f"{{{_ARCHIMATE_NS}}}relationships")
    rel = rels_el.find(f"{{{_ARCHIMATE_NS}}}relationship")
    assert rel.get(f"{{{_XSI_NS}}}type") == "ServingRelationship"


def test_export_relation_uses_original_rel_type_for_roundtrip(tmp_path: Path) -> None:
    nodes = [
        {"label": "Prozess", "name": "Prozess A", "archimate_id": None, "archimate_type": None},
        {"label": "Prozess", "name": "Prozess B", "archimate_id": None, "archimate_type": None},
    ]
    relations = [
        {"src_label": "Prozess", "src_name": "Prozess A",
         "tgt_label": "Prozess", "tgt_name": "Prozess B",
         "rel_type": "FOLGT_AUF", "archimate_rel_type": "FlowRelationship"},
    ]
    result = _run(tmp_path, nodes, relations)
    assert result.relations_exported == 1
    root = _parse_export(result.output_path)
    rels_el = root.find(f"{{{_ARCHIMATE_NS}}}relationships")
    rel = rels_el.find(f"{{{_ARCHIMATE_NS}}}relationship")
    assert rel.get(f"{{{_XSI_NS}}}type") == "FlowRelationship"


def test_export_counts_correct(tmp_path: Path) -> None:
    nodes = [
        {"label": "Prozess",   "name": "P1",   "archimate_id": None, "archimate_type": None},
        {"label": "Anwendung", "name": "App1", "archimate_id": None, "archimate_type": None},
    ]
    relations = [
        {"src_label": "Anwendung", "src_name": "App1",
         "tgt_label": "Prozess",   "tgt_name": "P1",
         "rel_type": "DIENT",      "archimate_rel_type": None},
    ]
    result = _run(tmp_path, nodes, relations)
    assert result.elements_exported == 2
    assert result.relations_exported == 1

from __future__ import annotations

from pathlib import Path

import pytest

from core.graph_schema import (
    QUERY_NODE_SCHEMA,
    QUERY_RELATIONSHIP_PATTERNS,
    QUERY_RELATIONSHIP_SCHEMA,
    build_query_schema_reference,
    build_archimate_mapping_reference,
    validate_query_schema,
)


# --- QUERY_NODE_SCHEMA contents ---

def test_ablehnung_not_in_node_schema() -> None:
    assert "Ablehnung" not in QUERY_NODE_SCHEMA


def test_expected_labels_in_node_schema() -> None:
    for label in ("Prozess", "Anwendung", "Schnittstelle", "Server", "OrgEinheit", "Rolle"):
        assert label in QUERY_NODE_SCHEMA


# --- DIENT relationship properties ---

def test_raw_name_not_in_dient_properties() -> None:
    assert "raw_name" not in QUERY_RELATIONSHIP_SCHEMA.get("DIENT", ())


def test_konfidenz_in_dient_properties() -> None:
    assert "konfidenz" in QUERY_RELATIONSHIP_SCHEMA.get("DIENT", ())


def test_source_in_dient_properties() -> None:
    assert "source" in QUERY_RELATIONSHIP_SCHEMA.get("DIENT", ())


# --- build_query_schema_reference output ---

def test_schema_reference_excludes_ablehnung() -> None:
    ref = build_query_schema_reference()
    assert "Ablehnung" not in ref


def test_schema_reference_excludes_raw_name() -> None:
    ref = build_query_schema_reference()
    assert "raw_name" not in ref


def test_schema_reference_includes_konfidenz_and_source() -> None:
    ref = build_query_schema_reference()
    assert "konfidenz" in ref
    assert "source" in ref


# --- validate_query_schema: Ablehnung rejected ---

def test_validator_rejects_ablehnung_label() -> None:
    with pytest.raises(ValueError, match="unknown node label"):
        validate_query_schema("MATCH (a:Ablehnung) RETURN a.prozess_name")


# --- validate_query_schema: known labels accepted ---

def test_validator_accepts_known_labels() -> None:
    validate_query_schema(
        "MATCH (a:Anwendung)-[:DIENT]->(p:Prozess) RETURN a.name, p.name"
    )


def test_validator_accepts_folgt_auf() -> None:
    validate_query_schema(
        "MATCH (p1:Prozess)-[:FOLGT_AUF]->(p2:Prozess) RETURN p1.name, p2.name"
    )


def test_validator_accepts_könnte_dienen() -> None:
    validate_query_schema(
        "MATCH (a:Anwendung)-[:KÖNNTE_DIENEN]->(p:Prozess) RETURN a.name, p.name"
    )


def test_validator_accepts_könnte_verantworten() -> None:
    validate_query_schema(
        "MATCH (o:OrgEinheit)-[:KÖNNTE_VERANTWORTEN]->(a:Anwendung) RETURN o.name, a.name"
    )


def test_validator_rejects_unknown_relationship_type() -> None:
    with pytest.raises(ValueError, match="unknown relationship type"):
        validate_query_schema(
            "MATCH (a:Anwendung)-[:INVENTED_REL]->(p:Prozess) RETURN a.name"
        )


def test_validator_rejects_unknown_node_property() -> None:
    with pytest.raises(ValueError, match="unknown property"):
        validate_query_schema(
            "MATCH (p:Prozess) RETURN p.raw_name"
        )


# --- New labels in QUERY_NODE_SCHEMA ---

def test_new_labels_in_node_schema() -> None:
    for label in ("Faehigkeit", "Ressource", "Ziel", "Risiko", "Datenobjekt", "Infrastruktur"):
        assert label in QUERY_NODE_SCHEMA, f"{label} missing from QUERY_NODE_SCHEMA"


def test_new_labels_have_expected_properties() -> None:
    for label in ("Faehigkeit", "Ressource", "Ziel", "Risiko", "Datenobjekt", "Infrastruktur"):
        props = QUERY_NODE_SCHEMA[label]
        assert "name" in props
        assert "archimate_type" in props
        assert "archimate_id" in props


# --- New relationship patterns ---

def test_new_relationship_patterns_present() -> None:
    patterns = {(p.relationship_type, p.source_label, p.target_label) for p in QUERY_RELATIONSHIP_PATTERNS}
    expected = [
        ("BETRIFFT", "Risiko", "Anwendung"),
        ("BETRIFFT", "Risiko", "Prozess"),
        ("BETRIFFT", "Risiko", "Server"),
        ("BETRIFFT", "Risiko", "Schnittstelle"),
        ("MITIGIERT", "Faehigkeit", "Risiko"),
        ("MITIGIERT", "Anwendung", "Risiko"),
        ("REALISIERT", "Faehigkeit", "Prozess"),
        ("REALISIERT", "Faehigkeit", "Anwendung"),
        ("BENOETIGT", "Prozess", "Ressource"),
        ("BENOETIGT", "Anwendung", "Ressource"),
        ("UNTERSTUETZT", "Anwendung", "Ziel"),
        ("UNTERSTUETZT", "Prozess", "Ziel"),
        ("VERARBEITET", "Anwendung", "Datenobjekt"),
        ("VERARBEITET", "Prozess", "Datenobjekt"),
        ("LAEUFT_AUF", "Anwendung", "Infrastruktur"),
    ]
    for triple in expected:
        assert triple in patterns, f"Pattern {triple} missing from QUERY_RELATIONSHIP_PATTERNS"


# --- build_query_schema_reference includes new labels ---

def test_schema_reference_includes_new_labels() -> None:
    ref = build_query_schema_reference()
    for label in ("Faehigkeit", "Ressource", "Ziel", "Risiko", "Datenobjekt", "Infrastruktur"):
        assert label in ref, f"{label} missing from schema reference"


def test_schema_reference_includes_new_relationships() -> None:
    ref = build_query_schema_reference()
    for rel in ("BETRIFFT", "MITIGIERT", "REALISIERT", "BENOETIGT", "UNTERSTUETZT", "VERARBEITET", "LAEUFT_AUF"):
        assert rel in ref, f"{rel} missing from schema reference"


# --- validator accepts new labels ---

def test_validator_accepts_risiko_label() -> None:
    validate_query_schema("MATCH (r:Risiko) RETURN r.name")


def test_validator_accepts_betrifft_relationship() -> None:
    validate_query_schema(
        "MATCH (r:Risiko)-[:BETRIFFT]->(a:Anwendung) RETURN r.name, a.name"
    )


def test_validator_accepts_laeuft_auf_relationship() -> None:
    validate_query_schema(
        "MATCH (a:Anwendung)-[:LAEUFT_AUF]->(i:Infrastruktur) RETURN a.name, i.name"
    )


# --- build_archimate_mapping_reference handles ignore list ---

def test_archimate_mapping_reference_with_ignore_list(tmp_path: Path, monkeypatch) -> None:
    import json
    import core.app_config as app_config

    mapping = {
        "elements": {
            "import": {"BusinessProcess": "Prozess", "Capability": "Faehigkeit"},
            "ignore": ["Grouping", "Location"],
            "export": {},
        },
        "relationships": {},
    }
    mapping_file = tmp_path / "data" / "archimate_mapping.json"
    mapping_file.parent.mkdir(parents=True, exist_ok=True)
    mapping_file.write_text(json.dumps(mapping), encoding="utf-8")
    monkeypatch.setattr(app_config, "PROJECT_ROOT", tmp_path)
    monkeypatch.chdir(tmp_path)

    ref = build_archimate_mapping_reference()
    assert "Grouping" in ref
    assert "Location" in ref
    # Import map entries should appear
    assert "BusinessProcess" in ref
    assert "Faehigkeit" in ref


def test_archimate_mapping_reference_without_ignore_list(tmp_path: Path, monkeypatch) -> None:
    import json
    import core.app_config as app_config

    mapping = {
        "elements": {
            "import": {"BusinessProcess": "Prozess"},
            "export": {},
        },
        "relationships": {},
    }
    mapping_file = tmp_path / "data" / "archimate_mapping.json"
    mapping_file.parent.mkdir(parents=True, exist_ok=True)
    mapping_file.write_text(json.dumps(mapping), encoding="utf-8")
    monkeypatch.setattr(app_config, "PROJECT_ROOT", tmp_path)
    monkeypatch.chdir(tmp_path)

    ref = build_archimate_mapping_reference()
    # No ignore note when list is empty/absent
    assert "explicitly ignored" not in ref

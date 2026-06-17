from __future__ import annotations

import json
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


def test_new_labels_have_required_properties() -> None:
    for label in ("Faehigkeit", "Ressource", "Ziel", "Risiko", "Datenobjekt", "Infrastruktur"):
        props = QUERY_NODE_SCHEMA[label]
        assert "name" in props
        assert "archimate_type" in props
        assert "archimate_id" in props


# --- New relationship patterns in QUERY_RELATIONSHIP_PATTERNS ---

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
    for pattern in expected:
        assert pattern in patterns, f"Pattern {pattern} missing from QUERY_RELATIONSHIP_PATTERNS"


# --- build_query_schema_reference includes new labels ---

def test_schema_reference_includes_new_labels() -> None:
    ref = build_query_schema_reference()
    for label in ("Faehigkeit", "Ressource", "Ziel", "Risiko", "Datenobjekt", "Infrastruktur"):
        assert label in ref, f"{label} missing from schema reference"


# --- validator accepts new labels ---

def test_validator_accepts_risiko_label() -> None:
    validate_query_schema("MATCH (r:Risiko)-[:BETRIFFT]->(a:Anwendung) RETURN r.name, a.name")


def test_validator_accepts_faehigkeit_label() -> None:
    validate_query_schema("MATCH (f:Faehigkeit)-[:REALISIERT]->(p:Prozess) RETURN f.name, p.name")


def test_validator_accepts_laeuft_auf() -> None:
    validate_query_schema("MATCH (a:Anwendung)-[:LAEUFT_AUF]->(i:Infrastruktur) RETURN a.name, i.name")


# --- build_archimate_mapping_reference handles ignore list ---

def _make_archimate_ref_from_mapping(raw: dict) -> str:
    """Helper: build an archimate mapping reference string directly from a dict."""
    import_map: dict[str, str] = raw.get("elements", {}).get("import", {})
    ignore_list: list[str] = raw.get("elements", {}).get("ignore", [])
    if not import_map:
        return ""
    rows = "\n".join(
        f"| {k:<22} | {v} |"
        for k, v in sorted(import_map.items())
    )
    ignore_note = ""
    if ignore_list:
        ignore_note = (
            "\n\nThe following ArchiMate types are intentionally ignored during import "
            "(silently skipped, not modeled in BRIDGR):\n"
            + ", ".join(sorted(ignore_list))
        )
    return (
        "## ArchiMate-Mapping\n\n"
        "| archimate_type         | BRIDGR-Label  |\n"
        "|------------------------|---------------|\n"
        f"{rows}"
        f"{ignore_note}"
    )


def test_archimate_mapping_reference_includes_ignore_note() -> None:
    mapping_data = {
        "elements": {
            "import": {"BusinessProcess": "Prozess"},
            "ignore": ["Grouping", "Location"],
        }
    }
    ref = _make_archimate_ref_from_mapping(mapping_data)
    assert "Grouping" in ref
    assert "intentionally ignored" in ref


def test_archimate_mapping_reference_no_ignore_note_when_empty() -> None:
    mapping_data = {
        "elements": {
            "import": {"BusinessProcess": "Prozess"},
        }
    }
    ref = _make_archimate_ref_from_mapping(mapping_data)
    assert "intentionally ignored" not in ref


# --- Motivation-Layer labels in QUERY_NODE_SCHEMA ---

def test_motivation_labels_in_node_schema() -> None:
    for label in ("Stakeholder", "Kontext", "Anforderung"):
        assert label in QUERY_NODE_SCHEMA, f"{label} missing from QUERY_NODE_SCHEMA"


def test_motivation_labels_have_required_properties() -> None:
    for label in ("Stakeholder", "Kontext", "Anforderung"):
        props = QUERY_NODE_SCHEMA[label]
        assert "name" in props
        assert "archimate_type" in props
        assert "archimate_id" in props


# --- Motivation-Layer relationship patterns ---

def test_motivation_relationship_patterns_present() -> None:
    patterns = {(p.relationship_type, p.source_label, p.target_label) for p in QUERY_RELATIONSHIP_PATTERNS}
    expected = [
        ("REALISIERT", "Anforderung", "Ziel"),
        ("BEEINFLUSST", "Kontext", "Ziel"),
        ("BEEINFLUSST", "Kontext", "Anforderung"),
        ("BEEINFLUSST", "Anforderung", "Prozess"),
        ("BEEINFLUSST", "Anforderung", "Anwendung"),
        ("BEEINFLUSST", "Anforderung", "Schnittstelle"),
        ("BEEINFLUSST", "Anforderung", "Server"),
        ("IST_VERBUNDEN_MIT", "Stakeholder", "Ziel"),
        ("IST_VERBUNDEN_MIT", "Stakeholder", "Anforderung"),
        ("IST_VERBUNDEN_MIT", "Stakeholder", "Prozess"),
        ("IST_VERBUNDEN_MIT", "Stakeholder", "Anwendung"),
    ]
    for pattern in expected:
        assert pattern in patterns, f"Pattern {pattern} missing from QUERY_RELATIONSHIP_PATTERNS"


def test_motivation_labels_in_schema_reference() -> None:
    ref = build_query_schema_reference()
    for label in ("Stakeholder", "Kontext", "Anforderung"):
        assert label in ref, f"{label} missing from schema reference"


# --- Validator: motivation labels and relations accepted ---

def test_validator_accepts_anforderung_label() -> None:
    validate_query_schema("MATCH (a:Anforderung)-[:REALISIERT]->(z:Ziel) RETURN a.name, z.name")


def test_validator_accepts_kontext_beeinflusst() -> None:
    validate_query_schema("MATCH (k:Kontext)-[:BEEINFLUSST]->(z:Ziel) RETURN k.name, z.name")


def test_validator_accepts_beeinflusst_anforderung_prozess() -> None:
    validate_query_schema("MATCH (a:Anforderung)-[:BEEINFLUSST]->(p:Prozess) RETURN a.name, p.name")


def test_validator_accepts_stakeholder_ist_verbunden_mit_ziel() -> None:
    validate_query_schema("MATCH (s:Stakeholder)-[:IST_VERBUNDEN_MIT]->(z:Ziel) RETURN s.name, z.name")


def test_validator_accepts_ist_verbunden_mit_arbitrary_labels() -> None:
    # IST_VERBUNDEN_MIT is unrestricted — any label pair is valid
    validate_query_schema("MATCH (a:Anwendung)-[:IST_VERBUNDEN_MIT]->(p:Prozess) RETURN a.name, p.name")
    validate_query_schema("MATCH (k:Kontext)-[:IST_VERBUNDEN_MIT]->(r:Risiko) RETURN k.name, r.name")


def test_validator_rejects_undirected_ist_verbunden_mit() -> None:
    with pytest.raises(ValueError, match="undirected"):
        validate_query_schema("MATCH (a:Anwendung)-[:IST_VERBUNDEN_MIT]-(p:Prozess) RETURN a.name")

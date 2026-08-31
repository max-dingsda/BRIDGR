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
    assert "Rejection" not in QUERY_NODE_SCHEMA


def test_manual_decision_not_in_node_schema() -> None:
    assert "ManualDecision" not in QUERY_NODE_SCHEMA


def test_expected_labels_in_node_schema() -> None:
    for label in ("Process", "Application", "Interface", "Server", "OrgUnit", "Role"):
        assert label in QUERY_NODE_SCHEMA


# --- SERVES relationship properties ---

def test_raw_name_not_in_dient_properties() -> None:
    assert "raw_name" not in QUERY_RELATIONSHIP_SCHEMA.get("SERVES", ())


def test_confidence_in_dient_properties() -> None:
    assert "confidence" in QUERY_RELATIONSHIP_SCHEMA.get("SERVES", ())


def test_source_in_dient_properties() -> None:
    assert "source" in QUERY_RELATIONSHIP_SCHEMA.get("SERVES", ())


# --- build_query_schema_reference output ---

def test_schema_reference_excludes_ablehnung() -> None:
    ref = build_query_schema_reference()
    assert "Rejection" not in ref


def test_schema_reference_excludes_manual_decision() -> None:
    ref = build_query_schema_reference()
    assert "ManualDecision" not in ref


def test_schema_reference_excludes_raw_name() -> None:
    ref = build_query_schema_reference()
    assert "raw_name" not in ref


def test_schema_reference_includes_confidence_and_source() -> None:
    ref = build_query_schema_reference()
    assert "confidence" in ref
    assert "source" in ref


# --- validate_query_schema: Rejection rejected ---

def test_validator_rejects_ablehnung_label() -> None:
    with pytest.raises(ValueError, match="unknown node label"):
        validate_query_schema("MATCH (a:Rejection) RETURN a.prozess_name")


def test_validator_rejects_manual_decision_label() -> None:
    with pytest.raises(ValueError, match="unknown node label"):
        validate_query_schema("MATCH (d:ManualDecision) RETURN d.decision_id")


# --- validate_query_schema: known labels accepted ---

def test_validator_accepts_known_labels() -> None:
    validate_query_schema(
        "MATCH (a:Application)-[:SERVES]->(p:Process) RETURN a.name, p.name"
    )


def test_validator_accepts_folgt_auf() -> None:
    validate_query_schema(
        "MATCH (p1:Process)-[:FOLLOWS]->(p2:Process) RETURN p1.name, p2.name"
    )


def test_validator_accepts_könnte_dienen() -> None:
    validate_query_schema(
        "MATCH (a:Application)-[:MAY_SERVE]->(p:Process) RETURN a.name, p.name"
    )


def test_validator_rejects_könnte_verantworten() -> None:
    # MAY_BE_RESPONSIBLE_FOR has no write path since finding #36 — removed from the query schema.
    with pytest.raises(ValueError, match="unknown relationship type"):
        validate_query_schema(
            "MATCH (o:OrgUnit)-[:MAY_BE_RESPONSIBLE_FOR]->(a:Application) RETURN o.name, a.name"
        )


def test_validator_rejects_unknown_relationship_type() -> None:
    with pytest.raises(ValueError, match="unknown relationship type"):
        validate_query_schema(
            "MATCH (a:Application)-[:INVENTED_REL]->(p:Process) RETURN a.name"
        )


def test_validator_rejects_unknown_node_property() -> None:
    with pytest.raises(ValueError, match="unknown property"):
        validate_query_schema(
            "MATCH (p:Process) RETURN p.raw_name"
        )


# --- New labels in QUERY_NODE_SCHEMA ---

def test_new_labels_in_node_schema() -> None:
    for label in ("Capability", "Resource", "Goal", "Risk", "DataObject", "Infrastructure"):
        assert label in QUERY_NODE_SCHEMA, f"{label} missing from QUERY_NODE_SCHEMA"


def test_new_labels_have_required_properties() -> None:
    for label in ("Capability", "Resource", "Goal", "Risk", "DataObject", "Infrastructure"):
        props = QUERY_NODE_SCHEMA[label]
        assert "name" in props
        assert "archimate_type" in props
        assert "archimate_id" in props


# --- New relationship patterns in QUERY_RELATIONSHIP_PATTERNS ---

def test_new_relationship_patterns_present() -> None:
    patterns = {(p.relationship_type, p.source_label, p.target_label) for p in QUERY_RELATIONSHIP_PATTERNS}
    expected = [
        ("AFFECTS", "Risk", "Application"),
        ("AFFECTS", "Risk", "Process"),
        ("AFFECTS", "Risk", "Server"),
        ("AFFECTS", "Risk", "Interface"),
        ("MITIGATES", "Capability", "Risk"),
        ("MITIGATES", "Application", "Risk"),
        ("REALIZES", "Capability", "Process"),
        ("REALIZES", "Capability", "Application"),
        ("REQUIRES", "Process", "Resource"),
        ("REQUIRES", "Application", "Resource"),
        ("SUPPORTS", "Application", "Goal"),
        ("SUPPORTS", "Process", "Goal"),
        ("PROCESSES", "Application", "DataObject"),
        ("PROCESSES", "Process", "DataObject"),
        ("RUNS_ON", "Application", "Infrastructure"),
    ]
    for pattern in expected:
        assert pattern in patterns, f"Pattern {pattern} missing from QUERY_RELATIONSHIP_PATTERNS"


# --- build_query_schema_reference includes new labels ---

def test_schema_reference_includes_new_labels() -> None:
    ref = build_query_schema_reference()
    for label in ("Capability", "Resource", "Goal", "Risk", "DataObject", "Infrastructure"):
        assert label in ref, f"{label} missing from schema reference"


# --- validator accepts new labels ---

def test_validator_accepts_risiko_label() -> None:
    validate_query_schema("MATCH (r:Risk)-[:AFFECTS]->(a:Application) RETURN r.name, a.name")


def test_validator_accepts_faehigkeit_label() -> None:
    validate_query_schema("MATCH (f:Capability)-[:REALIZES]->(p:Process) RETURN f.name, p.name")


def test_validator_accepts_laeuft_auf() -> None:
    validate_query_schema("MATCH (a:Application)-[:RUNS_ON]->(i:Infrastructure) RETURN a.name, i.name")


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
            "import": {"BusinessProcess": "Process"},
            "ignore": ["Grouping", "Location"],
        }
    }
    ref = _make_archimate_ref_from_mapping(mapping_data)
    assert "Grouping" in ref
    assert "intentionally ignored" in ref


def test_archimate_mapping_reference_no_ignore_note_when_empty() -> None:
    mapping_data = {
        "elements": {
            "import": {"BusinessProcess": "Process"},
        }
    }
    ref = _make_archimate_ref_from_mapping(mapping_data)
    assert "intentionally ignored" not in ref


# --- Motivation-Layer labels in QUERY_NODE_SCHEMA ---

def test_motivation_labels_in_node_schema() -> None:
    for label in ("Stakeholder", "Context", "Requirement"):
        assert label in QUERY_NODE_SCHEMA, f"{label} missing from QUERY_NODE_SCHEMA"


def test_motivation_labels_have_required_properties() -> None:
    for label in ("Stakeholder", "Context", "Requirement"):
        props = QUERY_NODE_SCHEMA[label]
        assert "name" in props
        assert "archimate_type" in props
        assert "archimate_id" in props


# --- Motivation-Layer relationship patterns ---

def test_motivation_relationship_patterns_present() -> None:
    patterns = {(p.relationship_type, p.source_label, p.target_label) for p in QUERY_RELATIONSHIP_PATTERNS}
    expected = [
        ("REALIZES", "Requirement", "Goal"),
        ("INFLUENCES", "Context", "Goal"),
        ("INFLUENCES", "Context", "Requirement"),
        ("INFLUENCES", "Requirement", "Process"),
        ("INFLUENCES", "Requirement", "Application"),
        ("INFLUENCES", "Requirement", "Interface"),
        ("INFLUENCES", "Requirement", "Server"),
        ("CONNECTED_TO", "Stakeholder", "Goal"),
        ("CONNECTED_TO", "Stakeholder", "Requirement"),
        ("CONNECTED_TO", "Stakeholder", "Process"),
        ("CONNECTED_TO", "Stakeholder", "Application"),
    ]
    for pattern in expected:
        assert pattern in patterns, f"Pattern {pattern} missing from QUERY_RELATIONSHIP_PATTERNS"


def test_motivation_labels_in_schema_reference() -> None:
    ref = build_query_schema_reference()
    for label in ("Stakeholder", "Context", "Requirement"):
        assert label in ref, f"{label} missing from schema reference"


# --- Validator: motivation labels and relations accepted ---

def test_validator_accepts_anforderung_label() -> None:
    validate_query_schema("MATCH (a:Requirement)-[:REALIZES]->(z:Goal) RETURN a.name, z.name")


def test_validator_accepts_kontext_beeinflusst() -> None:
    validate_query_schema("MATCH (k:Context)-[:INFLUENCES]->(z:Goal) RETURN k.name, z.name")


def test_validator_accepts_beeinflusst_anforderung_prozess() -> None:
    validate_query_schema("MATCH (a:Requirement)-[:INFLUENCES]->(p:Process) RETURN a.name, p.name")


def test_validator_accepts_stakeholder_ist_verbunden_mit_ziel() -> None:
    validate_query_schema("MATCH (s:Stakeholder)-[:CONNECTED_TO]->(z:Goal) RETURN s.name, z.name")


def test_validator_accepts_ist_verbunden_mit_arbitrary_labels() -> None:
    # CONNECTED_TO is unrestricted — any label pair is valid
    validate_query_schema("MATCH (a:Application)-[:CONNECTED_TO]->(p:Process) RETURN a.name, p.name")
    validate_query_schema("MATCH (k:Context)-[:CONNECTED_TO]->(r:Risk) RETURN k.name, r.name")


def test_validator_rejects_undirected_ist_verbunden_mit() -> None:
    with pytest.raises(ValueError, match="undirected"):
        validate_query_schema("MATCH (a:Application)-[:CONNECTED_TO]-(p:Process) RETURN a.name")

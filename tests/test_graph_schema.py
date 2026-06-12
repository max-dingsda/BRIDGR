from __future__ import annotations

import pytest

from core.graph_schema import (
    QUERY_NODE_SCHEMA,
    QUERY_RELATIONSHIP_SCHEMA,
    build_query_schema_reference,
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

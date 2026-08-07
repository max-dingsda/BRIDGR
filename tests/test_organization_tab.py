from types import SimpleNamespace

from ui.curation_sections import (
    _describe_manual_decision,
    _describe_manual_decision_context,
)
from ui.organization_tab import _build_role_assignment_options


def test_build_role_assignment_options_excludes_exact_matching_org_unit() -> None:
    org_units = [
        {"name": "Accounting"},
        {"name": "Auftragsbearbeitung"},
        {"name": "Controlling"},
    ]

    existing_org_unit_names, suggested_new_org_name = _build_role_assignment_options(org_units, "Auftragsbearbeitung")

    assert existing_org_unit_names == ["Accounting", "Controlling"]
    assert suggested_new_org_name == ""


def test_build_role_assignment_options_keeps_non_matching_suggestion() -> None:
    org_units = [
        {"name": "Accounting"},
        {"name": "Controlling"},
    ]

    existing_org_unit_names, suggested_new_org_name = _build_role_assignment_options(org_units, "Auftragsbearbeitung")

    assert existing_org_unit_names == ["Accounting", "Controlling"]
    assert suggested_new_org_name == "Auftragsbearbeitung"


def test_describe_manual_decision_maps_known_types() -> None:
    decision = SimpleNamespace(decision_type="manual_role_assignment")

    result = _describe_manual_decision(decision)

    assert result == "Manuelle Rollenzuordnung"


def test_describe_manual_decision_falls_back_to_raw_type() -> None:
    decision = SimpleNamespace(decision_type="custom_type")

    result = _describe_manual_decision(decision)

    assert result == "custom_type"


def test_describe_manual_decision_context_for_process_owner_assignment() -> None:
    decision = SimpleNamespace(
        decision_type="manual_process_owner_assignment",
        payload_json='{"process_id":"proc-42","process_name":"Reisekosten prüfen","org_unit_name":"Buchhaltung"}',
    )

    result = _describe_manual_decision_context(decision)

    assert result == "Prozess: Reisekosten prüfen | Eigentümer: Buchhaltung"


def test_describe_manual_decision_context_for_entity_merge() -> None:
    decision = SimpleNamespace(
        decision_type="entity_merge",
        payload_json='{"entity_type":"OrgUnit","source_name":"Controlling","target_name":"Buchhaltung"}',
    )

    result = _describe_manual_decision_context(decision)

    assert result == "Typ: OrgUnit | Quelle: Controlling | Ziel: Buchhaltung"

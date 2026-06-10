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

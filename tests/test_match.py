from skills.match import match_application


def test_match_application_prefers_confirmed_links() -> None:
    result = match_application(
        application_name="SAP SD",
        process_name="Auftragsabwicklung",
        cmdb_rows=[{"app_id": "1", "application_name": "SAP Sales"}],
        confirmed_links=[{"prozess": "Auftragsabwicklung", "anwendung_name": "SAP SD", "cmdb_id": "known-id"}],
        rejected_links=[],
        threshold=0.85,
        uuid_column="app_id",
        name_column="application_name",
    )

    assert result.cmdb_id == "known-id"
    assert result.source == "knowledge_base"


def test_match_application_uses_fuzzy_matching_for_close_names() -> None:
    result = match_application(
        application_name="SAP Sales",
        process_name="Auftragsabwicklung",
        cmdb_rows=[{"app_id": "1", "application_name": "SAP Sales"}],
        confirmed_links=[],
        rejected_links=[],
        threshold=0.85,
        uuid_column="app_id",
        name_column="application_name",
    )

    assert result.cmdb_id == "1"
    assert result.source == "fuzzy"


def test_match_application_respects_rejected_links() -> None:
    result = match_application(
        application_name="SAP Sales",
        process_name="Auftragsabwicklung",
        cmdb_rows=[{"app_id": "1", "application_name": "SAP Sales"}],
        confirmed_links=[],
        rejected_links=[{"prozess": "Auftragsabwicklung", "anwendung_name": "SAP Sales"}],
        threshold=0.85,
        uuid_column="app_id",
        name_column="application_name",
    )

    assert result.cmdb_id is None
    assert result.source == "rejected"

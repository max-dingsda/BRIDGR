from skills.match import match_application, match_application_candidates, normalize_name_for_matching


def test_match_application_prefers_confirmed_links() -> None:
    result = match_application(
        application_name="SAP SD",
        process_name="Auftragsabwicklung",
        cmdb_rows=[{"app_id": "1", "application_name": "SAP Sales"}],
        confirmed_links=[{"process": "Auftragsabwicklung", "anwendung_name": "SAP SD", "cmdb_id": "known-id"}],
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
    assert result.confidence == "stark"


def test_match_application_respects_rejected_links() -> None:
    result = match_application(
        application_name="SAP Sales",
        process_name="Auftragsabwicklung",
        cmdb_rows=[{"app_id": "1", "application_name": "SAP Sales"}],
        confirmed_links=[],
        rejected_links=[{"process": "Auftragsabwicklung", "anwendung_name": "SAP Sales"}],
        threshold=0.85,
        uuid_column="app_id",
        name_column="application_name",
    )

    assert result.cmdb_id is None
    assert result.source == "rejected"


def test_match_application_normalizes_interface_and_system_names() -> None:
    result = match_application(
        application_name="sellerServiceInterface (requestQuoteOp, orderOp)",
        process_name="Seller process",
        cmdb_rows=[{"app_id": "1", "application_name": "Seller Service"}],
        confirmed_links=[],
        rejected_links=[],
        threshold=0.85,
        uuid_column="app_id",
        name_column="application_name",
    )

    assert result.cmdb_id == "1"
    assert result.matched_name == "Seller Service"
    assert result.source == "fuzzy"
    assert result.confidence == "schwach"


def test_match_application_normalizes_technical_suffixes() -> None:
    result = match_application(
        application_name="Product Backlog Interface (java:com.camunda.examples.incidentmanagement.ProductBacklog)",
        process_name="Incident Management",
        cmdb_rows=[{"app_id": "1", "application_name": "Product Backlog System"}],
        confirmed_links=[],
        rejected_links=[],
        threshold=0.85,
        uuid_column="app_id",
        name_column="application_name",
    )

    assert result.cmdb_id == "1"
    assert result.matched_name == "Product Backlog System"
    assert result.confidence == "schwach"


def test_normalize_name_for_matching_reduces_technical_noise() -> None:
    normalized = normalize_name_for_matching(
        "shipperServiceInterface (requestShippingOp)"
    )

    assert normalized == "shipper service"


def test_match_application_candidates_returns_multiple_weak_candidates() -> None:
    results = match_application_candidates(
        application_name="Adobe",
        process_name="Dokumentenmanagement",
        cmdb_rows=[
            {"app_id": "1", "application_name": "Adobe Reader"},
            {"app_id": "2", "application_name": "Adobe Professional"},
        ],
        confirmed_links=[],
        rejected_links=[],
        threshold=0.85,
        uuid_column="app_id",
        name_column="application_name",
    )

    assert len(results) == 2
    assert {result.matched_name for result in results} == {"Adobe Reader", "Adobe Professional"}
    assert all(result.confidence == "schwach" for result in results)

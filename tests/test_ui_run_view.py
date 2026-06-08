from ui.ui_run_view import (
    build_duplicate_application_warnings,
    build_document_details,
    build_document_status_rows,
    build_review_rows,
    deduplicate_documents,
    filter_documents,
    summarize_org_candidate_scope,
    summarize_run,
    summarize_review_artifacts,
)


def sample_run() -> dict:
    return {
        "run_mode": "partial",
        "documents": [
            {
                "source_path": "Input/a.bpmn",
                "file_hash": "hash-a",
                "status": "processed",
                "error_message": None,
                "extracted_process": {
                    "process_name": "Auftragsabwicklung",
                    "process_id": "proc_001",
                    "org_unit": "Vertrieb",
                    "follows_after": ["Angebot"],
                    "raw_applications": [{"name": "SAP Sales", "confidence": "stark"}],
                    "applications": [{"name": "SAP Sales", "confidence": "stark"}],
                },
                "matches": [
                    {"cmdb_id": "cmdb-1", "confidence": "stark", "source": "fuzzy", "application_name": "SAP Sales", "matched_name": "SAP Sales"},
                    {"cmdb_id": "cmdb-2", "confidence": "schwach", "source": "fuzzy", "application_name": "Legacy Tool", "matched_name": "Legacy Suite"},
                    {"cmdb_id": None, "confidence": "schwach", "source": "unmatched", "application_name": "Unknown Tool", "matched_name": None},
                ],
                "review_items": [{"process_name": "Auftragsabwicklung", "application_name": "Legacy Tool", "reason": "fuzzy"}],
                "process_write_action": "inserted",
            },
            {
                "source_path": "Input/b.bpmn",
                "file_hash": "hash-b",
                "status": "error",
                "error_message": "Invalid BPMN XML",
                "extracted_process": None,
                "matches": [],
                "review_items": [],
                "process_write_action": "",
            },
        ],
    }


def test_summarize_run_counts_statuses() -> None:
    summary = summarize_run(sample_run())

    assert summary["run_mode"] == "partial"
    assert summary["documents"] == 2
    assert summary["identified_processes"] == 1
    assert summary["new_processes"] == 1
    assert summary["existing_processes"] == 0
    assert summary["errors"] == 1


def test_summarize_review_artifacts_counts_application_and_org_unit_outcomes() -> None:
    run = sample_run()
    run["documents"][0]["extracted_process"]["org_units"] = ["Vertrieb"]

    summary = summarize_review_artifacts(
        run["documents"],
        [
            {
                "candidate_name": "Sales Team",
                "normalized_name": "sales team",
                "source_paths": ["Input/a.bpmn"],
                "process_names": ["Auftragsabwicklung"],
                "role_names": ["Sales"],
                "status": "open",
                "mapped_org_unit": "",
                "first_seen": "2026-05-30",
                "last_seen": "2026-05-30",
            }
        ],
    )

    assert summary == {
        "exact_application_matches": 1,
        "review_application_matches": 2,
        "exact_org_unit_matches": 1,
        "review_org_unit_candidates": 1,
    }


def test_summarize_org_candidate_scope_separates_process_import_and_external_candidates() -> None:
    summary = summarize_org_candidate_scope(
        sample_run()["documents"],
        [
            {
                "candidate_name": "Sales Team",
                "normalized_name": "sales team",
                "source_paths": ["Input/a.bpmn"],
                "process_names": ["Auftragsabwicklung"],
                "role_names": ["Sales"],
                "status": "open",
                "mapped_org_unit": "",
                "first_seen": "2026-05-30",
                "last_seen": "2026-05-30",
            },
            {
                "candidate_name": "Finance Owner",
                "normalized_name": "finance owner",
                "source_paths": ["Input/cmdb.csv"],
                "process_names": [],
                "role_names": [],
                "status": "open",
                "mapped_org_unit": "",
                "first_seen": "2026-05-30",
                "last_seen": "2026-05-30",
            },
        ],
    )

    assert summary == {
        "scoped_open_candidates": 1,
        "external_open_candidates": 1,
    }


def test_filter_documents_filters_by_status() -> None:
    documents = filter_documents(sample_run(), ["error"])

    assert len(documents) == 1
    assert documents[0]["source_path"] == "Input/b.bpmn"


def test_build_document_status_rows_exposes_match_counts() -> None:
    rows = build_document_status_rows(sample_run()["documents"])

    assert rows[0]["matched"] == 2
    assert rows[0]["unmatched"] == 1
    assert rows[1]["error_message"] == "Invalid BPMN XML"


def test_build_review_rows_flattens_review_items() -> None:
    rows = build_review_rows(sample_run()["documents"])

    assert len(rows) == 2
    assert rows[0]["source_path"] == "Input/a.bpmn"
    assert rows[0]["prozess"] == "Auftragsabwicklung"
    assert rows[0]["anwendung_im_prozess"] == "Legacy Tool"
    assert rows[0]["anwendung_in_cmdb"] == "Legacy Suite"
    assert rows[0]["confidence"] == "schwach"
    assert rows[0]["quelle"] == "fuzzy"
    assert rows[0]["cmdb_id"] == "cmdb-2"
    assert rows[1]["source_path"] == "Input/a.bpmn"
    assert rows[1]["prozess"] == "Auftragsabwicklung"
    assert rows[1]["anwendung_im_prozess"] == "Unknown Tool"
    assert rows[1]["anwendung_in_cmdb"] == "-"
    assert rows[1]["confidence"] == "schwach"
    assert rows[1]["quelle"] == "unmatched"
    assert rows[1]["cmdb_id"] is None
    assert rows[0]["row_id"] != rows[1]["row_id"]


def test_build_document_details_includes_error_and_process_context() -> None:
    details = build_document_details(sample_run()["documents"])

    assert details[0]["process_id"] == "proc_001"
    assert details[0]["source_path"] == "Input/a.bpmn"
    assert details[0]["detail_id"]
    assert details[0]["raw_applications"][0]["name"] == "SAP Sales"
    assert details[1]["error_message"] == "Invalid BPMN XML"


def test_build_review_rows_uses_unique_ids_for_duplicate_hashes() -> None:
    run = sample_run()
    duplicate_document = {
        **run["documents"][0],
        "source_path": "Input/transformed/a_copy.bpmn",
    }
    run["documents"].append(duplicate_document)

    rows = build_review_rows(run["documents"])

    assert len(rows) == 4
    assert len({row["row_id"] for row in rows}) == 4


def test_build_document_details_uses_unique_ids_for_duplicate_hashes() -> None:
    run = sample_run()
    duplicate_document = {
        **run["documents"][0],
        "source_path": "Input/transformed/a_copy.bpmn",
    }
    run["documents"].append(duplicate_document)

    details = build_document_details(run["documents"])

    assert len(details) == 3
    assert len({detail["detail_id"] for detail in details}) == 3


def test_deduplicate_documents_removes_exact_duplicate_entries() -> None:
    run = sample_run()
    duplicate_document = dict(run["documents"][0])
    run["documents"].append(duplicate_document)

    deduplicated = deduplicate_documents(run["documents"])

    assert len(deduplicated) == 2


def test_build_duplicate_application_warnings_detects_variant_spellings() -> None:
    run = sample_run()
    run["documents"][0]["extracted_process"]["applications"] = [
        {"name": "ProductBacklog (com.camunda.examples.incidentmanagement.ProductBacklog)", "confidence": "stark"},
    ]
    run["documents"][0]["extracted_process"]["raw_applications"] = [
        {"name": "ProductBacklog (com.camunda.examples.incidentmanagement.ProductBacklog)", "confidence": "stark"},
        {"name": "com.camunda.examples.incidentmanagement.ProductBacklog (addTicketOperation)", "confidence": "stark"},
        {"name": "Mail System", "confidence": "stark"},
    ]

    warnings = build_duplicate_application_warnings(run["documents"])

    assert warnings == [
        {
            "prozess": "Auftragsabwicklung",
            "normalisiert": "product backlog",
            "varianten": [
                "ProductBacklog (com.camunda.examples.incidentmanagement.ProductBacklog)",
                "com.camunda.examples.incidentmanagement.ProductBacklog (addTicketOperation)",
            ],
        }
    ]

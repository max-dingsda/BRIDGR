from ui_run_view import (
    build_document_details,
    build_document_status_rows,
    build_review_rows,
    filter_documents,
    summarize_run,
)


def sample_run() -> dict:
    return {
        "run_mode": "delta",
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
                    "applications": [{"name": "SAP Sales", "confidence": "stark"}],
                },
                "matches": [{"cmdb_id": "cmdb-1"}, {"cmdb_id": None}],
                "review_items": [{"process_name": "Auftragsabwicklung", "application_name": "Legacy Tool", "reason": "unmatched"}],
            },
            {
                "source_path": "Input/b.bpmn",
                "file_hash": "hash-b",
                "status": "error",
                "error_message": "Invalid BPMN XML",
                "extracted_process": None,
                "matches": [],
                "review_items": [],
            },
        ],
    }


def test_summarize_run_counts_statuses() -> None:
    summary = summarize_run(sample_run())

    assert summary["run_mode"] == "delta"
    assert summary["documents"] == 2
    assert summary["processed"] == 1
    assert summary["errors"] == 1


def test_filter_documents_filters_by_status() -> None:
    documents = filter_documents(sample_run(), ["error"])

    assert len(documents) == 1
    assert documents[0]["source_path"] == "Input/b.bpmn"


def test_build_document_status_rows_exposes_match_counts() -> None:
    rows = build_document_status_rows(sample_run()["documents"])

    assert rows[0]["matched"] == 1
    assert rows[0]["unmatched"] == 1
    assert rows[1]["error_message"] == "Invalid BPMN XML"


def test_build_review_rows_flattens_review_items() -> None:
    rows = build_review_rows(sample_run()["documents"])

    assert rows == [
        {
            "source_path": "Input/a.bpmn",
            "process_name": "Auftragsabwicklung",
            "application_name": "Legacy Tool",
            "reason": "unmatched",
        }
    ]


def test_build_document_details_includes_error_and_process_context() -> None:
    details = build_document_details(sample_run()["documents"])

    assert details[0]["process_id"] == "proc_001"
    assert details[1]["error_message"] == "Invalid BPMN XML"

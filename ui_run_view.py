from __future__ import annotations


def summarize_run(latest_run: dict) -> dict[str, int | str]:
    documents = latest_run.get("documents", [])
    return {
        "run_mode": str(latest_run.get("run_mode", "-")),
        "documents": len(documents),
        "processed": sum(1 for document in documents if document.get("status") == "processed"),
        "skipped": sum(1 for document in documents if document.get("status") == "skipped_unchanged"),
        "no_matches": sum(1 for document in documents if document.get("status") == "no_matches"),
        "errors": sum(1 for document in documents if document.get("status") == "error"),
    }


def filter_documents(latest_run: dict, selected_statuses: list[str]) -> list[dict]:
    documents = latest_run.get("documents", [])
    if not selected_statuses:
        return documents
    return [document for document in documents if document.get("status") in selected_statuses]


def build_document_status_rows(documents: list[dict]) -> list[dict]:
    rows = []
    for document in documents:
        extracted_process = document.get("extracted_process") or {}
        matches = document.get("matches", [])
        rows.append(
            {
                "source_path": document.get("source_path", ""),
                "status": document.get("status", ""),
                "process_name": extracted_process.get("process_name", ""),
                "process_id": extracted_process.get("process_id", ""),
                "applications": len(extracted_process.get("applications", [])),
                "matched": sum(1 for match in matches if match.get("cmdb_id")),
                "unmatched": sum(1 for match in matches if not match.get("cmdb_id")),
                "review_items": len(document.get("review_items", [])),
                "error_message": document.get("error_message", ""),
            }
        )
    return rows


def build_review_rows(documents: list[dict]) -> list[dict]:
    review_rows = []
    for document in documents:
        for item in document.get("review_items", []):
            review_rows.append(
                {
                    "source_path": document.get("source_path", ""),
                    "process_name": item.get("process_name", ""),
                    "application_name": item.get("application_name", ""),
                    "reason": item.get("reason", ""),
                }
            )
    return review_rows


def build_document_details(documents: list[dict]) -> list[dict]:
    details = []
    for document in documents:
        extracted_process = document.get("extracted_process") or {}
        details.append(
            {
                "title": f"{document.get('status', 'unknown')}: {document.get('source_path', '')}",
                "process_name": extracted_process.get("process_name", ""),
                "process_id": extracted_process.get("process_id", ""),
                "org_unit": extracted_process.get("org_unit", ""),
                "follows_after": extracted_process.get("follows_after", []),
                "applications": extracted_process.get("applications", []),
                "matches": document.get("matches", []),
                "review_items": document.get("review_items", []),
                "error_message": document.get("error_message", ""),
                "file_hash": document.get("file_hash", ""),
            }
        )
    return details

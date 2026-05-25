from __future__ import annotations

from skills.match import normalize_name_for_matching


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
        extracted_process = document.get("extracted_process") or {}
        for index, match in enumerate(document.get("matches", [])):
            if match.get("source") == "rejected":
                continue
            if match.get("confidence") != "schwach" and match.get("cmdb_id"):
                continue
            review_rows.append(
                {
                    "row_id": f"{document.get('file_hash', '')}:{index}",
                    "source_path": document.get("source_path", ""),
                    "prozess": extracted_process.get("process_name", ""),
                    "anwendung_im_prozess": match.get("application_name", ""),
                    "anwendung_in_cmdb": match.get("matched_name", "") or "-",
                    "confidence": match.get("confidence", ""),
                    "quelle": match.get("source", ""),
                    "cmdb_id": match.get("cmdb_id"),
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
                "raw_applications": extracted_process.get("raw_applications", []),
                "applications": extracted_process.get("applications", []),
                "matches": document.get("matches", []),
                "review_items": document.get("review_items", []),
                "error_message": document.get("error_message", ""),
                "file_hash": document.get("file_hash", ""),
            }
        )
    return details


def build_duplicate_application_warnings(documents: list[dict]) -> list[dict]:
    warnings: list[dict] = []
    for document in documents:
        extracted_process = document.get("extracted_process") or {}
        process_name = extracted_process.get("process_name", "")
        grouped_names: dict[str, set[str]] = {}
        raw_applications = extracted_process.get("raw_applications") or extracted_process.get("applications", [])
        for application in raw_applications:
            application_name = application.get("name", "")
            normalized_name = normalize_name_for_matching(application_name)
            if not normalized_name:
                continue
            grouped_names.setdefault(normalized_name, set()).add(application_name)

        for normalized_name, variants in grouped_names.items():
            if len(variants) < 2:
                continue
            warnings.append(
                {
                    "prozess": process_name,
                    "normalisiert": normalized_name,
                    "varianten": sorted(variants),
                }
            )
    return warnings

from __future__ import annotations

import hashlib

from core.constants import (
    CONFIDENCE_WEAK,
    CONFIDENCE_STRONG,
    DOCUMENT_STATUS_ERROR,
    DOCUMENT_STATUS_NO_MATCHES,
    DOCUMENT_STATUS_SKIPPED_UNCHANGED,
    MATCH_SOURCE_KNOWLEDGE_BASE,
    MATCH_SOURCE_KNOWLEDGE_BASE_MANUAL,
    MATCH_SOURCE_REJECTED,
)
from skills.graph_writer import PROCESS_WRITE_ACTION_INSERTED, PROCESS_WRITE_ACTION_UPDATED
from skills.match import normalize_name_for_matching


def _stable_ui_id(*parts: object) -> str:
    material = "||".join(str(part) for part in parts)
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def summarize_run(latest_run: dict, documents: list[dict] | None = None) -> dict[str, int | str]:
    summary_documents = deduplicate_documents(documents if documents is not None else latest_run.get("documents", []))
    return {
        "run_mode": str(latest_run.get("run_mode", "-")),
        "documents": len(summary_documents),
        "identified_processes": sum(1 for document in summary_documents if document.get("extracted_process")),
        "new_processes": sum(
            1 for document in summary_documents if document.get("process_write_action") == PROCESS_WRITE_ACTION_INSERTED
        ),
        "existing_processes": sum(
            1 for document in summary_documents if document.get("process_write_action") == PROCESS_WRITE_ACTION_UPDATED
        ),
        "skipped": sum(1 for document in summary_documents if document.get("status") == DOCUMENT_STATUS_SKIPPED_UNCHANGED),
        "no_matches": sum(1 for document in summary_documents if document.get("status") == DOCUMENT_STATUS_NO_MATCHES),
        "errors": sum(1 for document in summary_documents if document.get("status") == DOCUMENT_STATUS_ERROR),
    }


def filter_documents(latest_run: dict, selected_statuses: list[str]) -> list[dict]:
    documents = deduplicate_documents(latest_run.get("documents", []))
    if not selected_statuses:
        return documents
    return [document for document in documents if document.get("status") in selected_statuses]


def deduplicate_documents(documents: list[dict]) -> list[dict]:
    deduplicated: list[dict] = []
    seen: set[tuple[str, str, str]] = set()
    for document in documents:
        dedupe_key = (
            document.get("source_path", ""),
            document.get("file_hash", ""),
            document.get("status", ""),
        )
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        deduplicated.append(document)
    return deduplicated


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
        matches = document.get("matches", [])
        strongly_matched_apps = {
            m.get("application_name")
            for m in matches
            if m.get("confidence") != CONFIDENCE_WEAK
            and m.get("cmdb_id")
            and m.get("source") != MATCH_SOURCE_REJECTED
        }
        for index, match in enumerate(matches):
            if match.get("source") == MATCH_SOURCE_REJECTED:
                continue
            if match.get("confidence") != CONFIDENCE_WEAK and match.get("cmdb_id"):
                continue
            if match.get("application_name") in strongly_matched_apps:
                continue
            review_rows.append(
                {
                    "row_id": _stable_ui_id(
                        document.get("source_path", ""),
                        document.get("file_hash", ""),
                        index,
                        match.get("application_name", ""),
                        match.get("matched_name", ""),
                        match.get("cmdb_id", ""),
                    ),
                    "source_path": document.get("source_path", ""),
                    "prozess": extracted_process.get("process_name", ""),
                    "process_id": extracted_process.get("process_id", ""),
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
    for index, document in enumerate(documents):
        extracted_process = document.get("extracted_process") or {}
        details.append(
            {
                "detail_id": _stable_ui_id(
                    document.get("source_path", ""),
                    document.get("file_hash", ""),
                    extracted_process.get("process_name", ""),
                    index,
                ),
                "title": f"{document.get('status', 'unknown')}: {document.get('source_path', '')}",
                "source_path": document.get("source_path", ""),
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


def summarize_review_artifacts(documents: list[dict], org_unit_candidates: list[dict] | None = None) -> dict[str, int]:
    scoped_process_names, scoped_source_paths = _collect_document_scope(documents)
    exact_application_matches = 0
    review_application_matches = 0
    exact_org_unit_matches = 0

    for document in documents:
        extracted_process = document.get("extracted_process") or {}
        process_name = extracted_process.get("process_name", "")
        source_path = document.get("source_path", "")
        exact_org_unit_matches += len(extracted_process.get("org_units", []))

        for match in document.get("matches", []):
            if match.get("source") == MATCH_SOURCE_REJECTED:
                continue
            has_cmdb_id = bool(match.get("cmdb_id"))
            confidence = match.get("confidence")
            source = match.get("source", "")
            is_exact_match = has_cmdb_id and (
                confidence == CONFIDENCE_STRONG
                or source in {MATCH_SOURCE_KNOWLEDGE_BASE, MATCH_SOURCE_KNOWLEDGE_BASE_MANUAL}
            )
            if is_exact_match:
                exact_application_matches += 1
                continue
            if confidence == CONFIDENCE_WEAK or not has_cmdb_id:
                review_application_matches += 1

    review_org_unit_candidates = 0
    for entry in org_unit_candidates or []:
        if entry.get("status", "open") != "open":
            continue
        candidate_process_names = set(entry.get("process_names", []))
        candidate_source_paths = set(entry.get("source_paths", []))
        if candidate_process_names & scoped_process_names or candidate_source_paths & scoped_source_paths:
            review_org_unit_candidates += 1

    return {
        "exact_application_matches": exact_application_matches,
        "review_application_matches": review_application_matches,
        "exact_org_unit_matches": exact_org_unit_matches,
        "review_org_unit_candidates": review_org_unit_candidates,
    }


def summarize_org_candidate_scope(documents: list[dict], org_unit_candidates: list[dict] | None = None) -> dict[str, int]:
    scoped_process_names, scoped_source_paths = _collect_document_scope(documents)
    scoped_open_candidates = 0
    external_open_candidates = 0

    for entry in org_unit_candidates or []:
        if entry.get("status", "open") != "open":
            continue
        candidate_process_names = set(entry.get("process_names", []))
        candidate_source_paths = set(entry.get("source_paths", []))
        if candidate_process_names & scoped_process_names or candidate_source_paths & scoped_source_paths:
            scoped_open_candidates += 1
        else:
            external_open_candidates += 1

    return {
        "scoped_open_candidates": scoped_open_candidates,
        "external_open_candidates": external_open_candidates,
    }


def _collect_document_scope(documents: list[dict]) -> tuple[set[str], set[str]]:
    scoped_process_names = set()
    scoped_source_paths = set()
    for document in documents:
        extracted_process = document.get("extracted_process") or {}
        process_name = extracted_process.get("process_name", "")
        source_path = document.get("source_path", "")
        if process_name:
            scoped_process_names.add(process_name)
        if source_path:
            scoped_source_paths.add(source_path)
    return scoped_process_names, scoped_source_paths

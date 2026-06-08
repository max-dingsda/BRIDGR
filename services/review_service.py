from __future__ import annotations

from dataclasses import asdict

from core.app_config import AppConfig, resolve_input_cmdb_path, resolve_runtime_output_path
from processing.cmdb import CmdbLoadError, load_cmdb_rows
from processing.knowledge_base import (
    clear_knowledge_base_sections,
    confirm_link,
    load_knowledge_base,
    reject_link,
    save_knowledge_base,
)
from processing.pipeline import apply_org_unit_mapping, build_manual_matches
from processing.run_artifacts import load_latest_run, write_latest_run
from services.alias_service import sync_knowledge_base_aliases
from services.runtime_service import get_session_neo4j_client
from skills.extract.extract_base import ApplicationReference, ExtractedProcess
from skills.graph_writer import GraphWriter
from skills.match import MatchResult, match_application_candidates
from skills.review import collect_review_items


def reconstruct_extracted_process(payload: dict) -> ExtractedProcess:
    return ExtractedProcess(
        process_name=payload.get("process_name", ""),
        process_id=payload.get("process_id", ""),
        org_unit=payload.get("org_unit", ""),
        roles=list(payload.get("roles", [])),
        org_units=list(payload.get("org_units", [])),
        org_unit_candidates=list(payload.get("org_unit_candidates", [])),
        follows_after=list(payload.get("follows_after", [])),
        raw_applications=[
            ApplicationReference(name=item.get("name", ""), confidence=item.get("confidence", ""))
            for item in payload.get("raw_applications", [])
        ],
        applications=[
            ApplicationReference(name=item.get("name", ""), confidence=item.get("confidence", ""))
            for item in payload.get("applications", [])
        ],
        source_path=payload.get("source_path", ""),
        process_owner_candidate=payload.get("process_owner_candidate", ""),
    )


def reconstruct_match_result(payload: dict) -> MatchResult:
    return MatchResult(
        application_name=payload.get("application_name", ""),
        cmdb_id=payload.get("cmdb_id"),
        matched_name=payload.get("matched_name"),
        confidence=payload.get("confidence", ""),
        source=payload.get("source", ""),
        score=float(payload.get("score", 0.0) or 0.0),
    )


def rerun_single_document_from_artifact(
    document: dict,
    config: AppConfig,
    cmdb_rows: list[dict[str, str]],
    knowledge_base,
) -> dict:
    extracted_process = reconstruct_extracted_process(document.get("extracted_process") or {})
    extracted_process = apply_org_unit_mapping(extracted_process, knowledge_base)
    matches: list[MatchResult] = []
    for application in extracted_process.applications:
        matches.extend(
            match_application_candidates(
                application_name=application.name,
                process_name=extracted_process.process_name,
                cmdb_rows=cmdb_rows,
                confirmed_links=knowledge_base.confirmed,
                rejected_links=knowledge_base.rejected,
                threshold=config.fuzzy_threshold,
                uuid_column=config.cmdb_uuid_column,
                name_column=config.cmdb_name_column,
            )
        )
    matches.extend(build_manual_matches(extracted_process.process_name, extracted_process.applications, knowledge_base.confirmed))
    review_items = collect_review_items(extracted_process, matches)
    graph_payload = GraphWriter().build_payload(extracted_process, matches)
    document["extracted_process"] = {
        "process_name": extracted_process.process_name,
        "process_id": extracted_process.process_id,
        "org_unit": extracted_process.org_unit,
        "roles": list(extracted_process.roles),
        "org_units": list(extracted_process.org_units),
        "org_unit_candidates": list(extracted_process.org_unit_candidates),
        "follows_after": list(extracted_process.follows_after),
        "raw_applications": [asdict(application) for application in extracted_process.raw_applications],
        "applications": [asdict(application) for application in extracted_process.applications],
        "source_path": extracted_process.source_path,
    }
    document["matches"] = [asdict(match) for match in matches]
    document["review_items"] = [asdict(review_item) for review_item in review_items]
    document["graph_payload"] = {
        "process": {
            "process_name": graph_payload.process.process_name,
            "process_id": graph_payload.process.process_id,
            "org_unit": graph_payload.process.org_unit,
            "roles": list(graph_payload.process.roles),
            "org_units": list(graph_payload.process.org_units),
            "org_unit_candidates": list(graph_payload.process.org_unit_candidates),
            "follows_after": list(graph_payload.process.follows_after),
            "raw_applications": [asdict(application) for application in graph_payload.process.raw_applications],
            "applications": [asdict(application) for application in graph_payload.process.applications],
            "source_path": graph_payload.process.source_path,
        },
        "matches": [asdict(match) for match in matches],
    }
    document["status"] = "no_matches" if not extracted_process.applications else "processed"
    return document


def persist_single_document_refresh(config: AppConfig, source_path: str, cmdb_rows: list[dict[str, str]]) -> None:
    runtime_output_path, _ = resolve_runtime_output_path(config.output_path)
    latest_run = load_latest_run(runtime_output_path)
    if latest_run is None:
        return
    knowledge_base = load_knowledge_base()
    updated_documents: list[dict] = []
    updated_document_for_graph: dict | None = None
    for document in latest_run.get("documents", []):
        if document.get("source_path") != source_path:
            updated_documents.append(document)
            continue
        refreshed_document = rerun_single_document_from_artifact(document, config, cmdb_rows, knowledge_base)
        updated_documents.append(refreshed_document)
        updated_document_for_graph = refreshed_document

    latest_run["documents"] = updated_documents
    write_latest_run(latest_run, runtime_output_path)

    if updated_document_for_graph is None:
        return

    graph_payload = updated_document_for_graph.get("graph_payload") or {}
    process_payload = graph_payload.get("process") or {}
    matches_payload = graph_payload.get("matches") or []
    process = reconstruct_extracted_process(process_payload)
    matches = [reconstruct_match_result(match_payload) for match_payload in matches_payload]
    graph_writer = GraphWriter()
    neo4j_client = get_session_neo4j_client(config)
    graph_writer.write_payload(neo4j_client, graph_writer.build_payload(process, matches))
    sync_knowledge_base_aliases(neo4j_client, knowledge_base)


def persist_latest_run_refresh(config: AppConfig, cmdb_rows: list[dict[str, str]]) -> int:
    runtime_output_path, _ = resolve_runtime_output_path(config.output_path)
    latest_run = load_latest_run(runtime_output_path)
    if latest_run is None:
        return 0

    knowledge_base = load_knowledge_base()
    updated_documents: list[dict] = []
    graph_writer = GraphWriter()
    neo4j_client = get_session_neo4j_client(config)
    refreshed_count = 0

    for document in latest_run.get("documents", []):
        refreshed_document = rerun_single_document_from_artifact(document, config, cmdb_rows, knowledge_base)
        updated_documents.append(refreshed_document)

        graph_payload = refreshed_document.get("graph_payload") or {}
        process_payload = graph_payload.get("process") or {}
        matches_payload = graph_payload.get("matches") or []
        process = reconstruct_extracted_process(process_payload)
        matches = [reconstruct_match_result(match_payload) for match_payload in matches_payload]
        graph_writer.write_payload(neo4j_client, graph_writer.build_payload(process, matches))
        refreshed_count += 1

    latest_run["documents"] = updated_documents
    write_latest_run(latest_run, runtime_output_path)
    sync_knowledge_base_aliases(neo4j_client, knowledge_base)
    return refreshed_count


def confirm_review_link(
    config: AppConfig,
    process_name: str,
    application_name: str,
    cmdb_id: str,
    matched_name: str,
    source_path: str,
    cmdb_rows: list[dict[str, str]],
) -> str:
    knowledge_base = load_knowledge_base()
    updated_kb = confirm_link(
        knowledge_base,
        process_name=process_name,
        application_name=application_name,
        cmdb_id=cmdb_id,
        matched_name=matched_name or application_name,
        source="manuell_bestaetigt",
    )
    save_knowledge_base(updated_kb)
    persist_single_document_refresh(config, source_path, cmdb_rows)
    return f"Link fuer '{application_name}' bestaetigt."


def reject_review_link(
    config: AppConfig,
    process_name: str,
    application_name: str,
    cmdb_id: str | None,
    source_path: str,
    cmdb_rows: list[dict[str, str]],
) -> str:
    knowledge_base = load_knowledge_base()
    updated_kb = reject_link(
        knowledge_base,
        process_name=process_name,
        application_name=application_name,
        cmdb_id=cmdb_id,
    )
    save_knowledge_base(updated_kb)
    persist_single_document_refresh(config, source_path, cmdb_rows)
    return f"Link fuer '{application_name}' abgelehnt."


def save_manual_link(
    config: AppConfig,
    process_name: str,
    application_name: str,
    cmdb_id: str,
    matched_name: str,
    source_path: str,
    cmdb_rows: list[dict[str, str]],
) -> str:
    knowledge_base = load_knowledge_base()
    updated_kb = confirm_link(
        knowledge_base,
        process_name=process_name,
        application_name=application_name,
        cmdb_id=cmdb_id,
        matched_name=matched_name or application_name,
        source="manueller_link",
    )
    save_knowledge_base(updated_kb)
    persist_single_document_refresh(config, source_path, cmdb_rows)
    return f"Manueller Link fuer '{application_name}' gespeichert."


def clear_knowledge_base_and_refresh(config: AppConfig, sections: set[str], success_message: str) -> tuple[str, str]:
    knowledge_base = load_knowledge_base()
    updated_kb = clear_knowledge_base_sections(knowledge_base, sections)
    save_knowledge_base(updated_kb)
    try:
        sync_knowledge_base_aliases(get_session_neo4j_client(config), updated_kb)
    except Exception as exc:
        return "warning", f"{success_message} Die Alias-Synchronisation nach Neo4j ist fehlgeschlagen: {exc}"

    try:
        cmdb_rows = load_cmdb_rows(
            resolve_input_cmdb_path(config),
            config.cmdb_uuid_column,
            config.cmdb_name_column,
        )
    except CmdbLoadError as exc:
        return "warning", f"{success_message} Die Aktualisierung des letzten Laufs ist fehlgeschlagen: {exc}"

    try:
        refreshed_count = persist_latest_run_refresh(config, cmdb_rows)
    except Exception as exc:
        return "warning", f"{success_message} Die Aktualisierung des letzten Laufs ist fehlgeschlagen: {exc}"

    if refreshed_count:
        return "success", f"{success_message} {refreshed_count} Dokument(e) aus dem letzten Lauf wurden neu bewertet."
    return "success", success_message

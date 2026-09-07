from __future__ import annotations

from collections.abc import Callable
from dataclasses import asdict, dataclass
from pathlib import Path
from uuid import uuid4

from core.app_config import AppConfig, resolve_project_path, resolve_runtime_output_path
from services.cmdb_service import load_application_cmdb_rows
from core.constants import (
    CONFIDENCE_STRONG,
    DOCUMENT_STATUS_ERROR,
    DOCUMENT_STATUS_NO_MATCHES,
    DOCUMENT_STATUS_PROCESSED,
    DOCUMENT_STATUS_SKIPPED_UNCHANGED,
    MATCH_SOURCE_KNOWLEDGE_BASE_MANUAL,
)
from core.debug_utils import write_debug_log
from processing.import_utils import list_process_files
from core.llm_client import LlmClientConfig, OpenAICompatibleClient
from core.neo4j_utils import Neo4jClient, Neo4jConfig, Neo4jConnectionError
from processing.run_artifacts import (
    DocumentState,
    ImportState,
    compute_file_hash,
    load_import_state,
    save_import_state,
    write_latest_run,
)
from skills.extract.extract_base import ExtractedProcess, Extractor
from skills.extract.extract_bpmn import BpmnExtractor, BpmnExtractorError
from skills.extract.extract_docx import DocxExtractor, DocxExtractorError
from skills.extract.extract_pdf import PdfExtractor, PdfExtractorError
from skills.extract.extract_txt import TextExtractor, TextExtractorError
from skills.graph_writer import GraphWritePayload, GraphWriter, normalize_org_unit_name
from skills.match import ConfirmedLink, MatchResult, match_application_candidates, decision_matches_process, confirmed_match_source
from core.org_resolution import resolve_organization
from skills.review import ReviewItem, collect_review_items
from services.cmdb_service import sync_cmdb_to_neo4j
from services.snapshot_service import create_snapshot


@dataclass(slots=True)
class DocumentRunResult:
    source_path: str
    file_hash: str
    status: str
    extracted_process: ExtractedProcess | None
    matches: list[MatchResult]
    review_items: list[ReviewItem]
    graph_payload: GraphWritePayload | None
    process_write_action: str = ""
    error_message: str | None = None


@dataclass(slots=True)
class PipelineRunResult:
    run_mode: str
    output_path: str
    used_output_fallback: bool
    documents: list[DocumentRunResult]
    run_id: str = ""


def run_pipeline(
    config: AppConfig,
    input_paths: list[Path] | None = None,
    progress_callback: Callable[[dict], None] | None = None,
) -> PipelineRunResult:
    from types import SimpleNamespace

    output_path, used_output_fallback = resolve_runtime_output_path(config.output_path)
    cmdb_rows = load_application_cmdb_rows(config)
    candidate_paths = (list(input_paths) if input_paths is not None else
                       list_bpmn_files(resolve_project_path(config.input_path)) if config.last_run_mode == "full" else [])
    total = len(candidate_paths)
    if progress_callback:
        progress_callback({"phase": "start", "completed": 0, "total": total, "source_path": "", "status": ""})
    llm_client = OpenAICompatibleClient(LlmClientConfig(
        base_url=config.llm_base_url, model=config.llm_model, api_key_env=config.llm_api_key_env,
        timeout_seconds=config.llm_timeout_seconds,
        debug_logger=lambda event, details: write_debug_log(config, event, details),
    ))
    writer = GraphWriter()
    # All extraction/LLM work precedes the write lock and database transactions.
    prepared = [run_document(path, compute_file_hash(path), build_extractor_for_path(path, llm_client),
                             config, cmdb_rows, writer) for path in candidate_paths]
    client = build_neo4j_client(config)
    completed = []
    states = []
    result = PipelineRunResult(run_mode=config.last_run_mode, output_path=str(output_path),
                               used_output_fallback=used_output_fallback, documents=completed, run_id=uuid4().hex)
    def checkpoint(status):
        save_import_state(ImportState(documents=states), output_path, client)
        write_latest_run({"run_id": result.run_id, "run_mode": result.run_mode, "output_path": result.output_path,
                          "used_output_fallback": used_output_fallback, "status": status,
                          "documents": [asdict(document) for document in completed]}, output_path, client)
    try:
        with client.serialized_writes():
            create_snapshot(config, client, trigger="pipeline", operation="process_import")
            sync_cmdb_to_neo4j(config, client)
            for index, document in enumerate(prepared, start=1):
                with client.transaction():
                    process = document.extracted_process
                    if process is not None:
                        # Match again against current decisions after acquiring the write lock.
                        document = run_document(
                            Path(document.source_path), document.file_hash,
                            SimpleNamespace(extract=lambda _path: process), config, cmdb_rows, writer,
                            writer.get_confirmed_links_from_neo4j(client),
                            writer.get_rejected_decisions_from_neo4j(client),
                            writer.load_org_units_from_neo4j(client), writer.load_org_unit_aliases_from_neo4j(client),
                        )
                        update_organization_knowledge(writer, client, document.extracted_process)
                        document.process_write_action = writer.write_payload(client, document.graph_payload)
                    completed.append(document)
                    states.append(DocumentState(source_path=document.source_path, file_hash=document.file_hash,
                                                process_id=process.process_id if process else ""))
                    checkpoint("in_progress")
                if progress_callback:
                    progress_callback({"phase": "document", "completed": index, "total": total,
                                       "source_path": document.source_path, "status": document.status})
            with client.transaction():
                writer.cleanup_process_placeholders(client)
                checkpoint("complete")
        if progress_callback:
            progress_callback({"phase": "done", "completed": total, "total": total, "source_path": "", "status": ""})
        return result
    finally:
        client.close()


def list_bpmn_files(root_path: Path) -> list[Path]:
    return list_process_files(root_path)


def build_extractor_for_path(source_path: Path, llm_client: OpenAICompatibleClient) -> Extractor:
    suffix = source_path.suffix.lower()
    if suffix in {".bpmn", ".xml"}:
        return BpmnExtractor(
            prompt_path=resolve_project_path("prompts/extract_bpmn.md"),
            llm_client=llm_client,
        )
    if suffix == ".txt":
        return TextExtractor(
            prompt_path=resolve_project_path("prompts/extract_generic.md"),
            llm_client=llm_client,
        )
    if suffix == ".docx":
        return DocxExtractor(
            prompt_path=resolve_project_path("prompts/extract_generic.md"),
            llm_client=llm_client,
        )
    if suffix == ".pdf":
        return PdfExtractor(
            prompt_path=resolve_project_path("prompts/extract_generic.md"),
            llm_client=llm_client,
        )
    raise ValueError(f"Unsupported process document format: {source_path.suffix}")


def run_document(
    source_path: Path,
    file_hash: str,
    extractor: Extractor,
    config: AppConfig,
    cmdb_rows: list[dict[str, str]],
    graph_writer: GraphWriter,
    confirmed_links: list[dict] | None = None,
    rejected_links: list[dict] | None = None,
    org_units: dict[str, str] | None = None,
    org_unit_aliases: dict[str, str] | None = None,
) -> DocumentRunResult:
    confirmed_links = confirmed_links if confirmed_links is not None else []
    rejected_links = rejected_links if rejected_links is not None else []
    org_units = org_units if org_units is not None else {}
    org_unit_aliases = org_unit_aliases if org_unit_aliases is not None else {}
    try:
        extracted_process = extractor.extract(source_path)
        extracted_process = apply_org_unit_mapping(extracted_process, org_units, org_unit_aliases)
    except (BpmnExtractorError, TextExtractorError, DocxExtractorError, PdfExtractorError) as exc:
        return DocumentRunResult(
            source_path=str(source_path),
            file_hash=file_hash,
            status=DOCUMENT_STATUS_ERROR,
            extracted_process=None,
            matches=[],
            review_items=[],
            graph_payload=None,
            error_message=str(exc),
        )

    matches: list[MatchResult] = []
    for application in extracted_process.applications:
        matches.extend(
            match_application_candidates(
                application_name=application.name,
                process_name=extracted_process.process_name,
                process_id=extracted_process.process_id,
                cmdb_rows=cmdb_rows,
                confirmed_links=confirmed_links,
                rejected_links=rejected_links,
                threshold=config.fuzzy_threshold,
                uuid_column=config.cmdb_uuid_column,
                name_column=config.cmdb_name_column,
            )
        )
    matches.extend(build_manual_matches(extracted_process.process_name, extracted_process.applications, confirmed_links, extracted_process.process_id))
    review_items = collect_review_items(extracted_process, matches)
    graph_payload = graph_writer.build_payload(extracted_process, matches)
    status = DOCUMENT_STATUS_NO_MATCHES if not extracted_process.applications else DOCUMENT_STATUS_PROCESSED
    return DocumentRunResult(
        source_path=str(source_path),
        file_hash=file_hash,
        status=status,
        extracted_process=extracted_process,
        matches=matches,
        review_items=review_items,
        graph_payload=graph_payload,
    )


def should_skip_file(
    run_mode: str,
    explicit_input_paths: list[Path] | None,
    source_path: Path,
    file_hash: str,
    previous_hashes: dict[str, str],
) -> bool:
    if explicit_input_paths is not None:
        return False
    return False


_PERSISTENT_LINK_SOURCES = {"manueller_link", "manuell_bestaetigt"}


def build_manual_matches(
    process_name: str,
    extracted_applications: list,
    confirmed_links: list[ConfirmedLink],
    process_id: str = "",
) -> list[MatchResult]:
    """Reconstruct confirmed links that survive re-import regardless of document content.

    Both manueller_link (manual links) and manuell_bestaetigt (user-confirmed weak candidates)
    are treated as persistent: they are recreated even when the raw application name is no
    longer mentioned in the current version of the document.
    """
    extracted_names = {application.name for application in extracted_applications}
    manual_matches: list[MatchResult] = []
    for link in confirmed_links:
        if not decision_matches_process(link, process_name, process_id):
            continue
        if link.get("quelle") not in _PERSISTENT_LINK_SOURCES:
            continue
        application_name = link.get("anwendung_name", "")
        if application_name in extracted_names:
            continue
        manual_matches.append(
            MatchResult(
                application_name=application_name,
                cmdb_id=link.get("cmdb_id"),
                matched_name=link.get("resolved_to", application_name),
                confidence=CONFIDENCE_STRONG,
                source=confirmed_match_source(link),
            )
        )
    return manual_matches


def apply_org_unit_mapping(
    extracted_process: ExtractedProcess,
    org_units: dict[str, str],
    org_unit_aliases: dict[str, str],
) -> ExtractedProcess:
    matched_org_units = resolve_org_units(extracted_process, org_units, org_unit_aliases)
    filtered_candidates = [
        candidate_name
        for candidate_name in extracted_process.org_unit_candidates
        if not _resolve_org_unit_name(candidate_name, org_units, org_unit_aliases)
    ]
    resolved_owner_candidate = _resolve_org_unit_name(
        extracted_process.process_owner_candidate,
        org_units,
        org_unit_aliases,
    )
    return ExtractedProcess(
        process_name=extracted_process.process_name,
        process_id=extracted_process.process_id,
        org_unit=matched_org_units[0] if len(matched_org_units) == 1 else "",
        roles=list(extracted_process.roles),
        org_units=matched_org_units,
        org_unit_candidates=filtered_candidates,
        follows_after=list(extracted_process.follows_after),
        raw_applications=list(extracted_process.raw_applications),
        applications=list(extracted_process.applications),
        source_path=extracted_process.source_path,
        process_owner_candidate=resolved_owner_candidate or extracted_process.process_owner_candidate,
    )


def resolve_org_units(
    extracted_process: ExtractedProcess,
    org_units: dict[str, str],
    org_unit_aliases: dict[str, str],
) -> list[str]:
    """Resolve role and candidate names to canonical OrgUnit names.

    org_units: {normalized_name: canonical_name} loaded from Neo4j OrgUnit nodes.
    org_unit_aliases: {normalized_alias: canonical_org_unit_name} loaded from Neo4j Alias nodes.
    """
    resolved_org_units: list[str] = []
    for role_name in extracted_process.roles:
        normalized_role = normalize_org_unit_name(role_name)
        matched_name = org_units.get(normalized_role)
        if not matched_name or matched_name in resolved_org_units:
            continue
        resolved_org_units.append(matched_name)

    for candidate_name in extracted_process.org_unit_candidates:
        mapped_name = _resolve_org_unit_name(candidate_name, org_units, org_unit_aliases)
        if not mapped_name or mapped_name in resolved_org_units:
            continue
        resolved_org_units.append(mapped_name)
    return resolved_org_units


def _resolve_org_unit_name(
    raw_name: str,
    org_units: dict[str, str],
    org_unit_aliases: dict[str, str],
) -> str:
    normalized_name = normalize_org_unit_name(raw_name)
    if not normalized_name:
        return ""
    return resolve_organization(raw_name, org_units, org_unit_aliases).name


def update_organization_knowledge(
    graph_writer: GraphWriter,
    neo4j_client: Neo4jClient,
    extracted_process: ExtractedProcess,
) -> None:
    primary_role = extracted_process.roles[0] if extracted_process.roles else ""
    for candidate_name in extracted_process.org_unit_candidates:
        graph_writer.upsert_org_unit_candidate(
            neo4j_client,
            candidate_name=candidate_name,
            source_path=extracted_process.source_path,
            process_name=extracted_process.process_name,
            role_name=primary_role,
        )


def build_neo4j_client(config: AppConfig) -> Neo4jClient:
    if not config.neo4j_password:
        raise Neo4jConnectionError("Neo4j password is not configured.")
    return Neo4jClient(
        Neo4jConfig(
            url=config.neo4j_url,
            user=config.neo4j_user,
            password=config.neo4j_password,
            database=config.neo4j_database,
        )
    )

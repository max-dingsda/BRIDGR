from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path

from app_config import AppConfig, resolve_project_path, resolve_runtime_output_path
from cmdb import load_cmdb_rows
from import_utils import list_process_files
from knowledge_base import KnowledgeBase, load_knowledge_base
from llm_client import LlmClientConfig, OpenAICompatibleClient
from run_artifacts import (
    DocumentState,
    ImportState,
    compute_file_hash,
    load_import_state,
    save_import_state,
    write_latest_run,
)
from skills.extract.extract_base import ExtractedProcess
from skills.extract.extract_bpmn import BpmnExtractor, BpmnExtractorError
from skills.graph_writer import GraphWritePayload, GraphWriter
from skills.match import MatchResult, match_application
from skills.review import ReviewItem, collect_review_items


@dataclass(slots=True)
class DocumentRunResult:
    source_path: str
    file_hash: str
    status: str
    extracted_process: ExtractedProcess | None
    matches: list[MatchResult]
    review_items: list[ReviewItem]
    graph_payload: GraphWritePayload | None
    error_message: str | None = None


@dataclass(slots=True)
class PipelineRunResult:
    run_mode: str
    output_path: str
    used_output_fallback: bool
    documents: list[DocumentRunResult]


def run_pipeline(config: AppConfig, input_paths: list[Path] | None = None) -> PipelineRunResult:
    output_path, used_output_fallback = resolve_runtime_output_path(config.output_path)
    knowledge_base = load_knowledge_base()
    cmdb_rows = load_cmdb_rows(resolve_project_path(config.cmdb_path))
    import_state = load_import_state(output_path)
    previous_hashes = {document.source_path: document.file_hash for document in import_state.documents}
    llm_client = OpenAICompatibleClient(
        LlmClientConfig(
            base_url=config.llm_base_url,
            model=config.llm_model,
            api_key_env=config.llm_api_key_env,
        )
    )
    extractor = BpmnExtractor(prompt_path=resolve_project_path("prompts/extract_bpmn.md"), llm_client=llm_client)
    graph_writer = GraphWriter()

    candidate_paths = input_paths or list_bpmn_files(resolve_project_path(config.process_input_path))
    document_results = []
    next_state_documents: list[DocumentState] = []
    for path in candidate_paths:
        file_hash = compute_file_hash(path)
        if should_skip_file(config.last_run_mode, input_paths, path, file_hash, previous_hashes):
            document_results.append(
                DocumentRunResult(
                    source_path=str(path),
                    file_hash=file_hash,
                    status="skipped_unchanged",
                    extracted_process=None,
                    matches=[],
                    review_items=[],
                    graph_payload=None,
                )
            )
            next_state_documents.append(
                DocumentState(source_path=str(path), file_hash=file_hash, process_id="")
            )
            continue

        document_result = run_document(path, file_hash, extractor, config, knowledge_base, cmdb_rows, graph_writer)
        document_results.append(document_result)
        next_state_documents.append(
            DocumentState(
                source_path=str(path),
                file_hash=file_hash,
                process_id=document_result.extracted_process.process_id if document_result.extracted_process else "",
            )
        )

    run_result = PipelineRunResult(
        run_mode=config.last_run_mode,
        output_path=str(output_path),
        used_output_fallback=used_output_fallback,
        documents=document_results,
    )
    save_import_state(ImportState(documents=next_state_documents), output_path)
    write_latest_run(
        {
            "run_mode": run_result.run_mode,
            "output_path": run_result.output_path,
            "used_output_fallback": run_result.used_output_fallback,
            "documents": [asdict(document) for document in run_result.documents],
        },
        output_path,
    )
    return run_result


def list_bpmn_files(root_path: Path) -> list[Path]:
    return list_process_files(root_path)


def run_document(
    source_path: Path,
    file_hash: str,
    extractor: BpmnExtractor,
    config: AppConfig,
    knowledge_base: KnowledgeBase,
    cmdb_rows: list[dict[str, str]],
    graph_writer: GraphWriter,
) -> DocumentRunResult:
    try:
        extracted_process = extractor.extract(source_path)
    except BpmnExtractorError as exc:
        return DocumentRunResult(
            source_path=str(source_path),
            file_hash=file_hash,
            status="error",
            extracted_process=None,
            matches=[],
            review_items=[],
            graph_payload=None,
            error_message=str(exc),
        )

    matches = [
        match_application(
            application_name=application.name,
            process_name=extracted_process.process_name,
            cmdb_rows=cmdb_rows,
            confirmed_links=knowledge_base.confirmed,
            rejected_links=knowledge_base.rejected,
            threshold=config.fuzzy_threshold,
            uuid_column=config.cmdb_uuid_column,
            name_column=config.cmdb_name_column,
        )
        for application in extracted_process.applications
    ]
    matches.extend(build_manual_matches(extracted_process.process_name, extracted_process.applications, knowledge_base.confirmed))
    review_items = collect_review_items(extracted_process, matches)
    graph_payload = graph_writer.build_payload(extracted_process, matches)
    status = "no_matches" if not extracted_process.applications else "processed"
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
    if run_mode != "delta":
        return False
    return previous_hashes.get(str(source_path)) == file_hash


def build_manual_matches(
    process_name: str,
    extracted_applications: list,
    confirmed_links: list[dict[str, str]],
) -> list[MatchResult]:
    extracted_names = {application.name for application in extracted_applications}
    manual_matches: list[MatchResult] = []
    for link in confirmed_links:
        if link.get("prozess") != process_name:
            continue
        application_name = link.get("anwendung_name", "")
        if application_name in extracted_names:
            continue
        manual_matches.append(
            MatchResult(
                application_name=application_name,
                cmdb_id=link.get("cmdb_id"),
                matched_name=link.get("resolved_to", application_name),
                confidence="stark",
                source="knowledge_base_manual",
            )
        )
    return manual_matches

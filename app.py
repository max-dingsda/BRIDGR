from __future__ import annotations

from dataclasses import asdict
from datetime import UTC, datetime
import json
import os
from pathlib import Path
from time import perf_counter
import threading
from uuid import uuid4

import streamlit as st

from app_config import (
    AppConfig,
    is_legacy_input_path,
    load_config,
    resolve_input_cmdb_path,
    resolve_project_path,
    resolve_runtime_output_path,
    save_config,
)
from bpmn_transformer import BpmnTransformError, transform_bpmn_for_import
from cmdb import CmdbLoadError, build_cmdb_option_labels, find_cmdb_row_by_label, load_cmdb_rows
from constants import (
    DOCUMENT_STATUS_OPTIONS,
    MATCH_SOURCE_REJECTED,
)
import debug_utils
from dialog_utils import pick_directory, pick_file
from env_loader import load_env_files
from import_utils import list_cmdb_files, list_process_files, sanitize_uploaded_name, save_uploaded_file
from input_validation import validate_manual_application_name
from knowledge_base import (
    accept_org_unit_candidate_as_new,
    add_org_unit,
    clear_knowledge_base_sections,
    confirm_link,
    map_org_unit_candidate,
    load_knowledge_base,
    reject_org_unit_candidate,
    reject_link,
    save_knowledge_base,
)
from llm_client import LlmClientConfig, LlmClientError, OpenAICompatibleClient
from neo4j_utils import (
    Neo4jClient,
    Neo4jConfig,
    Neo4jConnectionError,
    Neo4jQueryError,
    QueryValidationError,
)
from pipeline import run_pipeline
from query_layer import build_natural_language_answer, generate_cypher_from_question
from run_artifacts import load_latest_run
from ui_run_view import (
    build_duplicate_application_warnings,
    build_document_details,
    build_document_status_rows,
    build_review_rows,
    filter_documents,
    summarize_run,
)

NEO4J_CLIENT_STATE_KEY = "neo4j_client"
NEO4J_CLIENT_CONFIG_STATE_KEY = "neo4j_client_config"
NEO4J_CONNECTION_STATUS_STATE_KEY = "neo4j_connection_status"
NEO4J_CONNECTION_STATUS_CONFIG_STATE_KEY = "neo4j_connection_status_config"
LLM_STATUS_STATE_KEY = "llm_status"
LLM_STATUS_CONFIG_STATE_KEY = "llm_status_config"
CHAT_MESSAGES_STATE_KEY = "chat_messages"
CHAT_PENDING_APPLICATION_OPTIONS_STATE_KEY = "chat_pending_application_options"
CHAT_PENDING_ORIGINAL_QUESTION_STATE_KEY = "chat_pending_original_question"
REVIEW_RUN_FEEDBACK_STATE_KEY = "review_run_feedback"
IMPORT_RUN_FEEDBACK_STATE_KEY = "import_run_feedback"
ACTIVE_REVIEW_RUN_ID_STATE_KEY = "active_review_run_id"
ACTIVE_IMPORT_RUN_ID_STATE_KEY = "active_import_run_id"

PIPELINE_RUN_TRACKER_LOCK = threading.Lock()
PIPELINE_RUN_TRACKER: dict[str, dict] = {}


def build_neo4j_client_key(config: AppConfig) -> tuple[str, str, str, str]:
    return (
        config.neo4j_url,
        config.neo4j_user,
        config.neo4j_password,
        config.neo4j_database,
    )


def reset_session_neo4j_client(show_warning: bool = False) -> None:
    client = st.session_state.pop(NEO4J_CLIENT_STATE_KEY, None)
    st.session_state.pop(NEO4J_CLIENT_CONFIG_STATE_KEY, None)
    if client is None:
        return
    try:
        client.close()
    except Exception as exc:
        if show_warning:
            st.warning(f"Neo4j-Client konnte nicht sauber geschlossen werden: {exc}")


def get_session_neo4j_client(config: AppConfig) -> Neo4jClient:
    if not config.neo4j_password:
        raise Neo4jConnectionError("Bitte zuerst die Neo4j-Zugangsdaten konfigurieren.")

    desired_key = build_neo4j_client_key(config)
    cached_key = st.session_state.get(NEO4J_CLIENT_CONFIG_STATE_KEY)
    cached_client = st.session_state.get(NEO4J_CLIENT_STATE_KEY)
    if cached_client is not None and cached_key == desired_key:
        return cached_client

    reset_session_neo4j_client(show_warning=True)
    client = Neo4jClient(
        Neo4jConfig(
            url=config.neo4j_url,
            user=config.neo4j_user,
            password=config.neo4j_password,
            database=config.neo4j_database,
        )
    )
    st.session_state[NEO4J_CLIENT_STATE_KEY] = client
    st.session_state[NEO4J_CLIENT_CONFIG_STATE_KEY] = desired_key
    return client


def get_neo4j_connection_status(config: AppConfig, force_refresh: bool = False) -> tuple[bool, str]:
    desired_key = build_neo4j_client_key(config)
    cached_key = st.session_state.get(NEO4J_CONNECTION_STATUS_CONFIG_STATE_KEY)
    cached_status = st.session_state.get(NEO4J_CONNECTION_STATUS_STATE_KEY)

    if not force_refresh and cached_key == desired_key and cached_status is not None:
        return cached_status

    if not config.neo4j_password:
        status = (False, "Neo4j-Verbindung nicht pruefbar: Passwort fehlt.")
    else:
        try:
            client = get_session_neo4j_client(config)
            client.execute_read("RETURN 1 AS ok")
        except (Neo4jConnectionError, Neo4jQueryError) as exc:
            status = (False, f"Neo4j nicht erreichbar: {exc}")
        else:
            database_label = config.neo4j_database or "default"
            status = (True, f"Neo4j erreichbar ({config.neo4j_url}, DB: {database_label}).")

    st.session_state[NEO4J_CONNECTION_STATUS_CONFIG_STATE_KEY] = desired_key
    st.session_state[NEO4J_CONNECTION_STATUS_STATE_KEY] = status
    return status


def get_llm_status(config: AppConfig, force_refresh: bool = False) -> tuple[str, str]:
    desired_key = (
        config.llm_base_url,
        config.llm_model,
        config.llm_api_key_env,
        config.llm_timeout_seconds,
    )
    cached_key = st.session_state.get(LLM_STATUS_CONFIG_STATE_KEY)
    cached_status = st.session_state.get(LLM_STATUS_STATE_KEY)

    if not force_refresh and cached_key == desired_key and cached_status is not None:
        return cached_status

    if not config.llm_base_url:
        status = ("error", "LLM nicht pruefbar: Base URL fehlt.")
    elif not config.llm_model:
        status = ("warning", "LLM-Endpoint erreichbar noch nicht geprueft: Modellname fehlt.")
    else:
        try:
            client = OpenAICompatibleClient(
                LlmClientConfig(
                    base_url=config.llm_base_url,
                    model=config.llm_model,
                    api_key_env=config.llm_api_key_env,
                    timeout_seconds=config.llm_timeout_seconds,
                    debug_logger=lambda event, details: write_debug_log(config, event, details),
                )
            )
            models = client.list_models()
        except LlmClientError as exc:
            status = ("error", f"LLM nicht erreichbar: {exc}")
        else:
            if config.llm_model in models:
                status = (
                    "success",
                    f"LLM erreichbar. Modell `{config.llm_model}` ist verfuegbar; der erste Aufruf kann bei Ollama trotzdem Ladezeit haben.",
                )
            else:
                available_models = ", ".join(models[:5])
                suffix = " ..." if len(models) > 5 else ""
                available_note = f" Verfuegbar: {available_models}{suffix}." if models else ""
                status = (
                    "warning",
                    f"LLM-Endpoint erreichbar, aber Modell `{config.llm_model}` ist nicht verfuegbar.{available_note}",
                )

    st.session_state[LLM_STATUS_CONFIG_STATE_KEY] = desired_key
    st.session_state[LLM_STATUS_STATE_KEY] = status
    return status


def write_debug_log(config: AppConfig, event: str, details: dict) -> None:
    original_resolver = debug_utils.resolve_runtime_output_path
    try:
        debug_utils.resolve_runtime_output_path = resolve_runtime_output_path
        debug_utils.write_debug_log(config, event, details)
    finally:
        debug_utils.resolve_runtime_output_path = original_resolver


def format_duration(seconds: float) -> str:
    total_seconds = max(0, int(round(seconds)))
    minutes, remaining_seconds = divmod(total_seconds, 60)
    hours, remaining_minutes = divmod(minutes, 60)
    if hours:
        return f"{hours}h {remaining_minutes}m {remaining_seconds}s"
    if minutes:
        return f"{minutes}m {remaining_seconds}s"
    return f"{remaining_seconds}s"


def clear_run_feedback(state_key: str) -> None:
    st.session_state.pop(state_key, None)


def render_run_feedback(state_key: str) -> None:
    feedback = st.session_state.get(state_key)
    if not feedback:
        return

    level = feedback.get("level", "info")
    message = feedback.get("message", "")
    if level == "success":
        st.success(message)
    elif level == "error":
        st.error(message)
    elif level == "warning":
        st.warning(message)
    else:
        st.info(message)


def set_run_feedback(state_key: str, level: str, message: str) -> None:
    st.session_state[state_key] = {"level": level, "message": message}


def create_pipeline_run_tracker(success_message_template: str) -> str:
    run_id = uuid4().hex
    with PIPELINE_RUN_TRACKER_LOCK:
        PIPELINE_RUN_TRACKER[run_id] = {
            "status": "running",
            "completed": 0,
            "total": 0,
            "source_path": "",
            "document_status": "",
            "duration_seconds": None,
            "error_message": "",
            "success_message_template": success_message_template,
        }
    return run_id


def update_pipeline_run_tracker(run_id: str, progress: dict) -> None:
    with PIPELINE_RUN_TRACKER_LOCK:
        tracker = PIPELINE_RUN_TRACKER.get(run_id)
        if tracker is None:
            return
        tracker["completed"] = max(0, int(progress.get("completed", 0)))
        tracker["total"] = max(0, int(progress.get("total", 0)))
        tracker["source_path"] = progress.get("source_path", "")
        tracker["document_status"] = progress.get("status", "")


def finish_pipeline_run_tracker(run_id: str, duration_seconds: float) -> None:
    with PIPELINE_RUN_TRACKER_LOCK:
        tracker = PIPELINE_RUN_TRACKER.get(run_id)
        if tracker is None:
            return
        tracker["status"] = "success"
        tracker["duration_seconds"] = duration_seconds


def fail_pipeline_run_tracker(run_id: str, error_message: str) -> None:
    with PIPELINE_RUN_TRACKER_LOCK:
        tracker = PIPELINE_RUN_TRACKER.get(run_id)
        if tracker is None:
            return
        tracker["status"] = "error"
        tracker["error_message"] = error_message


def get_pipeline_run_tracker(run_id: str) -> dict | None:
    with PIPELINE_RUN_TRACKER_LOCK:
        tracker = PIPELINE_RUN_TRACKER.get(run_id)
        if tracker is None:
            return None
        return dict(tracker)


def clear_pipeline_run_tracker(run_id: str) -> None:
    with PIPELINE_RUN_TRACKER_LOCK:
        PIPELINE_RUN_TRACKER.pop(run_id, None)


def start_async_pipeline_run(
    config: AppConfig,
    run_state_key: str,
    feedback_state_key: str,
    success_message_template: str,
    input_paths: list[Path] | None = None,
) -> None:
    clear_run_feedback(feedback_state_key)
    run_id = create_pipeline_run_tracker(success_message_template)
    st.session_state[run_state_key] = run_id
    config_copy = AppConfig(**asdict(config))
    input_paths_copy = list(input_paths) if input_paths is not None else None

    def worker() -> None:
        started_at = perf_counter()
        try:
            run_pipeline(
                config_copy,
                input_paths=input_paths_copy,
                progress_callback=lambda progress: update_pipeline_run_tracker(run_id, progress),
            )
        except Exception as exc:
            fail_pipeline_run_tracker(run_id, str(exc))
            return
        finish_pipeline_run_tracker(run_id, perf_counter() - started_at)

    threading.Thread(target=worker, daemon=True).start()


@st.fragment(run_every=1)
def render_active_pipeline_run_monitor(
    run_state_key: str,
    feedback_state_key: str,
) -> None:
    active_run_id = st.session_state.get(run_state_key)
    if not active_run_id:
        return

    tracker = get_pipeline_run_tracker(active_run_id)
    if tracker is None:
        st.session_state.pop(run_state_key, None)
        return

    status = tracker.get("status", "running")
    if status == "running":
        total = max(0, int(tracker.get("total", 0)))
        completed = max(0, int(tracker.get("completed", 0)))
        source_path = tracker.get("source_path", "")
        document_status = tracker.get("document_status", "")
        source_name = Path(source_path).name if source_path else "-"
        if total > 0:
            st.progress(min(1.0, completed / total))
            st.info(
                f"{completed} von {total} Dateien bearbeitet. Aktuell/zuletzt: `{source_name}` ({document_status or 'unbekannt'})."
            )
        else:
            st.info("Lauf gestartet. Die Anzahl der zu bearbeitenden Dateien wird ermittelt.")
        return

    st.session_state.pop(run_state_key, None)
    clear_pipeline_run_tracker(active_run_id)
    if status == "success":
        duration_seconds = float(tracker.get("duration_seconds") or 0.0)
        set_run_feedback(
            feedback_state_key,
            "success",
            str(tracker.get("success_message_template", "")).format(duration=format_duration(duration_seconds)),
        )
    else:
        set_run_feedback(feedback_state_key, "error", str(tracker.get("error_message", "Unbekannter Fehler.")))
    st.rerun()


def render_query_tab() -> None:
    st.subheader("Kommunikation")
    config = load_config(Path("config.json"))
    ensure_query_chat_defaults()
    action_column, _ = st.columns([1, 5])
    with action_column:
        if st.button("Neues Gespraech", key="chat-reset", width="stretch"):
            reset_query_chat_state()
            st.rerun()
    render_query_chat_messages()

    question = st.chat_input("Frage an den Wissensgraphen")
    if not question:
        return
    if not config.llm_model:
        st.warning("Bitte zuerst ein LLM-Modell konfigurieren.")
        return
    if not config.neo4j_password:
        st.warning("Bitte zuerst die Neo4j-Zugangsdaten konfigurieren.")
        return

    append_chat_message("user", question)
    pending_options = st.session_state.get(CHAT_PENDING_APPLICATION_OPTIONS_STATE_KEY, [])
    if pending_options:
        handle_query_clarification(question, config, pending_options)
    else:
        run_query_chat_turn(question, config)
    st.rerun()


def ensure_query_chat_defaults() -> None:
    st.session_state.setdefault(CHAT_MESSAGES_STATE_KEY, [])
    st.session_state.setdefault(CHAT_PENDING_APPLICATION_OPTIONS_STATE_KEY, [])
    st.session_state.setdefault(CHAT_PENDING_ORIGINAL_QUESTION_STATE_KEY, "")


def reset_query_chat_state() -> None:
    st.session_state[CHAT_MESSAGES_STATE_KEY] = []
    st.session_state[CHAT_PENDING_APPLICATION_OPTIONS_STATE_KEY] = []
    st.session_state[CHAT_PENDING_ORIGINAL_QUESTION_STATE_KEY] = ""


def append_chat_message(role: str, content: str, cypher_query: str = "", rows: list[dict] | None = None) -> None:
    st.session_state[CHAT_MESSAGES_STATE_KEY].append(
        {
            "role": role,
            "content": content,
            "cypher_query": cypher_query,
            "rows": rows or [],
        }
    )


def render_query_chat_messages() -> None:
    for message in st.session_state.get(CHAT_MESSAGES_STATE_KEY, []):
        with st.chat_message(message["role"]):
            st.write(message["content"])
            rows = message.get("rows", [])
            if rows:
                st.markdown("**Ergebnis**")
                st.dataframe(rows, width="stretch")
            elif message["role"] == "assistant" and message.get("cypher_query"):
                st.info("Keine Treffer gefunden.")
            if message.get("cypher_query"):
                with st.expander("Technische Details", expanded=False):
                    st.markdown("**Cypher**")
                    st.code(message["cypher_query"], language="cypher")


def handle_query_clarification(user_message: str, config: AppConfig, options: list[str]) -> None:
    from query_layer import resolve_application_clarification

    resolved_option = resolve_application_clarification(user_message, options)
    if resolved_option is None:
        append_chat_message(
            "assistant",
            "Ich konnte Ihre Praezisierung noch nicht eindeutig zuordnen. Bitte nennen Sie genau eine dieser Anwendungen: "
            + ", ".join(options),
        )
        return

    original_question = st.session_state.get(CHAT_PENDING_ORIGINAL_QUESTION_STATE_KEY, "")
    clarified_question = (
        f"{original_question}\n"
        f"Die Rueckfrage wurde so praezisiert: Gemeint ist genau die Anwendung \"{resolved_option}\"."
    )
    st.session_state[CHAT_PENDING_APPLICATION_OPTIONS_STATE_KEY] = []
    st.session_state[CHAT_PENDING_ORIGINAL_QUESTION_STATE_KEY] = ""
    run_query_chat_turn(clarified_question, config)


def run_query_chat_turn(question: str, config: AppConfig) -> None:
    from query_layer import find_application_ambiguity_options

    cypher_query = ""
    try:
        llm_client = OpenAICompatibleClient(
            LlmClientConfig(
                base_url=config.llm_base_url,
                model=config.llm_model,
                api_key_env=config.llm_api_key_env,
                timeout_seconds=config.llm_timeout_seconds,
                debug_logger=lambda event, details: write_debug_log(config, event, details),
            )
        )
        neo4j_client = get_session_neo4j_client(config)
        cypher_query = generate_cypher_from_question(
            question=question,
            llm_client=llm_client,
            prompt_path=resolve_project_path("prompts/cypher_gen.md"),
        )
        rows = neo4j_client.execute_read(cypher_query)
        answer_text = build_natural_language_answer(
            question=question,
            cypher_query=cypher_query,
            rows=rows,
            llm_client=llm_client,
            prompt_path=resolve_project_path("prompts/answer_query.md"),
        )
    except (LlmClientError, Neo4jConnectionError, Neo4jQueryError, QueryValidationError) as exc:
        write_debug_log(
            config,
            "query_error",
            {
                "question": question,
                "cypher_query": cypher_query,
                "error": str(exc),
            },
        )
        append_chat_message("assistant", str(exc), cypher_query=cypher_query)
        return

    ambiguity_options = find_application_ambiguity_options(question, rows)
    if ambiguity_options:
        st.session_state[CHAT_PENDING_APPLICATION_OPTIONS_STATE_KEY] = ambiguity_options
        st.session_state[CHAT_PENDING_ORIGINAL_QUESTION_STATE_KEY] = question
        append_chat_message(
            "assistant",
            "Ich habe mehrere passende Anwendungen gefunden: "
            + ", ".join(ambiguity_options)
            + ". Welche meinen Sie?",
            cypher_query=cypher_query,
            rows=rows,
        )
        return

    append_chat_message("assistant", answer_text, cypher_query=cypher_query, rows=rows)


def render_review_tab() -> None:
    st.subheader("Link Editing")
    config = load_config(Path("config.json"))
    render_run_feedback(REVIEW_RUN_FEEDBACK_STATE_KEY)
    render_active_pipeline_run_monitor(ACTIVE_REVIEW_RUN_ID_STATE_KEY, REVIEW_RUN_FEEDBACK_STATE_KEY)
    preview_running = bool(st.session_state.get(ACTIVE_REVIEW_RUN_ID_STATE_KEY))

    action_column, info_column = st.columns([1, 2])
    with action_column:
        if st.button("Pipeline Preview starten", key="review_preview", width="stretch", disabled=preview_running):
            if not config.llm_model:
                st.warning("Bitte zuerst ein LLM-Modell in Anwendungskonfig konfigurieren.")
            else:
                start_async_pipeline_run(
                    config,
                    run_state_key=ACTIVE_REVIEW_RUN_ID_STATE_KEY,
                    feedback_state_key=REVIEW_RUN_FEEDBACK_STATE_KEY,
                    success_message_template="Preview-Lauf abgeschlossen in {duration}. Artefakte im Output-Ordner wurden aktualisiert.",
                )
                st.rerun()
    with info_column:
        st.caption("Die Ansicht liest den letzten gespeicherten Lauf aus `Output/latest_run.json`.")

    runtime_output_path, used_output_fallback = resolve_runtime_output_path(config.output_path)
    latest_run = load_latest_run(runtime_output_path)
    if latest_run is None:
        if used_output_fallback:
            st.warning(f"Der konfigurierte Output-Pfad ist nicht beschreibbar. Laufartefakte werden nach `{runtime_output_path}` umgeleitet.")
        st.info("Noch kein gespeicherter Pipeline-Lauf vorhanden.")
        return

    if latest_run.get("used_output_fallback"):
        st.warning(f"Laufartefakte werden aktuell nach `{latest_run.get('output_path', runtime_output_path)}` geschrieben.")

    render_latest_run_summary(latest_run)
    selected_statuses = st.multiselect(
        "Statusfilter",
        options=DOCUMENT_STATUS_OPTIONS,
        default=DOCUMENT_STATUS_OPTIONS,
    )
    filtered_documents = filter_documents(latest_run, selected_statuses)
    try:
        cmdb_rows = load_cmdb_rows(
            resolve_input_cmdb_path(config),
            config.cmdb_uuid_column,
            config.cmdb_name_column,
        )
    except CmdbLoadError as exc:
        st.error(str(exc))
        return
    render_document_status_table(filtered_documents)
    render_duplicate_application_warnings(filtered_documents)
    render_review_items_table(filtered_documents, config, cmdb_rows)
    render_document_details(filtered_documents, config, cmdb_rows)
    render_knowledge_base_tools(config)


def render_latest_run_summary(latest_run: dict) -> None:
    summary = summarize_run(latest_run)

    metric_columns = st.columns(5)
    metric_columns[0].metric("Run Mode", str(summary["run_mode"]))
    metric_columns[1].metric("Documents", int(summary["documents"]))
    metric_columns[2].metric("Processed", int(summary["processed"]))
    metric_columns[3].metric("Skipped", int(summary["skipped"]))
    metric_columns[4].metric("Errors", int(summary["errors"]))
    if summary["no_matches"]:
        st.caption(f"Documents without application matches: {summary['no_matches']}")


def render_document_status_table(documents: list[dict]) -> None:
    rows = build_document_status_rows(documents)
    st.markdown("**Dokumentstatus**")
    if rows:
        st.dataframe(rows, width="stretch")
    else:
        st.info("Keine Dokumente fuer den aktuellen Filter gefunden.")


def render_review_items_table(documents: list[dict], config: AppConfig, cmdb_rows: list[dict[str, str]]) -> None:
    review_rows = build_review_rows(documents)
    st.markdown("**Review-Items**")
    if not review_rows:
        st.success("Keine Review-Items fuer den aktuellen Filter gefunden.")
        return

    header_columns = st.columns([2, 3, 3, 1, 1, 1, 2])
    header_columns[0].markdown("**Prozess**")
    header_columns[1].markdown("**Anwendung im Prozess**")
    header_columns[2].markdown("**Anwendung in der CMDB**")
    header_columns[3].markdown("**Bewertung**")
    header_columns[4].markdown("**Bestaetigen**")
    header_columns[5].markdown("**Ablehnen**")
    header_columns[6].markdown("**Manuell anlegen**")

    for review_row in review_rows:
        render_review_item_actions(review_row, config, cmdb_rows)


def render_duplicate_application_warnings(documents: list[dict]) -> None:
    warnings = build_duplicate_application_warnings(documents)
    if not warnings:
        return

    st.markdown("**Hinweise zur Prozessnotation**")
    for warning in warnings:
        variants = "; ".join(warning.get("varianten", []))
        st.warning(
            f"Im Prozess '{warning.get('prozess', '')}' scheint dieselbe Anwendung mehrfach unterschiedlich notiert zu sein: {variants}"
        )


def render_document_details(documents: list[dict], config: AppConfig, cmdb_rows: list[dict[str, str]]) -> None:
    st.markdown("**Dokumentdetails**")
    details = build_document_details(documents)
    if not details:
        st.info("Keine Detaildaten fuer den aktuellen Filter vorhanden.")
        return

    for detail in details:
        with st.expander(detail["title"]):
            left_column, right_column = st.columns(2)
            with left_column:
                st.write(
                    {
                        "process_name": detail["process_name"],
                        "process_id": detail["process_id"],
                        "org_unit": detail["org_unit"],
                        "follows_after": detail["follows_after"],
                        "file_hash": detail["file_hash"],
                    }
                )
            with right_column:
                if detail["error_message"]:
                    st.error(detail["error_message"])
                else:
                    st.write({"review_items": detail["review_items"]})

            render_review_actions(detail, config, cmdb_rows)
            render_manual_link_form(detail, config, cmdb_rows)
            with st.expander("Technische Details", expanded=False):
                st.markdown("Raw Applications")
                st.json(detail["raw_applications"])
                st.markdown("Applications")
                st.json(detail["applications"])
                st.markdown("Matches")
                st.json(detail["matches"])


def render_review_actions(detail: dict, config: AppConfig, cmdb_rows: list[dict[str, str]]) -> None:
    process_name = detail["process_name"]
    matches = detail["matches"]
    if not matches:
        return

    st.markdown("Pruefbare Verknuepfungen")
    header_columns = st.columns([2, 3, 3, 1, 1, 1])
    header_columns[0].markdown("**Prozess**")
    header_columns[1].markdown("**Anwendung im Prozess**")
    header_columns[2].markdown("**Anwendung in der CMDB**")
    header_columns[3].markdown("**Bewertung**")
    header_columns[4].markdown("**Bestaetigen**")
    header_columns[5].markdown("**Ablehnen**")

    for index, match in enumerate(matches):
        application_name = match.get("application_name", "")
        matched_name = match.get("matched_name") or ""
        cmdb_id = match.get("cmdb_id")
        source = match.get("source", "")
        confidence = match.get("confidence", "")
        if source == MATCH_SOURCE_REJECTED:
            continue

        action_columns = st.columns([2, 3, 3, 1, 1, 1])
        action_columns[0].write(process_name)
        action_columns[1].write(application_name)
        action_columns[2].write(matched_name or "-")
        action_columns[3].write(confidence)

        confirm_key = f"confirm::{detail['detail_id']}::{index}"
        reject_key = f"reject::{detail['detail_id']}::{index}"

        if cmdb_id and action_columns[4].button("Bestaetigen", key=confirm_key, width="stretch"):
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
            run_pipeline(config)
            st.success(f"Link fuer '{application_name}' bestaetigt.")
            st.rerun()

        if action_columns[5].button("Ablehnen", key=reject_key, width="stretch"):
            knowledge_base = load_knowledge_base()
            updated_kb = reject_link(
                knowledge_base,
                process_name=process_name,
                application_name=application_name,
                cmdb_id=cmdb_id,
            )
            save_knowledge_base(updated_kb)
            run_pipeline(config)
            st.success(f"Link fuer '{application_name}' abgelehnt.")
            st.rerun()


def render_review_item_actions(review_row: dict, config: AppConfig, cmdb_rows: list[dict[str, str]]) -> None:
    process_name = review_row.get("prozess", "")
    application_name = review_row.get("anwendung_im_prozess", "")
    matched_name = review_row.get("anwendung_in_cmdb", "")
    cmdb_id = review_row.get("cmdb_id")
    row_id = review_row.get("row_id", "")

    row_columns = st.columns([2, 3, 3, 1, 1, 1, 2])
    row_columns[0].write(process_name)
    row_columns[1].write(application_name)
    row_columns[2].write(matched_name)
    row_columns[3].write(review_row.get("confidence", ""))

    confirm_key = f"review-confirm::{row_id}"
    reject_key = f"review-reject::{row_id}"
    manual_select_key = f"review-manual-select::{row_id}"
    manual_submit_key = f"review-manual-submit::{row_id}"

    if cmdb_id and row_columns[4].button("Bestaetigen", key=confirm_key, width="stretch"):
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
        run_pipeline(config)
        st.success(f"Link fuer '{application_name}' bestaetigt.")
        st.rerun()

    if row_columns[5].button("Ablehnen", key=reject_key, width="stretch"):
        knowledge_base = load_knowledge_base()
        updated_kb = reject_link(
            knowledge_base,
            process_name=process_name,
            application_name=application_name,
            cmdb_id=cmdb_id,
        )
        save_knowledge_base(updated_kb)
        run_pipeline(config)
        st.success(f"Link fuer '{application_name}' abgelehnt.")
        st.rerun()

    cmdb_options = build_cmdb_option_labels(cmdb_rows, config.cmdb_uuid_column, config.cmdb_name_column)
    if not cmdb_options:
        row_columns[6].write("-")
        return

    with row_columns[6].popover("Manuell anlegen", use_container_width=True):
        selected_label = st.selectbox(
            "CMDB-Ziel",
            options=cmdb_options,
            key=manual_select_key,
            label_visibility="collapsed",
        )
        if st.button("Speichern", key=manual_submit_key, width="stretch"):
            selected_row = find_cmdb_row_by_label(
                cmdb_rows,
                selected_label,
                config.cmdb_uuid_column,
                config.cmdb_name_column,
            )
            if selected_row is None:
                st.error("Ausgewaehltes CMDB-Ziel konnte nicht aufgeloest werden.")
                return
            knowledge_base = load_knowledge_base()
            updated_kb = confirm_link(
                knowledge_base,
                process_name=process_name,
                application_name=application_name,
                cmdb_id=selected_row.get(config.cmdb_uuid_column, ""),
                matched_name=selected_row.get(config.cmdb_name_column, application_name),
                source="manueller_link",
            )
            save_knowledge_base(updated_kb)
            run_pipeline(config)
            st.success(f"Manueller Link fuer '{application_name}' gespeichert.")
            st.rerun()


def render_manual_link_form(detail: dict, config: AppConfig, cmdb_rows: list[dict[str, str]]) -> None:
    process_name = detail["process_name"]
    if not process_name:
        return

    cmdb_options = build_cmdb_option_labels(cmdb_rows, config.cmdb_uuid_column, config.cmdb_name_column)
    if not cmdb_options:
        st.info("Keine CMDB-Eintraege fuer manuellen Link verfuegbar.")
        return

    st.markdown("Manuellen Link anlegen")
    manual_name_key = f"manual-name::{detail['detail_id']}"
    manual_target_key = f"manual-target::{detail['detail_id']}"
    manual_submit_key = f"manual-submit::{detail['detail_id']}"

    manual_application_name = st.text_input(
        "Bezeichnung im Prozesskontext",
        value="",
        key=manual_name_key,
        placeholder="z.B. SAP Sales oder Vertragssystem",
    )
    selected_label = st.selectbox(
        "CMDB-Ziel",
        options=cmdb_options,
        key=manual_target_key,
    )

    if st.button("Manuellen Link speichern", key=manual_submit_key, width="stretch"):
        selected_row = find_cmdb_row_by_label(
            cmdb_rows,
            selected_label,
            config.cmdb_uuid_column,
            config.cmdb_name_column,
        )
        if selected_row is None:
            st.error("Ausgewaehltes CMDB-Ziel konnte nicht aufgeloest werden.")
            return

        if manual_application_name.strip():
            try:
                application_name = validate_manual_application_name(manual_application_name)
            except ValueError as exc:
                st.error(str(exc))
                return
        else:
            application_name = selected_row.get(config.cmdb_name_column, "")
        knowledge_base = load_knowledge_base()
        updated_kb = confirm_link(
            knowledge_base,
            process_name=process_name,
            application_name=application_name,
            cmdb_id=selected_row.get(config.cmdb_uuid_column, ""),
            matched_name=selected_row.get(config.cmdb_name_column, application_name),
            source="manueller_link",
        )
        save_knowledge_base(updated_kb)
        run_pipeline(config)
        st.success(f"Manueller Link fuer '{application_name}' gespeichert.")
        st.rerun()


def render_knowledge_base_tools(config: AppConfig) -> None:
    with st.expander("Knowledge Base verwalten", expanded=False):
        st.caption("Hilft beim Zuruecksetzen von Testentscheidungen ohne manuelles Bearbeiten von `knowledge_base/kb.json`.")
        action_columns = st.columns(3)

        if action_columns[0].button("KB komplett leeren", key="kb-clear-all", width="stretch"):
            clear_knowledge_base_and_refresh(
                config,
                sections={"confirmed", "rejected", "disambiguation", "process_identity"},
                success_message="Die gesamte Knowledge Base wurde geleert.",
            )

        if action_columns[1].button("Nur confirmed leeren", key="kb-clear-confirmed", width="stretch"):
            clear_knowledge_base_and_refresh(
                config,
                sections={"confirmed"},
                success_message="Die bestaetigten KB-Eintraege wurden geleert.",
            )

        if action_columns[2].button("Nur rejected leeren", key="kb-clear-rejected", width="stretch"):
            clear_knowledge_base_and_refresh(
                config,
                sections={"rejected"},
                success_message="Die abgelehnten KB-Eintraege wurden geleert.",
            )


def clear_knowledge_base_and_refresh(config: AppConfig, sections: set[str], success_message: str) -> None:
    knowledge_base = load_knowledge_base()
    updated_kb = clear_knowledge_base_sections(knowledge_base, sections)
    save_knowledge_base(updated_kb)
    reset_session_neo4j_client(show_warning=True)
    try:
        run_pipeline(config)
    except Exception as exc:
        st.warning(f"{success_message} Der anschliessende Pipeline-Lauf ist fehlgeschlagen: {exc}")
    else:
        st.success(f"{success_message} Die Pipeline wurde anschliessend neu ausgefuehrt.")
    st.rerun()


def render_organization_tab() -> None:
    st.subheader("Organisation")
    knowledge_base = load_knowledge_base()

    st.markdown("**Organisationseinheiten**")
    org_units = sorted(knowledge_base.org_units, key=lambda entry: entry.get("name", "").casefold())
    if org_units:
        st.dataframe(
            [
                {
                    "Name": entry.get("name", ""),
                    "Quelle": entry.get("source", ""),
                    "Angelegt am": entry.get("created_at", ""),
                }
                for entry in org_units
            ],
            width="stretch",
        )
    else:
        st.info("Noch keine Organisationseinheiten gepflegt.")

    with st.form("organization-add-form"):
        new_org_unit_name = st.text_input("Neue Organisationseinheit")
        add_submitted = st.form_submit_button("Organisationseinheit hinzufuegen")
    if add_submitted:
        updated_kb = add_org_unit(knowledge_base, new_org_unit_name, source="manual")
        save_knowledge_base(updated_kb)
        st.success("Organisationseinheit gespeichert.")
        st.rerun()

    st.markdown("**Kandidaten**")
    open_candidates = [
        entry
        for entry in knowledge_base.org_unit_candidates
        if entry.get("status", "open") == "open"
    ]
    if not open_candidates:
        st.info("Aktuell liegen keine offenen Kandidaten vor.")
    else:
        existing_org_unit_options = [entry.get("name", "") for entry in org_units if entry.get("name")]
        for candidate in sorted(open_candidates, key=lambda entry: entry.get("candidate_name", "").casefold()):
            candidate_name = candidate.get("candidate_name", "")
            candidate_key = candidate.get("normalized_name", candidate_name.casefold())
            with st.container(border=True):
                st.markdown(f"**{candidate_name}**")
                process_names = ", ".join(candidate.get("process_names", [])) or "-"
                role_names = ", ".join(candidate.get("role_names", [])) or "-"
                source_paths = ", ".join(Path(path).name for path in candidate.get("source_paths", [])) or "-"
                st.caption(f"Prozesse: {process_names}")
                st.caption(f"Rollen: {role_names}")
                st.caption(f"Quellen: {source_paths}")

                action_columns = st.columns([2, 1, 2, 1, 1])
                selected_target = action_columns[0].selectbox(
                    "Bestehende Org-Einheit",
                    options=[""] + existing_org_unit_options,
                    key=f"org-candidate-select::{candidate_key}",
                )
                if action_columns[1].button("Mappen", key=f"org-candidate-map::{candidate_key}", width="stretch"):
                    if not selected_target:
                        st.warning("Bitte zuerst eine bestehende Organisationseinheit auswaehlen.")
                    else:
                        updated_kb = map_org_unit_candidate(knowledge_base, candidate_name, selected_target)
                        save_knowledge_base(updated_kb)
                        st.success("Kandidat wurde gemappt.")
                        st.rerun()

                proposed_name = action_columns[2].text_input(
                    "Als neue Org-Einheit uebernehmen",
                    value=candidate_name,
                    key=f"org-candidate-new::{candidate_key}",
                )
                if action_columns[3].button("Uebernehmen", key=f"org-candidate-accept::{candidate_key}", width="stretch"):
                    updated_kb = accept_org_unit_candidate_as_new(knowledge_base, candidate_name, proposed_name)
                    save_knowledge_base(updated_kb)
                    st.success("Kandidat wurde als neue Organisationseinheit uebernommen.")
                    st.rerun()

                if action_columns[4].button("Abweisen", key=f"org-candidate-reject::{candidate_key}", width="stretch"):
                    updated_kb = reject_org_unit_candidate(knowledge_base, candidate_name)
                    save_knowledge_base(updated_kb)
                    st.success("Kandidat wurde abgewiesen.")
                    st.rerun()

    with st.expander("Bereits entschiedene Kandidaten", expanded=False):
        decided_candidates = [
            entry
            for entry in knowledge_base.org_unit_candidates
            if entry.get("status", "open") != "open"
        ]
        if not decided_candidates:
            st.info("Noch keine entschiedenen Kandidaten vorhanden.")
        else:
            st.dataframe(
                [
                    {
                        "Kandidat": entry.get("candidate_name", ""),
                        "Status": entry.get("status", ""),
                        "Gemappt auf": entry.get("mapped_org_unit", ""),
                        "Zuletzt gesehen": entry.get("last_seen", ""),
                    }
                    for entry in decided_candidates
                ],
                width="stretch",
            )


def render_config_tab(config_path: Path) -> None:
    st.subheader("Anwendungskonfig")
    config = load_config(config_path)
    ensure_config_session_defaults(config)
    sync_config_session_defaults(config)

    with st.expander("Import", expanded=False):
        render_import_section(config)

    with st.expander("Konfiguration", expanded=False):
        render_path_picker_controls()

        with st.form("config_form"):
            llm_base_url = st.text_input("LLM Base URL", value=st.session_state["config_llm_base_url"])
            llm_model = st.text_input("LLM Model", value=st.session_state["config_llm_model"])
            llm_api_key_env = st.text_input("API Key Env Var", value=st.session_state["config_llm_api_key_env"])
            llm_context_window = st.number_input("Context Window", min_value=1, value=st.session_state["config_llm_context_window"])
            llm_timeout_seconds = st.number_input("LLM Timeout Seconds", min_value=1, value=int(config.llm_timeout_seconds))
            input_path = st.text_input("Input Path", value=st.session_state["config_input_path"])
            cmdb_filename = st.text_input("CMDB Filename", value=st.session_state["config_cmdb_filename"])
            output_path = st.text_input("Output Path", value=st.session_state["config_output_path"])
            cmdb_uuid_column = st.text_input("CMDB UUID Column", value=config.cmdb_uuid_column)
            cmdb_name_column = st.text_input("CMDB Name Column", value=config.cmdb_name_column)
            neo4j_url = st.text_input(
                "Neo4j URL",
                value=st.session_state["config_neo4j_url"],
            )
            if os.getenv("NEO4J_URI"):
                st.caption(
                    "NEO4J_URI wurde aus der Umgebung geladen. Der aktuell wirksame Wert ist im Feld sichtbar "
                    "und kann hier dauerhaft ueberschrieben werden."
                )
            neo4j_user = st.text_input(
                "Neo4j User",
                value=st.session_state["config_neo4j_user"],
            )
            if os.getenv("NEO4J_USERNAME"):
                st.caption(
                    "NEO4J_USERNAME wurde aus der Umgebung geladen. Der aktuell wirksame Wert ist im Feld sichtbar "
                    "und kann hier dauerhaft ueberschrieben werden."
                )
            neo4j_password = st.text_input("Neo4j Password", value=st.session_state["config_neo4j_password"], type="password")
            if os.getenv("NEO4J_PASSWORD"):
                st.caption(
                    "NEO4J_PASSWORD wurde aus der Umgebung geladen. Der aktuell wirksame Wert bleibt beim Speichern "
                    "erhalten, bis Sie ihn hier explizit aendern."
                )
            neo4j_database = st.text_input(
                "Neo4j Database",
                value=st.session_state["config_neo4j_database"],
            )
            if os.getenv("NEO4J_DATABASE"):
                st.caption(
                    "NEO4J_DATABASE wurde aus der Umgebung geladen. Der aktuell wirksame Wert ist im Feld sichtbar "
                    "und kann hier dauerhaft ueberschrieben werden."
                )
            fuzzy_threshold = st.number_input(
                "Fuzzy Threshold",
                min_value=0.0,
                max_value=1.0,
                value=float(config.fuzzy_threshold),
                step=0.01,
            )
            debug_mode = st.checkbox("Debug Mode", value=config.debug_mode)
            last_run_mode = st.selectbox(
                "Last Run Mode",
                ["initial", "full", "delta"],
                index=["initial", "full", "delta"].index(config.last_run_mode),
            )
            submitted = st.form_submit_button("Save Config")

        if submitted:
            previous_client_key = build_neo4j_client_key(config)
            updated_config = AppConfig(
                llm_base_url=llm_base_url,
                llm_model=llm_model,
                llm_api_key_env=llm_api_key_env,
                llm_context_window=int(llm_context_window),
                llm_timeout_seconds=int(llm_timeout_seconds),
                neo4j_url=neo4j_url.strip(),
                neo4j_user=neo4j_user.strip(),
                neo4j_password=neo4j_password.strip(),
                neo4j_database=neo4j_database.strip(),
                fuzzy_threshold=float(fuzzy_threshold),
                cmdb_uuid_column=cmdb_uuid_column,
                cmdb_name_column=cmdb_name_column,
                input_path=input_path,
                cmdb_filename=cmdb_filename,
                output_path=output_path,
                last_run_mode=last_run_mode,
                debug_mode=debug_mode,
            )
            save_config(updated_config, config_path)
            if build_neo4j_client_key(updated_config) != previous_client_key:
                reset_session_neo4j_client(show_warning=True)
            update_config_session_defaults(updated_config)
            st.success("Configuration saved.")

        refresh_neo4j_status = st.button("Neo4j-Verbindung neu pruefen")
        connection_ok, connection_message = get_neo4j_connection_status(
            load_config(config_path),
            force_refresh=refresh_neo4j_status,
        )
        if connection_ok:
            st.success(connection_message)
        else:
            st.error(connection_message)

        if st.button("Refresh Models"):
            client = OpenAICompatibleClient(
                LlmClientConfig(
                    base_url=st.session_state["config_llm_base_url"],
                    model=st.session_state["config_llm_model"],
                    api_key_env=st.session_state["config_llm_api_key_env"],
                    debug_logger=lambda event, details: write_debug_log(load_config(config_path), event, details),
                )
            )
            try:
                models = client.list_models()
            except LlmClientError as exc:
                st.error(str(exc))
            else:
                st.write({"models": models})

        refresh_llm_status = st.button("LLM-Verbindung neu pruefen")
        llm_status_level, llm_status_message = get_llm_status(
            load_config(config_path),
            force_refresh=refresh_llm_status,
        )
        if llm_status_level == "success":
            st.success(llm_status_message)
        elif llm_status_level == "warning":
            st.warning(llm_status_message)
        else:
            st.error(llm_status_message)

        st.caption("Current config")
        st.json(asdict(load_config(config_path)))


def ensure_config_session_defaults(config: AppConfig) -> None:
    if "config_llm_base_url" not in st.session_state:
        update_config_session_defaults(config)


def sync_config_session_defaults(config: AppConfig) -> None:
    if is_legacy_input_path(st.session_state.get("config_input_path", "")) and config.input_path != st.session_state.get("config_input_path"):
        st.session_state["config_input_path"] = config.input_path
    if st.session_state.get("config_neo4j_url") != config.neo4j_url:
        st.session_state["config_neo4j_url"] = config.neo4j_url
    if st.session_state.get("config_neo4j_user") != config.neo4j_user:
        st.session_state["config_neo4j_user"] = config.neo4j_user
    if st.session_state.get("config_neo4j_password") != config.neo4j_password:
        st.session_state["config_neo4j_password"] = config.neo4j_password
    if st.session_state.get("config_neo4j_database") != config.neo4j_database:
        st.session_state["config_neo4j_database"] = config.neo4j_database


def update_config_session_defaults(config: AppConfig) -> None:
    st.session_state["config_llm_base_url"] = config.llm_base_url
    st.session_state["config_llm_model"] = config.llm_model
    st.session_state["config_llm_api_key_env"] = config.llm_api_key_env
    st.session_state["config_llm_context_window"] = config.llm_context_window
    st.session_state["config_input_path"] = config.input_path
    st.session_state["config_cmdb_filename"] = config.cmdb_filename
    st.session_state["config_output_path"] = config.output_path
    st.session_state["config_neo4j_url"] = config.neo4j_url
    st.session_state["config_neo4j_user"] = config.neo4j_user
    st.session_state["config_neo4j_password"] = config.neo4j_password
    st.session_state["config_neo4j_database"] = config.neo4j_database


def render_path_picker_controls() -> None:
    st.markdown("**Pfade auswaehlen**")
    input_column, cmdb_column, output_column = st.columns(3)

    if input_column.button("Input-Ordner waehlen", width="stretch"):
        selected_path = pick_directory(st.session_state["config_input_path"])
        if selected_path:
            st.session_state["config_input_path"] = selected_path
            st.rerun()

    if cmdb_column.button("CMDB-Datei im Input-Ordner waehlen", width="stretch"):
        selected_path = pick_file(st.session_state["config_input_path"], [("CSV files", "*.csv"), ("All files", "*.*")])
        if selected_path:
            selected_file = Path(selected_path)
            st.session_state["config_input_path"] = str(selected_file.parent)
            st.session_state["config_cmdb_filename"] = selected_file.name
            st.rerun()

    if output_column.button("Output-Ordner waehlen", width="stretch"):
        selected_path = pick_directory(st.session_state["config_output_path"])
        if selected_path:
            st.session_state["config_output_path"] = selected_path
            st.rerun()


def render_import_section(config: AppConfig) -> None:
    st.markdown("**Import**")
    ensure_import_session_defaults(config)

    input_dir = resolve_project_path(config.input_path)
    cmdb_path = resolve_input_cmdb_path(config)
    current_process_files = list_process_files(input_dir)
    process_file_labels = {path.relative_to(input_dir).as_posix(): path for path in current_process_files}
    available_bpmn_files = [
        path
        for path in current_process_files
        if path.suffix.lower() in {".bpmn", ".xml"}
    ]

    uploaded_process_files = st.file_uploader(
        "Prozessdateien importieren",
        type=["bpmn", "xml", "txt", "docx", "pdf"],
        accept_multiple_files=True,
        key="process_upload",
    )
    uploaded_cmdb_file = st.file_uploader(
        "CMDB-Datei importieren",
        type=["csv"],
        accept_multiple_files=False,
        key="cmdb_upload",
    )

    mode_column, save_column, transform_column, run_column = st.columns([1, 1, 1, 1])
    with mode_column:
        selected_run_mode = st.selectbox(
            "Importmodus",
            options=["initial", "full", "delta"],
            key="import_run_mode",
        )
        selected_import_filenames = st.multiselect(
            "Dateien fuer Import",
            options=list(process_file_labels.keys()),
            default=[],
            key="import_process_selection",
        )
    with save_column:
        if st.button("Importdateien speichern", width="stretch"):
            saved_files: list[str] = []
            for uploaded_file in uploaded_process_files or []:
                target_path = input_dir / sanitize_uploaded_name(uploaded_file.name)
                save_uploaded_file(target_path, uploaded_file.getvalue())
                saved_files.append(str(target_path))

            if uploaded_cmdb_file is not None:
                target_path = input_dir / sanitize_uploaded_name(uploaded_cmdb_file.name)
                save_uploaded_file(target_path, uploaded_cmdb_file.getvalue())
                saved_files.append(str(cmdb_path))
                updated_config = AppConfig(**{**asdict(config), "cmdb_filename": sanitize_uploaded_name(uploaded_cmdb_file.name)})
                save_config(updated_config)
                update_config_session_defaults(updated_config)

            if saved_files:
                st.success(f"{len(saved_files)} Datei(en) gespeichert.")
                st.rerun()
            else:
                st.info("Keine neuen Dateien zum Speichern ausgewaehlt.")

    with transform_column:
        selected_transform_filenames = st.multiselect(
            "BPMN fuer Transformation",
            options=[path.relative_to(input_dir).as_posix() for path in available_bpmn_files],
            default=[],
            key="transform_bpmn_selection",
        )
        if st.button("BPMN transformieren", width="stretch"):
            if not available_bpmn_files:
                st.info("Keine BPMN/XML-Dateien im aktuellen Input-Pfad gefunden.")
            elif not selected_transform_filenames:
                st.info("Bitte waehlen Sie mindestens eine BPMN/XML-Datei fuer die Transformation aus.")
            else:
                selected_bpmn_files = [
                    process_file_labels[label]
                    for label in selected_transform_filenames
                ]
                transformed_paths: list[str] = []
                try:
                    for bpmn_file in selected_bpmn_files:
                        transformed_batch = transform_bpmn_for_import(bpmn_file, input_dir)
                        transformed_paths.extend(str(path) for path in transformed_batch)
                except BpmnTransformError as exc:
                    st.error(str(exc))
                else:
                    st.success(
                        f"{len(transformed_paths)} Transform-Datei(en) erzeugt. "
                        f"Die neuen Dateien liegen unter `{input_dir / 'transformed'}`."
                    )
                    st.write(transformed_paths)

    with run_column:
        render_run_feedback(IMPORT_RUN_FEEDBACK_STATE_KEY)
        render_active_pipeline_run_monitor(ACTIVE_IMPORT_RUN_ID_STATE_KEY, IMPORT_RUN_FEEDBACK_STATE_KEY)
        import_running = bool(st.session_state.get(ACTIVE_IMPORT_RUN_ID_STATE_KEY))
        if st.button("Pipeline starten", width="stretch", disabled=import_running):
            if not config.llm_model:
                st.warning("Bitte zuerst ein LLM-Modell konfigurieren.")
            else:
                uploaded_runtime_paths: list[Path] = []
                for uploaded_file in uploaded_process_files or []:
                    target_path = input_dir / sanitize_uploaded_name(uploaded_file.name)
                    save_uploaded_file(target_path, uploaded_file.getvalue())
                    uploaded_runtime_paths.append(target_path)

                selected_input_paths = [
                    process_file_labels[label]
                    for label in selected_import_filenames
                ]
                explicit_input_paths = uploaded_runtime_paths + selected_input_paths
                if not explicit_input_paths:
                    st.info("Bitte waehlen Sie mindestens eine Prozessdatei fuer den Import aus.")
                    return

                runtime_config = AppConfig(
                    **{
                        **asdict(config),
                        "last_run_mode": selected_run_mode,
                        "cmdb_filename": st.session_state.get("active_cmdb_filename", config.cmdb_filename),
                    }
                )
                start_async_pipeline_run(
                    runtime_config,
                    run_state_key=ACTIVE_IMPORT_RUN_ID_STATE_KEY,
                    feedback_state_key=IMPORT_RUN_FEEDBACK_STATE_KEY,
                    success_message_template="Pipeline-Lauf abgeschlossen in {duration}. Ergebnisse liegen im Output-Ordner.",
                    input_paths=explicit_input_paths,
                )
                st.rerun()

    current_cmdb_files = list_cmdb_files(input_dir)
    ensure_active_cmdb_selection(config, current_cmdb_files)

    st.caption(f"Aktueller Input-Pfad: `{input_dir}`")
    if current_process_files:
        st.write([str(path) for path in current_process_files])
    else:
        st.info("Noch keine Prozessdateien im Input-Pfad vorhanden.")

    st.caption("Verfuegbare CMDB-Dateien im Input-Pfad")
    if current_cmdb_files:
        selected_cmdb_filename = st.selectbox(
            "Aktive CMDB-Datei",
            options=[path.name for path in current_cmdb_files],
            key="active_cmdb_filename",
        )
        if st.button("Aktive CMDB-Datei uebernehmen", width="stretch"):
            updated_config = AppConfig(**{**asdict(config), "cmdb_filename": selected_cmdb_filename})
            save_config(updated_config)
            update_config_session_defaults(updated_config)
            st.success(f"Aktive CMDB-Datei auf '{selected_cmdb_filename}' gesetzt.")
            st.rerun()
    else:
        st.info("Noch keine CMDB-Datei im Input-Pfad vorhanden.")

    runtime_output_path, used_output_fallback = resolve_runtime_output_path(config.output_path)
    st.caption(f"Konfigurierter Output-Pfad: `{resolve_project_path(config.output_path)}`")
    if used_output_fallback:
        st.warning(f"Der konfigurierte Output-Pfad ist aktuell nicht beschreibbar. Artefakte werden nach `{runtime_output_path}` geschrieben.")
    else:
        st.write(str(runtime_output_path))


def ensure_active_cmdb_selection(config: AppConfig, cmdb_files: list[Path]) -> None:
    available_filenames = [path.name for path in cmdb_files]
    if "active_cmdb_filename" not in st.session_state:
        st.session_state["active_cmdb_filename"] = config.cmdb_filename
    if available_filenames and st.session_state["active_cmdb_filename"] not in available_filenames:
        st.session_state["active_cmdb_filename"] = available_filenames[0]


def ensure_import_session_defaults(config: AppConfig) -> None:
    if "import_run_mode" not in st.session_state:
        st.session_state["import_run_mode"] = config.last_run_mode
    if st.session_state.get("import_run_mode") not in {"initial", "full", "delta"}:
        st.session_state["import_run_mode"] = config.last_run_mode


def main() -> None:
    load_env_files()
    st.set_page_config(page_title="BRIDGR", layout="wide")
    st.title("BRIDGR")
    tabs = st.tabs(["Kommunikation", "Link Editing", "Anwendungskonfig", "Organisation"])
    config_path = Path("config.json")

    with tabs[0]:
        render_query_tab()
    with tabs[1]:
        render_review_tab()
    with tabs[2]:
        render_config_tab(config_path)
    with tabs[3]:
        render_organization_tab()


if __name__ == "__main__":
    main()

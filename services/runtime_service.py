from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from time import perf_counter, sleep
import threading
from uuid import uuid4

import streamlit as st

import core.debug_utils as debug_utils
from core.app_config import AppConfig, is_legacy_input_path, resolve_runtime_output_path
from core.llm_client import LlmClientConfig, LlmClientError, OpenAICompatibleClient
from core.neo4j_utils import Neo4jClient, Neo4jConfig, Neo4jConnectionError, Neo4jQueryError
from processing.pipeline import run_pipeline


NEO4J_CLIENT_STATE_KEY = "neo4j_client"
NEO4J_CLIENT_CONFIG_STATE_KEY = "neo4j_client_config"
NEO4J_CONNECTION_STATUS_STATE_KEY = "neo4j_connection_status"
NEO4J_CONNECTION_STATUS_CONFIG_STATE_KEY = "neo4j_connection_status_config"
LLM_STATUS_STATE_KEY = "llm_status"
LLM_STATUS_CONFIG_STATE_KEY = "llm_status_config"
CHAT_MESSAGES_STATE_KEY = "chat_messages"
REVIEW_RUN_FEEDBACK_STATE_KEY = "review_run_feedback"
IMPORT_RUN_FEEDBACK_STATE_KEY = "import_run_feedback"
ACTIVE_REVIEW_RUN_ID_STATE_KEY = "active_review_run_id"
ACTIVE_IMPORT_RUN_ID_STATE_KEY = "active_import_run_id"
PENDING_REVIEW_SCOPE_MODE_STATE_KEY = "pending_review_scope_mode"
PENDING_REVIEW_SELECTION_CLEAR_STATE_KEY = "pending_review_selection_clear"

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


def write_debug_log(config: AppConfig, event: str, details: dict) -> None:
    original_resolver = debug_utils.resolve_runtime_output_path
    try:
        debug_utils.resolve_runtime_output_path = resolve_runtime_output_path
        debug_utils.write_debug_log(config, event, details)
    finally:
        debug_utils.resolve_runtime_output_path = original_resolver


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


def render_active_pipeline_run_monitor(run_state_key: str, feedback_state_key: str) -> None:
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
        sleep(1)
        st.rerun()
        return

    st.session_state.pop(run_state_key, None)
    clear_pipeline_run_tracker(active_run_id)
    if status == "success":
        duration_seconds = float(tracker.get("duration_seconds") or 0.0)
        success_message = str(tracker.get("success_message_template", "")).format(
            duration=format_duration(duration_seconds)
        )
        set_run_feedback(feedback_state_key, "success", success_message)
        st.success(success_message)
    else:
        error_message = str(tracker.get("error_message", "Unbekannter Fehler."))
        set_run_feedback(feedback_state_key, "error", error_message)
        st.error(error_message)


def run_pipeline_with_live_feedback(
    config: AppConfig,
    feedback_state_key: str,
    success_message_template: str,
    input_paths: list[Path] | None = None,
) -> tuple[object | None, str | None]:
    clear_run_feedback(feedback_state_key)
    progress_placeholder = st.empty()
    status_placeholder = st.empty()
    started_at = perf_counter()

    def progress_callback(progress: dict) -> None:
        total = max(0, int(progress.get("total", 0)))
        completed = max(0, int(progress.get("completed", 0)))
        source_path = progress.get("source_path", "")
        document_status = progress.get("status", "")
        source_name = Path(source_path).name if source_path else "-"
        if total > 0:
            progress_placeholder.progress(min(1.0, completed / total))
            status_placeholder.info(
                f"{completed} von {total} Dateien bearbeitet. Aktuell/zuletzt: `{source_name}` ({document_status or 'unbekannt'})."
            )
        else:
            status_placeholder.info("Lauf gestartet. Die Anzahl der zu bearbeitenden Dateien wird ermittelt.")

    try:
        run_result = run_pipeline(config, input_paths=input_paths, progress_callback=progress_callback)
    except Exception as exc:
        progress_placeholder.empty()
        status_placeholder.empty()
        error_message = str(exc)
        set_run_feedback(feedback_state_key, "error", error_message)
        st.error(error_message)
        return None, None

    progress_placeholder.empty()
    status_placeholder.empty()
    duration = format_duration(perf_counter() - started_at)
    success_message = success_message_template.format(duration=duration)
    set_run_feedback(feedback_state_key, "success", success_message)
    st.success(success_message)
    return run_result, duration


def ensure_query_chat_defaults() -> None:
    st.session_state.setdefault(CHAT_MESSAGES_STATE_KEY, [])


def reset_query_chat_state() -> None:
    st.session_state[CHAT_MESSAGES_STATE_KEY] = []


def append_chat_message(role: str, content: str, cypher_query: str = "", rows: list[dict] | None = None) -> None:
    st.session_state[CHAT_MESSAGES_STATE_KEY].append(
        {
            "role": role,
            "content": content,
            "cypher_query": cypher_query,
            "rows": rows or [],
        }
    )


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
    st.session_state["config_chat_mode"] = config.chat_mode
    st.session_state["config_input_path"] = config.input_path
    st.session_state["config_cmdb_filename"] = config.cmdb_filename
    st.session_state["config_cmdb_relations_filename"] = config.cmdb_relations_filename
    st.session_state["config_output_path"] = config.output_path
    st.session_state["config_neo4j_url"] = config.neo4j_url
    st.session_state["config_neo4j_user"] = config.neo4j_user
    st.session_state["config_neo4j_password"] = config.neo4j_password
    st.session_state["config_neo4j_database"] = config.neo4j_database


def ensure_active_cmdb_selection(
    config: AppConfig,
    entity_files: list[Path],
    relation_files: list[Path],
) -> None:
    available_entity_paths = [path.as_posix() for path in entity_files]
    available_relation_paths = [path.as_posix() for path in relation_files]
    if "active_cmdb_filename" not in st.session_state:
        st.session_state["active_cmdb_filename"] = config.cmdb_filename
    if available_entity_paths and st.session_state["active_cmdb_filename"] not in available_entity_paths:
        st.session_state["active_cmdb_filename"] = available_entity_paths[0]
    if "active_cmdb_relations_filename" not in st.session_state:
        st.session_state["active_cmdb_relations_filename"] = config.cmdb_relations_filename
    if available_relation_paths:
        if st.session_state["active_cmdb_relations_filename"] not in available_relation_paths:
            st.session_state["active_cmdb_relations_filename"] = available_relation_paths[0]
    else:
        st.session_state["active_cmdb_relations_filename"] = ""


def ensure_import_session_defaults(config: AppConfig) -> None:
    if "import_run_mode" not in st.session_state:
        st.session_state["import_run_mode"] = config.last_run_mode
    if st.session_state.get("import_run_mode") not in {"full", "partial"}:
        st.session_state["import_run_mode"] = config.last_run_mode


def request_review_last_import_scope() -> None:
    st.session_state[PENDING_REVIEW_SCOPE_MODE_STATE_KEY] = "Nur letzter Import"
    st.session_state[PENDING_REVIEW_SELECTION_CLEAR_STATE_KEY] = True


def apply_pending_review_scope_defaults() -> None:
    pending_scope_mode = st.session_state.pop(PENDING_REVIEW_SCOPE_MODE_STATE_KEY, None)
    if pending_scope_mode is not None:
        st.session_state["review_scope_mode"] = pending_scope_mode

    should_clear_selection = st.session_state.pop(PENDING_REVIEW_SELECTION_CLEAR_STATE_KEY, False)
    if should_clear_selection:
        st.session_state["review_process_selection"] = []

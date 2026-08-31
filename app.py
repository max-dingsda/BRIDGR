from __future__ import annotations

from pathlib import Path

import streamlit as st

from core.env_loader import load_env_files
from core.app_config import load_config
from services.organization_service import (
    persist_org_candidate_mapping_refresh,
    persist_organization_sync,
    persist_org_unit_node,
)
from services.review_service import (
    persist_latest_run_refresh,
    rerun_single_document_from_artifact,
)
from services.runtime_service import (
    ACTIVE_IMPORT_RUN_ID_STATE_KEY,
    ACTIVE_REVIEW_RUN_ID_STATE_KEY,
    CHAT_MESSAGES_STATE_KEY,
    IMPORT_RUN_FEEDBACK_STATE_KEY,
    LLM_STATUS_CONFIG_STATE_KEY,
    LLM_STATUS_STATE_KEY,
    NEO4J_CLIENT_CONFIG_STATE_KEY,
    NEO4J_CLIENT_STATE_KEY,
    NEO4J_CONNECTION_STATUS_CONFIG_STATE_KEY,
    NEO4J_CONNECTION_STATUS_STATE_KEY,
    REVIEW_RUN_FEEDBACK_STATE_KEY,
    append_chat_message,
    apply_pending_review_scope_defaults,
    build_neo4j_client_key,
    clear_pipeline_run_tracker,
    clear_run_feedback,
    create_pipeline_run_tracker,
    ensure_config_session_defaults,
    ensure_import_session_defaults,
    ensure_query_chat_defaults,
    fail_pipeline_run_tracker,
    finish_pipeline_run_tracker,
    format_duration,
    get_llm_status,
    get_neo4j_connection_status,
    get_pipeline_run_tracker,
    get_session_neo4j_client,
    render_active_pipeline_run_monitor,
    render_run_feedback,
    request_review_last_import_scope,
    reset_query_chat_state,
    reset_session_neo4j_client,
    run_pipeline_with_live_feedback,
    set_run_feedback,
    sync_config_session_defaults,
    update_config_session_defaults,
    update_pipeline_run_tracker,
    write_debug_log,
)
from ui.archimate_tab import render_archimate_tab
from ui.config_tab import render_config_tab
from ui.import_tab import render_import_tab
from ui.layout import get_active_locale, get_active_role, get_dark_mode_preference, get_visible_tabs, inject_global_styles, render_app_header
from core.i18n import install_streamlit_localization, translate
from ui.organization_tab import render_organization_tab
from ui.query_tab import render_query_tab
from ui.review_tab import render_review_tab


def main() -> None:
    load_env_files()
    st.set_page_config(page_title="BRIDGR", layout="wide")
    install_streamlit_localization()
    config_path = Path("config.json")
    st.session_state.setdefault("bridgr_locale", load_config(config_path).ui_locale)
    inject_global_styles(get_dark_mode_preference())
    render_app_header()

    tab_renderers = {
        "chat": render_query_tab,
        "import": lambda: render_import_tab(config_path),
        "review": render_review_tab,
        "organization": render_organization_tab,
        "archimate": render_archimate_tab,
        "configuration": lambda: render_config_tab(config_path),
    }

    visible_tab_names = get_visible_tabs(get_active_role())
    locale = get_active_locale()
    tabs = st.tabs([translate(f"tab.{tab_name}", locale) for tab_name in visible_tab_names])
    for tab, tab_name in zip(tabs, visible_tab_names):
        with tab:
            tab_renderers[tab_name]()


if __name__ == "__main__":
    main()

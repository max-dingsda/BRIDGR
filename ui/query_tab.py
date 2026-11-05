from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

from core.app_config import AppConfig, load_config
from core.i18n import translate
from core.neo4j_utils import Neo4jExecutionError
from ui.layout import get_active_locale
from services.chat_diagram_service import diagram_is_possible, render_chat_diagram
from services.query_service import run_query_chat_turn
from ui.layout import render_page_header
from services.runtime_service import (
    CHAT_MESSAGES_STATE_KEY,
    append_chat_message,
    ensure_query_chat_defaults,
    get_session_chat_client,
    reset_query_chat_state,
)


_INTERACTIVE_DIAGRAM_HEIGHT = 1000


def _has_no_matches(message: dict, rows: list[dict]) -> bool:
    """Only an empty stored result warrants the no-matches notice."""
    return message.get("role") == "assistant" and bool(message.get("cypher_query")) and not rows


def _diagram_state(message: dict) -> str:
    """Distinguish an unrequested diagram from an unavailable generated one."""
    if "diagram_html" not in message:
        return "not_requested"
    return "ready" if message["diagram_html"] else "unavailable"


def render_query_chat_messages(config: AppConfig) -> None:
    locale = get_active_locale()
    for idx, message in enumerate(st.session_state.get(CHAT_MESSAGES_STATE_KEY, [])):
        with st.chat_message(message["role"]):
            st.write(message["content"])
            rows = message.get("rows", [])
            if rows and message.get("table_visible"):
                st.markdown(f"**{translate('chat.result', locale)}**")
                st.dataframe(rows, width="stretch")
                csv_data = pd.DataFrame(rows).to_csv(index=False).encode("utf-8")
                st.download_button(
                    label=f"⬇ {translate('chat.export_csv', locale)}",
                    data=csv_data,
                    file_name="result.csv",
                    mime="text/csv",
                    key=f"download-csv-{idx}",
                )
            elif _has_no_matches(message, rows):
                st.info(translate("chat.no_matches", locale))
            if message.get("cypher_query"):
                with st.expander(translate("chat.technical_details", locale), expanded=False):
                    st.markdown("**Cypher**")
                    st.code(message["cypher_query"], language="cypher")
            if message["role"] == "assistant":
                _render_message_actions(idx, message, config, locale)


def _render_message_actions(idx: int, message: dict, config: AppConfig, locale: str) -> None:
    """Keep presentation state on the message; no query is repeated for a table."""
    rows = message.get("rows", [])
    if rows and st.button("Tabelle anzeigen" if not message.get("table_visible") else "Tabelle ausblenden", key=f"table-btn-{idx}"):
        message["table_visible"] = not message.get("table_visible", False)
        st.rerun()
    if not diagram_is_possible(rows):
        return
    if _diagram_state(message) == "not_requested":
        if st.button(f"📊 {translate('chat.show_as_diagram', locale)}", key=f"diagram-btn-{idx}"):
            try:
                result = render_chat_diagram(get_session_chat_client(config), rows, message.get("cypher_query", ""), f"chat-{idx}")
            except Neo4jExecutionError:
                st.warning(translate("chat.diagram_unavailable", locale))
                return
            except RuntimeError as exc:
                st.warning(str(exc))
                return
            message["diagram_html"] = result.html_path or ""
            message["diagram_png"] = result.png_path or ""
            message["diagram_note"] = result.note
            st.rerun()
        return
    if _diagram_state(message) == "unavailable":
        st.info(translate("chat.diagram_none", locale))
        return
    if not _render_interactive_diagram(message["diagram_html"]):
        if message.get("diagram_png"):
            st.image(message["diagram_png"], caption="Diagrammvorschau")
        st.warning("Die interaktive Diagrammansicht konnte nicht geladen werden.")
    if message.get("diagram_note"):
        st.caption(message["diagram_note"])
    if st.button(translate("chat.hide_diagram", locale), key=f"diagram-hide-{idx}"):
        for key in ("diagram_html", "diagram_png", "diagram_note"):
            message.pop(key, None)
        st.rerun()


def _render_interactive_diagram(html_path: str) -> bool:
    """Embed the standalone Archify artifact so its viewer controls remain usable."""
    try:
        document = Path(html_path).read_text(encoding="utf-8")
    except OSError:
        return False
    components.html(document, height=_INTERACTIVE_DIAGRAM_HEIGHT, scrolling=True)
    return True


def render_query_tab() -> None:
    render_page_header(
        translate("chat.title", get_active_locale()),
        translate("chat.subtitle", get_active_locale()),
        translate("chat.meta", get_active_locale()),
    )
    config = load_config(Path("config.json"))
    ensure_query_chat_defaults()

    if not config.llm_model:
        st.info(
            translate("chat.getting_started", get_active_locale())
        )

    action_column, _ = st.columns([1, 5])
    with action_column:
        if st.button(translate("chat.new_conversation", get_active_locale()), key="chat-reset", width="stretch"):
            reset_query_chat_state()
            st.rerun()
    render_query_chat_messages(config)

    question = st.chat_input(translate("chat.input", get_active_locale()))
    if not question:
        return
    if not config.llm_model:
        st.warning(translate("chat.configure_llm", get_active_locale()))
        return
    if not config.neo4j_password:
        st.warning(translate("chat.configure_neo4j", get_active_locale()))
        return

    append_chat_message("user", question)
    with st.chat_message("user"):
        st.write(question)
    with st.chat_message("assistant"):
        with st.spinner(""):
            run_query_chat_turn(question, config, get_active_locale())
    st.rerun()

from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

from core.app_config import load_config
from core.i18n import translate
from ui.layout import get_active_locale
from services.query_service import run_query_chat_turn
from ui.layout import render_page_header
from services.runtime_service import (
    CHAT_MESSAGES_STATE_KEY,
    append_chat_message,
    ensure_query_chat_defaults,
    reset_query_chat_state,
)


def render_query_chat_messages() -> None:
    locale = get_active_locale()
    for idx, message in enumerate(st.session_state.get(CHAT_MESSAGES_STATE_KEY, [])):
        with st.chat_message(message["role"]):
            st.write(message["content"])
            rows = message.get("rows", [])
            if rows:
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
            elif message["role"] == "assistant" and message.get("cypher_query"):
                st.info(translate("chat.no_matches", locale))
            if message.get("cypher_query"):
                with st.expander(translate("chat.technical_details", locale), expanded=False):
                    st.markdown("**Cypher**")
                    st.code(message["cypher_query"], language="cypher")


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
    render_query_chat_messages()

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

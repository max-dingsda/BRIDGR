from __future__ import annotations

from pathlib import Path

import streamlit as st

from app_config import load_config
from services.query_service import handle_query_clarification, run_query_chat_turn
from services.runtime_service import (
    CHAT_MESSAGES_STATE_KEY,
    CHAT_PENDING_APPLICATION_OPTIONS_STATE_KEY,
    append_chat_message,
    ensure_query_chat_defaults,
    reset_query_chat_state,
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

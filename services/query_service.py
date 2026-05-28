from __future__ import annotations

from app_config import AppConfig, resolve_project_path
from llm_client import LlmClientConfig, LlmClientError, OpenAICompatibleClient
from neo4j_utils import Neo4jConnectionError, Neo4jQueryError, QueryValidationError
from query_layer import build_natural_language_answer, generate_cypher_from_question
from services.runtime_service import (
    CHAT_PENDING_APPLICATION_OPTIONS_STATE_KEY,
    CHAT_PENDING_ORIGINAL_QUESTION_STATE_KEY,
    append_chat_message,
    get_session_neo4j_client,
    write_debug_log,
)
import streamlit as st


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
        f'Die Rueckfrage wurde so praezisiert: Gemeint ist genau die Anwendung "{resolved_option}".'
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
            {"question": question, "cypher_query": cypher_query, "error": str(exc)},
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

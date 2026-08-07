from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from core.neo4j_utils import Neo4jConnectionError
from core.llm_client import LlmClientError
from services.query_service import (
    _build_llm_history,
    _collect_protected_names,
    _extract_cypher_from_response,
    _format_query_result,
    _polish_response_language,
    _translate_error_for_user,
    _run_tool_use_turn,
    _EXECUTE_CYPHER_TOOL_SCHEMA,
)


def test_polish_response_language_uses_a_separate_language_only_prompt() -> None:
    llm_client = MagicMock()
    llm_client.generate_chat.return_value = "Es gibt drei Prozesse."

    result = _polish_response_language(
        llm_client,
        "Welche Prozesse gibt es?",
        "There are three Process nodes.",
        ["ns-prd-001"],
    )

    assert result == "Es gibt drei Prozesse."
    messages = llm_client.generate_chat.call_args.args[0]
    assert "Preserve every fact" in messages[0]["content"]
    assert "Correct spelling" in messages[0]["content"]
    assert "business slang" in messages[0]["content"]
    assert "Graph schema" not in messages[0]["content"]
    assert '"ns-prd-001"' in messages[1]["content"]


def test_polish_response_language_keeps_original_on_llm_error() -> None:
    llm_client = MagicMock()
    llm_client.generate_chat.side_effect = LlmClientError("offline")

    assert _polish_response_language(llm_client, "Question", "Original answer") == "Original answer"


def test_collect_protected_names_preserves_result_names_but_not_schema_terms() -> None:
    rows = [{"application": "SAP SD", "server": "ns-prd-001", "type": "Application"}]

    assert _collect_protected_names(rows) == ["SAP SD", "ns-prd-001"]


# --- _extract_cypher_from_response ---

def test_extract_cypher_from_response_returns_query_from_fenced_block() -> None:
    response = "```cypher\nMATCH (p:Process) RETURN p.name AS process\n```"
    assert _extract_cypher_from_response(response) == "MATCH (p:Process) RETURN p.name AS process"


def test_extract_cypher_from_response_returns_empty_for_plain_text() -> None:
    assert _extract_cypher_from_response("Es gibt 5 Processe.") == ""


def test_extract_cypher_from_response_returns_empty_for_empty_string() -> None:
    assert _extract_cypher_from_response("") == ""


def test_extract_cypher_from_response_handles_plain_fence_without_language_tag() -> None:
    response = "```\nMATCH (a:Application) RETURN a.name AS application\n```"
    assert _extract_cypher_from_response(response) == "MATCH (a:Application) RETURN a.name AS application"


def test_extract_cypher_from_response_ignores_trailing_text_after_block() -> None:
    response = "```cypher\nMATCH (p:Process) RETURN count(p) AS cnt\n```\nDas wird die Anzahl der Processe ergeben."
    result = _extract_cypher_from_response(response)
    assert result == "MATCH (p:Process) RETURN count(p) AS cnt"


def test_extract_cypher_from_response_is_case_insensitive_on_fence_tag() -> None:
    response = "```CYPHER\nMATCH (s:Server) RETURN s.name AS server\n```"
    assert _extract_cypher_from_response(response) == "MATCH (s:Server) RETURN s.name AS server"


# --- _format_query_result ---

def test_format_query_result_includes_rows_as_json() -> None:
    rows = [{"process": "Bestellabwicklung"}, {"process": "Reklamationsbearbeitung"}]
    result = _format_query_result(rows, [])
    assert "[ABFRAGEERGEBNIS]" in result
    assert "Bestellabwicklung" in result
    assert "Reklamationsbearbeitung" in result


def test_format_query_result_reports_no_results_when_empty() -> None:
    result = _format_query_result([], [])
    assert "[ABFRAGEERGEBNIS]" in result
    assert "Keine Treffer" in result


def test_format_query_result_includes_alias_hints_when_empty() -> None:
    hints = ['"mail" könnte sich auf "Mail System" (Application) beziehen']
    result = _format_query_result([], hints)
    assert "Keine Treffer" in result
    assert "Mail System" in result
    assert "Hinweis" in result


def test_format_query_result_does_not_include_hints_when_rows_present() -> None:
    rows = [{"process": "Bestellabwicklung"}]
    hints = ['"mail" könnte sich auf "Mail System" (Application) beziehen']
    result = _format_query_result(rows, hints)
    # hints must not appear when we have actual results
    assert "Mail System" not in result


def test_format_query_result_uses_english_protocol_for_english_chat() -> None:
    assert _format_query_result([], [], "en") == "[QUERY_RESULT]\nNo matches."


def test_translate_error_for_user_uses_active_response_locale() -> None:
    assert "cannot reach" in _translate_error_for_user(Neo4jConnectionError("offline"), "en")


# --- _build_llm_history ---

def test_build_llm_history_returns_role_and_content_only() -> None:
    messages = [
        {"role": "user", "content": "Welche Processe gibt es?", "cypher_query": "MATCH ...", "rows": []},
        {"role": "assistant", "content": "Es gibt 5 Processe.", "cypher_query": "MATCH ...", "rows": []},
    ]
    history = _build_llm_history(messages)
    assert history == [
        {"role": "user", "content": "Welche Processe gibt es?"},
        {"role": "assistant", "content": "Es gibt 5 Processe."},
    ]


def test_build_llm_history_skips_messages_with_empty_content() -> None:
    messages = [
        {"role": "user", "content": ""},
        {"role": "assistant", "content": "Antwort"},
    ]
    history = _build_llm_history(messages)
    assert history == [{"role": "assistant", "content": "Antwort"}]


def test_build_llm_history_trims_to_max_messages() -> None:
    messages = [{"role": "user", "content": f"Frage {i}"} for i in range(30)]
    history = _build_llm_history(messages)
    assert len(history) == 20
    assert history[0]["content"] == "Frage 10"
    assert history[-1]["content"] == "Frage 29"


def test_build_llm_history_returns_empty_for_no_messages() -> None:
    assert _build_llm_history([]) == []


# --- _run_tool_use_turn ---

def _make_tool_call(call_id: str, query: str) -> dict:
    return {
        "id": call_id,
        "type": "function",
        "function": {"name": "execute_cypher", "arguments": json.dumps({"query": query})},
    }


def test_run_tool_use_turn_returns_direct_answer_when_no_tool_calls() -> None:
    # Model never calls a tool (e.g. greeting). After the correction retry it still
    # returns no tool call, so we accept the response.
    llm_client = MagicMock()
    llm_client.generate_with_tools.side_effect = [
        ("Direkte Antwort", []),  # first attempt — no tool call, correction injected
        ("Direkte Antwort", []),  # retry after correction — still no tool call, accepted
    ]
    neo4j_client = MagicMock()

    messages = [{"role": "user", "content": "Frage"}]
    content, cypher, rows = _run_tool_use_turn(messages, llm_client, neo4j_client)

    assert content == "Direkte Antwort"
    assert cypher == ""
    assert rows == []
    assert llm_client.generate_with_tools.call_count == 2
    neo4j_client.execute_read.assert_not_called()


def test_run_tool_use_turn_retries_with_correction_when_model_skips_tool() -> None:
    # Simulates the hallucination bug: model answers a factual question without calling
    # the tool on the first try, then correctly calls the tool after the correction.
    tool_call = _make_tool_call("call_retry", "MATCH (a:Application) RETURN a.name AS application")
    rows_result = [{"application": "SAP ERP"}]

    llm_client = MagicMock()
    llm_client.generate_with_tools.side_effect = [
        ("SAP ERP und Webshop.", []),        # first call: hallucinated answer, no tool
        ("", [tool_call]),                   # second call (after correction): calls tool
        ("Die Application ist SAP ERP.", []),  # third call: final answer from query result
    ]
    neo4j_client = MagicMock()
    neo4j_client.execute_read.return_value = rows_result

    log_fn = MagicMock()
    messages = [{"role": "user", "content": "Welche Applicationen gibt es?"}]
    content, cypher, rows = _run_tool_use_turn(messages, llm_client, neo4j_client, log_fn)

    assert content == "Die Application ist SAP ERP."
    assert cypher == "MATCH (a:Application) RETURN a.name AS application"
    assert rows == rows_result
    assert llm_client.generate_with_tools.call_count == 3
    neo4j_client.execute_read.assert_called_once()
    log_fn.assert_called_once_with("query_correction_retry", {
        "reason": "no_tool_call_on_first_turn",
        "first_response": "SAP ERP und Webshop.",
    })


def test_run_tool_use_turn_executes_single_tool_call_and_returns_answer() -> None:
    tool_call = _make_tool_call("call_1", "MATCH (p:Process) RETURN p.name AS process")
    rows_result = [{"process": "Bestellabwicklung"}]

    llm_client = MagicMock()
    llm_client.generate_with_tools.side_effect = [
        ("", [tool_call]),
        ("Es gibt einen Process.", []),
    ]
    neo4j_client = MagicMock()
    neo4j_client.execute_read.return_value = rows_result

    messages = [{"role": "user", "content": "Welche Processe gibt es?"}]
    content, cypher, rows = _run_tool_use_turn(messages, llm_client, neo4j_client)

    assert content == "Es gibt einen Process."
    assert cypher == "MATCH (p:Process) RETURN p.name AS process"
    assert rows == rows_result
    neo4j_client.execute_read.assert_called_once()


def test_run_tool_use_turn_appends_tool_result_to_messages() -> None:
    tool_call = _make_tool_call("call_x", "MATCH (p:Process) RETURN count(p) AS cnt")
    llm_client = MagicMock()
    llm_client.generate_with_tools.side_effect = [
        ("", [tool_call]),
        ("Es gibt 5 Processe.", []),
    ]
    neo4j_client = MagicMock()
    neo4j_client.execute_read.return_value = [{"cnt": 5}]

    messages: list[dict] = [{"role": "user", "content": "Wie viele Processe?"}]
    _run_tool_use_turn(messages, llm_client, neo4j_client)

    roles = [m["role"] for m in messages]
    assert "tool" in roles
    tool_msg = next(m for m in messages if m["role"] == "tool")
    assert tool_msg["tool_call_id"] == "call_x"
    assert "[ABFRAGEERGEBNIS]" in tool_msg["content"]


def test_run_tool_use_turn_handles_unknown_tool_gracefully() -> None:
    tool_call = {"id": "call_u", "type": "function", "function": {"name": "unknown_tool", "arguments": "{}"}}
    llm_client = MagicMock()
    # After the unknown-tool error, the model may answer without a further tool call.
    # The correction retry fires once, then the third response is accepted.
    llm_client.generate_with_tools.side_effect = [
        ("", [tool_call]),
        ("Konnte nicht ausfuehren.", []),  # no tool call → correction injected
        ("Konnte nicht ausfuehren.", []),  # retry → still no tool call → accepted
    ]
    neo4j_client = MagicMock()

    messages = [{"role": "user", "content": "test"}]
    content, _, _ = _run_tool_use_turn(messages, llm_client, neo4j_client)

    assert content == "Konnte nicht ausfuehren."
    neo4j_client.execute_read.assert_not_called()
    tool_msg = next(m for m in messages if m["role"] == "tool")
    assert "Unknown tool" in tool_msg["content"]


def test_execute_cypher_tool_schema_has_required_structure() -> None:
    assert _EXECUTE_CYPHER_TOOL_SCHEMA["type"] == "function"
    fn = _EXECUTE_CYPHER_TOOL_SCHEMA["function"]
    assert fn["name"] == "execute_cypher"
    assert "query" in fn["parameters"]["properties"]
    assert "query" in fn["parameters"]["required"]

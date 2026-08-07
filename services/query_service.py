from __future__ import annotations

import json
import re
from typing import Callable

from core.app_config import AppConfig, resolve_project_path
from core.i18n import normalize_locale
from core.graph_schema import build_archimate_mapping_reference, build_query_schema_reference
from core.llm_client import LlmClientConfig, LlmClientError, OpenAICompatibleClient
from core.neo4j_utils import Neo4jConnectionError, Neo4jQueryError, QueryValidationError
from services.alias_service import lookup_alias_matches
from services.runtime_service import (
    CHAT_MESSAGES_STATE_KEY,
    append_chat_message,
    get_session_neo4j_client,
    write_debug_log,
)
import streamlit as st

MAX_HISTORY_MESSAGES = 20
MAX_CYPHER_RETRIES = 2
MAX_TOOL_CALLS_PER_TURN = 5

_RESPONSE_POLISH_PROMPT = """You are the final copy editor for an enterprise architecture assistant.
Return a complete rewritten version of the answer in the language of the user's most recent
natural-language message.

Hard requirements:
- Correct spelling, grammar, inflection, punctuation, and terminology throughout.
- Use one language consistently for ordinary prose and generic enterprise-architecture
  concepts. Correct accidental code-switched fragments and malformed localized terms.
- Preserve the supplied protected business-object names and identifiers exactly. Also preserve
  established business slang or industry jargon when intentionally used (for example, a
  standard term such as "Single Point of Failure"). Do not treat malformed or mixed-language
  standard terms as protected jargon.
- Preserve every fact, number, identifier, genuine proper name, uncertainty marker, and
  Markdown structure. Do not add, omit, or reinterpret information.
- Do not mention Cypher, schemas, databases, internal labels, or this editing instruction.

Return only the polished answer."""

_EXECUTE_CYPHER_TOOL_SCHEMA: dict = {
    "type": "function",
    "function": {
        "name": "execute_cypher",
        "description": (
            "Execute a read-only Cypher query against the enterprise architecture knowledge graph. "
            "Returns matching rows as a JSON array. On empty results may include alias hints."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "A valid, read-only Cypher MATCH...RETURN statement.",
                }
            },
            "required": ["query"],
        },
    },
}

_PROMPT_ONLY_QUERY_PROTOCOL = (
    "## How to query the graph\n"
    "\n"
    "When you need data from the graph to answer a question, output a single read-only Cypher\n"
    "query in a fenced code block and nothing else:\n"
    "\n"
    "```cypher\n"
    "MATCH ...\n"
    "RETURN ...\n"
    "```\n"
    "\n"
    "The query will be executed and the result returned to you as the next message. You then\n"
    "formulate your final answer based on that result.\n"
    "\n"
    "Rules for this protocol:\n"
    "- When outputting a query, output ONLY the ```cypher block — no explanation, no partial\n"
    "  answer, no surrounding text.\n"
    "- Output at most one ```cypher block per response.\n"
    "- After receiving the result, formulate your answer in natural language without any\n"
    "  ```cypher block. Do not mention Cypher, Neo4j, databases, or technical internals.\n"
    "- If the result is empty and alias hints are provided in the result message, use them to\n"
    "  decide whether to re-query with the canonical name or ask the user to clarify.\n"
    "- If you do not need to query the graph (clarification question, or enough context is\n"
    "  already in the conversation), respond directly without any ```cypher block."
)

_TOOL_USE_QUERY_PROTOCOL = (
    "## How to query the graph\n"
    "\n"
    "When you need data from the graph to answer a question, call the `execute_cypher` tool\n"
    "with a read-only Cypher query. The tool returns the matching rows as a JSON array.\n"
    "\n"
    "Rules for this protocol:\n"
    "- Call the tool only when you actually need graph data — not for clarification questions.\n"
    "- You may call the tool multiple times per turn if you need to refine or follow up.\n"
    "- After receiving the result, formulate your final answer in natural language.\n"
    "- Do not mention the tool, Cypher, Neo4j, databases, or technical internals in your answer.\n"
    "- If the result is empty and alias hints are provided, use them to refine your query\n"
    "  or ask the user to clarify.\n"
    "- If you do not need to query the graph, respond directly without calling the tool."
)


def run_query_chat_turn(question: str, config: AppConfig, response_locale: str | None = None) -> None:
    cypher_query = ""
    rows: list[dict] = []
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

        system_prompt = _build_chat_system_prompt(config, response_locale)
        all_messages = st.session_state.get(CHAT_MESSAGES_STATE_KEY, [])
        # Exclude the last message: query_tab already appended the current user question
        # before calling this function; we add it explicitly below to avoid duplication.
        history = _build_llm_history(all_messages[:-1] if all_messages else [])
        turn_messages: list[dict] = (
            [{"role": "system", "content": system_prompt}]
            + history
            + [{"role": "user", "content": question}]
        )

        if config.chat_mode == "tool-use":
            log_fn = lambda event, details: write_debug_log(config, event, details)
            final_response, cypher_query, rows = _run_tool_use_turn(
                turn_messages, llm_client, neo4j_client, log_fn, response_locale
            )
        else:
            final_response, cypher_query, rows = _run_prompt_only_turn(
                turn_messages, llm_client, neo4j_client, response_locale
            )
        final_response = _polish_response_language(
            llm_client,
            question,
            final_response,
            _collect_protected_names(rows),
        )

    except (LlmClientError, Neo4jConnectionError, Neo4jQueryError, QueryValidationError) as exc:
        write_debug_log(
            config,
            "query_error",
            {"question": question, "cypher_query": cypher_query, "error": str(exc)},
        )
        append_chat_message(
            "assistant",
            _translate_error_for_user(exc, response_locale or config.ui_locale),
            cypher_query=cypher_query,
        )
        return

    append_chat_message("assistant", final_response.strip(), cypher_query=cypher_query, rows=rows)


def _polish_response_language(
    llm_client: OpenAICompatibleClient,
    question: str,
    answer: str,
    protected_names: list[str] | None = None,
) -> str:
    """Run a constrained second pass that improves language without changing facts."""
    if not answer.strip():
        return answer
    messages = [
        {"role": "system", "content": _RESPONSE_POLISH_PROMPT},
        {
            "role": "user",
            "content": (
                f"User message (determines the target language):\n{question}\n\n"
                "Protected business-object names and identifiers "
                f"(preserve exactly):\n{json.dumps(protected_names or [], ensure_ascii=False)}\n\n"
                f"Answer to polish:\n{answer}"
            ),
        },
    ]
    try:
        polished = llm_client.generate_chat(messages).strip()
    except LlmClientError:
        return answer
    return polished or answer


def _collect_protected_names(rows: list[dict]) -> list[str]:
    """Return distinct string values from query results that must not be translated."""
    schema_terms = {
        "application",
        "process",
        "interface",
        "server",
        "orgunit",
        "role",
        "capability",
        "goal",
        "dataobject",
        "resource",
        "infrastructure",
        "risk",
    }
    names: list[str] = []
    seen: set[str] = set()
    for row in rows:
        for value in row.values():
            if not isinstance(value, str):
                continue
            name = value.strip()
            if not name or name.casefold() in schema_terms or name in seen:
                continue
            names.append(name)
            seen.add(name)
    return names


def _run_prompt_only_turn(
    turn_messages: list[dict],
    llm_client: OpenAICompatibleClient,
    neo4j_client,
    response_locale: str | None = None,
) -> tuple[str, str, list[dict]]:
    response = llm_client.generate_chat(turn_messages)
    cypher_query = _extract_cypher_from_response(response)

    if not cypher_query:
        return response.strip(), "", []

    turn_messages.append({"role": "assistant", "content": response})
    rows: list[dict] = []
    for attempt in range(MAX_CYPHER_RETRIES):
        try:
            rows = neo4j_client.execute_read(cypher_query)
            break
        except (QueryValidationError, Neo4jQueryError) as exc:
            if attempt == MAX_CYPHER_RETRIES - 1:
                raise
            error_feedback = (
                f"[ABFRAGEFEHLER]\n{str(exc)[:300]}\n\n"
                "Bitte korrigiere die Cypher-Abfrage und gib nur den korrigierten ```cypher-Block aus."
            )
            turn_messages.append({"role": "user", "content": error_feedback})
            response = llm_client.generate_chat(turn_messages)
            cypher_query = _extract_cypher_from_response(response) or cypher_query
            turn_messages.append({"role": "assistant", "content": response})

    alias_hints: list[str] = []
    if not rows:
        alias_hints = _collect_alias_hints(cypher_query, neo4j_client)

    result_message = _format_query_result(rows, alias_hints, response_locale)
    turn_messages.append({"role": "user", "content": result_message})
    final_response = llm_client.generate_chat(turn_messages)
    return final_response, cypher_query, rows


def _run_tool_use_turn(
    turn_messages: list[dict],
    llm_client: OpenAICompatibleClient,
    neo4j_client,
    log_fn: Callable[[str, dict], None] | None = None,
    response_locale: str | None = None,
) -> tuple[str, str, list[dict]]:
    cypher_query = ""
    rows: list[dict] = []
    query_reminder_sent = False

    for _ in range(MAX_TOOL_CALLS_PER_TURN):
        content, tool_calls = llm_client.generate_with_tools(turn_messages, [_EXECUTE_CYPHER_TOOL_SCHEMA])

        if not tool_calls:
            # Model answered without calling the tool. If no query has run yet in this
            # turn, inject a single correction and retry — the model may have answered
            # from training knowledge instead of querying the graph.
            if not cypher_query and not query_reminder_sent:
                query_reminder_sent = True
                if log_fn:
                    log_fn("query_correction_retry", {
                        "reason": "no_tool_call_on_first_turn",
                        "first_response": (content or "")[:300],
                    })
                turn_messages.append({"role": "assistant", "content": content or ""})
                turn_messages.append({
                    "role": "user",
                    "content": (
                        "[HINWEIS] Falls deine vorherige Antwort auf faktischen Daten zur "
                        "IT-Landschaft basiert, rufe bitte zuerst execute_cypher auf. "
                        "Falls es sich um eine Frage zu deinen Fähigkeiten, eine Begrüßung "
                        "oder eine Rückfrage handelt, kannst du direkt antworten."
                    ),
                })
                continue
            return content or "", cypher_query, rows

        turn_messages.append({"role": "assistant", "content": content or None, "tool_calls": tool_calls})

        for tool_call in tool_calls:
            tool_call_id = tool_call.get("id", "")
            fn = tool_call.get("function", {})

            if fn.get("name") != "execute_cypher":
                turn_messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call_id,
                    "content": '{"error": "Unknown tool"}',
                })
                continue

            try:
                args = json.loads(fn.get("arguments", "{}"))
                cypher_query = args.get("query", "").strip()
            except (json.JSONDecodeError, AttributeError):
                cypher_query = ""

            if not cypher_query:
                turn_messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call_id,
                    "content": '{"error": "No query provided"}',
                })
                continue

            try:
                rows = neo4j_client.execute_read(cypher_query)
                alias_hints = _collect_alias_hints(cypher_query, neo4j_client) if not rows else []
                result = _format_query_result(rows, alias_hints, response_locale)
            except (QueryValidationError, Neo4jQueryError) as exc:
                result = json.dumps({"error": str(exc)[:300]}, ensure_ascii=False)
                rows = []

            turn_messages.append({
                "role": "tool",
                "tool_call_id": tool_call_id,
                "content": result,
            })

    # Exhausted tool call budget — request final text answer
    content, _ = llm_client.generate_with_tools(turn_messages, [_EXECUTE_CYPHER_TOOL_SCHEMA])
    return content or "", cypher_query, rows


def _build_chat_system_prompt(config: AppConfig, response_locale: str | None = None) -> str:
    template = resolve_project_path("prompts/chat_system.md").read_text(encoding="utf-8")
    protocol = _TOOL_USE_QUERY_PROTOCOL if config.chat_mode == "tool-use" else _PROMPT_ONLY_QUERY_PROTOCOL
    return (
        template
        .replace("{GRAPH_QUERY_PROTOCOL}", protocol)
        .replace("{RESPONSE_LANGUAGE}", "the language of the user's most recent message")
        .replace("{ARCHIMATE_MAPPING}", build_archimate_mapping_reference())
        .replace("{GRAPH_SCHEMA_REFERENCE}", build_query_schema_reference())
    )


def _build_llm_history(chat_messages: list[dict]) -> list[dict[str, str]]:
    result = []
    for msg in chat_messages[-MAX_HISTORY_MESSAGES:]:
        role = str(msg.get("role", "")).strip()
        content = str(msg.get("content", "")).strip()
        if role and content:
            result.append({"role": role, "content": content})
    return result


def _extract_cypher_from_response(response_text: str) -> str:
    match = re.search(r"```(?:cypher)?\s*\n(.*?)```", response_text, re.DOTALL | re.IGNORECASE)
    if not match:
        return ""
    return match.group(1).strip()


def _collect_alias_hints(cypher_query: str, neo4j_client) -> list[str]:
    hints: list[str] = []
    seen: set[str] = set()
    for term in re.findall(r"'([^']{2,})'", cypher_query):
        for row in lookup_alias_matches(neo4j_client, term):
            entity_name = str(row.get("entity_name", "")).strip()
            entity_type = str(row.get("entity_type", "")).strip()
            key = f"{entity_type}:{entity_name}"
            if key not in seen and entity_name and entity_type:
                hints.append(f'"{term}" könnte sich auf "{entity_name}" ({entity_type}) beziehen')
                seen.add(key)
    return hints


def _format_query_result(rows: list[dict], alias_hints: list[str], response_locale: str | None = None) -> str:
    if normalize_locale(response_locale) == "en":
        if rows:
            return f"[QUERY_RESULT]\n{json.dumps(rows, ensure_ascii=False, indent=2)}"
        if alias_hints:
            hints_text = "\n".join(f"- {hint}" for hint in alias_hints)
            return f"[QUERY_RESULT]\nNo matches.\n\nPossible alternative terms in the knowledge graph:\n{hints_text}"
        return "[QUERY_RESULT]\nNo matches."
    if rows:
        return f"[ABFRAGEERGEBNIS]\n{json.dumps(rows, ensure_ascii=False, indent=2)}"
    if alias_hints:
        hints_text = "\n".join(f"- {h}" for h in alias_hints)
        return (
            f"[ABFRAGEERGEBNIS]\nKeine Treffer.\n\n"
            f"Hinweis — mögliche Alternativbegriffe im Wissensgraphen:\n{hints_text}"
        )
    return "[ABFRAGEERGEBNIS]\nKeine Treffer."


def _translate_error_for_user(exc: Exception, response_locale: str | None = None) -> str:
    if normalize_locale(response_locale) == "en":
        if isinstance(exc, QueryValidationError):
            return "I could not derive a valid read-only query from your question yet. Please phrase it more specifically."
        if isinstance(exc, Neo4jQueryError):
            return "I could not evaluate the question correctly against the current knowledge graph."
        if isinstance(exc, Neo4jConnectionError):
            return "I cannot reach the knowledge graph right now. Please check the Neo4j connection in Configuration."
        if isinstance(exc, LlmClientError):
            return "I could not process the question reliably right now. Please try again or phrase it more specifically."
        return "The request could not be processed right now."
    if isinstance(exc, QueryValidationError):
        normalized = str(exc).casefold()
        if "multiple statements" in normalized:
            return (
                "Ich konnte die Frage noch nicht in eine konsistente Abfrage uebersetzen. "
                "Bitte formulieren Sie die Frage etwas konkreter oder stellen Sie Teilfragen nacheinander."
            )
        if "forbidden token" in normalized:
            return (
                "Ich kann hier nur lesend auf den Wissensgraphen zugreifen. "
                "Die Frage wurde intern noch nicht passend in eine reine Leseabfrage uebersetzt."
            )
        return "Ich konnte aus Ihrer Frage noch keine gueltige Abfrage fuer den Wissensgraphen ableiten."
    if isinstance(exc, Neo4jQueryError):
        return "Ich konnte die Frage auf Basis des aktuellen Wissensgraphen noch nicht korrekt auswerten."
    if isinstance(exc, Neo4jConnectionError):
        return "Ich kann den Wissensgraphen im Moment nicht erreichen. Bitte pruefen Sie die Neo4j-Verbindung in der Konfiguration."
    if isinstance(exc, LlmClientError):
        return "Ich konnte die Frage im Moment nicht zuverlaessig verarbeiten. Bitte versuchen Sie es erneut oder formulieren Sie sie etwas konkreter."
    return "Die Anfrage konnte im Moment nicht verarbeitet werden."

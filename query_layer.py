from __future__ import annotations

import json
from pathlib import Path

from graph_schema import build_query_schema_reference
from llm_client import OpenAICompatibleClient
from neo4j_utils import Neo4jClient


def generate_cypher_from_question(question: str, llm_client: OpenAICompatibleClient, prompt_path: Path) -> str:
    system_prompt = prompt_path.read_text(encoding="utf-8").rstrip() + "\n\n" + build_query_schema_reference()
    raw_response = llm_client.generate_text(system_prompt=system_prompt, user_prompt=question)
    return sanitize_cypher_response(raw_response)


def sanitize_cypher_response(raw_response: str) -> str:
    cleaned_response = raw_response.strip()
    if cleaned_response.startswith("```"):
        lines = cleaned_response.splitlines()
        if lines:
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        cleaned_response = "\n".join(lines).strip()
    return cleaned_response


def build_natural_language_answer(
    question: str,
    cypher_query: str,
    rows: list[dict],
    llm_client: OpenAICompatibleClient,
    prompt_path: Path,
) -> str:
    if not rows:
        return "Ich habe dazu aktuell keine passenden Informationen im Wissensgraphen gefunden."

    system_prompt = prompt_path.read_text(encoding="utf-8")
    user_prompt = json.dumps(
        {
            "question": question,
            "cypher": cypher_query,
            "rows": rows,
        },
        ensure_ascii=False,
        indent=2,
    )
    return llm_client.generate_text(system_prompt=system_prompt, user_prompt=user_prompt).strip()


def answer_question(
    question: str,
    llm_client: OpenAICompatibleClient,
    neo4j_client: Neo4jClient,
    cypher_prompt_path: Path,
    answer_prompt_path: Path,
) -> tuple[str, str, list[dict]]:
    cypher_query = generate_cypher_from_question(question, llm_client, cypher_prompt_path)
    rows = neo4j_client.execute_read(cypher_query)
    answer_text = build_natural_language_answer(
        question=question,
        cypher_query=cypher_query,
        rows=rows,
        llm_client=llm_client,
        prompt_path=answer_prompt_path,
    )
    return answer_text, cypher_query, rows


def find_application_ambiguity_options(question: str, rows: list[dict]) -> list[str]:
    application_names = sorted(
        {
            application_name
            for row in rows
            for application_name in [_extract_application_name_from_row(row)]
            if application_name
        }
    )
    if len(application_names) < 2:
        return []
    if not should_request_application_clarification(question):
        return []
    return application_names


def should_request_application_clarification(question: str) -> bool:
    normalized_question = question.casefold()
    plural_markers = [
        "welche",
        "alle",
        "liste",
        "anwendungen",
        "produkte",
        "mehrere",
    ]
    return not any(marker in normalized_question for marker in plural_markers)


def resolve_application_clarification(user_message: str, options: list[str]) -> str | None:
    normalized_message = user_message.casefold().strip()
    exact_matches = [option for option in options if option.casefold() == normalized_message]
    if len(exact_matches) == 1:
        return exact_matches[0]

    partial_matches = [
        option
        for option in options
        if normalized_message and normalized_message in option.casefold()
    ]
    if len(partial_matches) == 1:
        return partial_matches[0]
    return None


def _extract_application_name_from_row(row: dict) -> str:
    for key in ("application", "application_name", "anwendung", "anwendung_name"):
        value = str(row.get(key, "")).strip()
        if value:
            return value
    return ""

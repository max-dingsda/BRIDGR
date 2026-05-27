from pathlib import Path

from graph_schema import build_query_schema_reference
from query_layer import (
    answer_question,
    find_application_ambiguity_options,
    generate_cypher_from_question,
    resolve_application_clarification,
)


class FakeLlmClient:
    def generate_text(self, system_prompt: str, user_prompt: str) -> str:
        if "question" in user_prompt and "rows" in user_prompt:
            return "Es gibt den Prozess Auftragsabwicklung im Wissensgraphen."
        return "MATCH (p:Prozess) RETURN p.name AS process_name"


class FakeNeo4jClient:
    def execute_read(self, query: str, parameters=None):
        return [{"process_name": "Auftragsabwicklung"}]


class PromptCapturingLlmClient:
    def __init__(self) -> None:
        self.system_prompt = ""

    def generate_text(self, system_prompt: str, user_prompt: str) -> str:
        self.system_prompt = system_prompt
        return "MATCH (p:Prozess) RETURN p.name AS process"


def test_answer_question_returns_cypher_and_rows(tmp_path: Path) -> None:
    cypher_prompt_path = tmp_path / "cypher_gen.md"
    answer_prompt_path = tmp_path / "answer_query.md"
    cypher_prompt_path.write_text("prompt", encoding="utf-8")
    answer_prompt_path.write_text("prompt", encoding="utf-8")

    answer_text, cypher_query, rows = answer_question(
        question="Welche Prozesse gibt es?",
        llm_client=FakeLlmClient(),
        neo4j_client=FakeNeo4jClient(),
        cypher_prompt_path=cypher_prompt_path,
        answer_prompt_path=answer_prompt_path,
    )

    assert answer_text == "Es gibt den Prozess Auftragsabwicklung im Wissensgraphen."
    assert "MATCH" in cypher_query
    assert rows == [{"process_name": "Auftragsabwicklung"}]


def test_generate_cypher_from_question_appends_runtime_schema_reference(tmp_path: Path) -> None:
    cypher_prompt_path = tmp_path / "cypher_gen.md"
    cypher_prompt_path.write_text(
        "Apply all explicit filters from the question directly in Cypher whenever possible.",
        encoding="utf-8",
    )
    llm_client = PromptCapturingLlmClient()

    cypher_query = generate_cypher_from_question(
        question="Welche Prozesse gibt es?",
        llm_client=llm_client,
        prompt_path=cypher_prompt_path,
    )

    assert cypher_query == "MATCH (p:Prozess) RETURN p.name AS process"
    assert build_query_schema_reference() in llm_client.system_prompt
    assert "Apply all explicit filters from the question directly in Cypher whenever possible." in llm_client.system_prompt


class FenceLlmClient:
    def __init__(self) -> None:
        self.calls = 0

    def generate_text(self, system_prompt: str, user_prompt: str) -> str:
        self.calls += 1
        if self.calls == 1:
            return "```cypher\nMATCH (p:Prozess) RETURN p.name AS process_name\n```"
        return "Der Prozess Auftragsabwicklung ist im Wissensgraphen vorhanden."


def test_answer_question_strips_markdown_code_fences(tmp_path: Path) -> None:
    cypher_prompt_path = tmp_path / "cypher_gen.md"
    answer_prompt_path = tmp_path / "answer_query.md"
    cypher_prompt_path.write_text("prompt", encoding="utf-8")
    answer_prompt_path.write_text("prompt", encoding="utf-8")

    answer_text, cypher_query, rows = answer_question(
        question="Welche Prozesse gibt es?",
        llm_client=FenceLlmClient(),
        neo4j_client=FakeNeo4jClient(),
        cypher_prompt_path=cypher_prompt_path,
        answer_prompt_path=answer_prompt_path,
    )

    assert answer_text == "Der Prozess Auftragsabwicklung ist im Wissensgraphen vorhanden."
    assert cypher_query == "MATCH (p:Prozess) RETURN p.name AS process_name"
    assert rows == [{"process_name": "Auftragsabwicklung"}]


class SequencedLlmClient:
    def __init__(self) -> None:
        self.calls = 0

    def generate_text(self, system_prompt: str, user_prompt: str) -> str:
        self.calls += 1
        if self.calls == 1:
            return "```cypher\nMATCH (p:Prozess) RETURN p.name AS process_name\n```"
        return "Der Wissensgraph kennt den Prozess Auftragsabwicklung."


def test_answer_question_builds_natural_language_answer(tmp_path: Path) -> None:
    cypher_prompt_path = tmp_path / "cypher_gen.md"
    answer_prompt_path = tmp_path / "answer_query.md"
    cypher_prompt_path.write_text("prompt", encoding="utf-8")
    answer_prompt_path.write_text("prompt", encoding="utf-8")

    answer_text, cypher_query, rows = answer_question(
        question="Welche Prozesse gibt es?",
        llm_client=SequencedLlmClient(),
        neo4j_client=FakeNeo4jClient(),
        cypher_prompt_path=cypher_prompt_path,
        answer_prompt_path=answer_prompt_path,
    )

    assert answer_text == "Der Wissensgraph kennt den Prozess Auftragsabwicklung."
    assert cypher_query == "MATCH (p:Prozess) RETURN p.name AS process_name"
    assert rows == [{"process_name": "Auftragsabwicklung"}]


def test_answer_question_returns_fallback_text_for_empty_results(tmp_path: Path) -> None:
    class EmptyNeo4jClient:
        def execute_read(self, query: str, parameters=None):
            return []

    cypher_prompt_path = tmp_path / "cypher_gen.md"
    answer_prompt_path = tmp_path / "answer_query.md"
    cypher_prompt_path.write_text("prompt", encoding="utf-8")
    answer_prompt_path.write_text("prompt", encoding="utf-8")

    answer_text, cypher_query, rows = answer_question(
        question="Welche Prozesse gibt es?",
        llm_client=FakeLlmClient(),
        neo4j_client=EmptyNeo4jClient(),
        cypher_prompt_path=cypher_prompt_path,
        answer_prompt_path=answer_prompt_path,
    )

    assert answer_text == "Ich habe dazu aktuell keine passenden Informationen im Wissensgraphen gefunden."
    assert cypher_query == "MATCH (p:Prozess) RETURN p.name AS process_name"
    assert rows == []


def test_find_application_ambiguity_options_returns_multiple_application_names_for_singular_question() -> None:
    rows = [
        {"application": "Adobe Reader", "process": "Bestellabwicklung"},
        {"application": "Adobe Professional", "process": "Rechnungseingang"},
    ]

    options = find_application_ambiguity_options("Wird Adobe genutzt?", rows)

    assert options == ["Adobe Professional", "Adobe Reader"]


def test_find_application_ambiguity_options_accepts_application_name_alias() -> None:
    rows = [
        {"application_name": "Mail System", "process": "Incident Management"},
        {"application_name": "Newsletter Mailer", "process": "Marketing"},
    ]

    options = find_application_ambiguity_options("Wird mail genutzt?", rows)

    assert options == ["Mail System", "Newsletter Mailer"]


def test_cypher_prompt_requires_concrete_application_for_name_filters(tmp_path: Path) -> None:
    prompt_path = tmp_path / "cypher_gen.md"
    prompt_path.write_text(Path("prompts/cypher_gen.md").read_text(encoding="utf-8"), encoding="utf-8")

    prompt_text = prompt_path.read_text(encoding="utf-8")

    assert "return the concrete matched application as `application`" in prompt_text


def test_find_application_ambiguity_options_skips_plural_questions() -> None:
    rows = [
        {"application": "Adobe Reader", "process": "Bestellabwicklung"},
        {"application": "Adobe Professional", "process": "Rechnungseingang"},
    ]

    options = find_application_ambiguity_options("Welche Adobe Produkte werden genutzt?", rows)

    assert options == []


def test_resolve_application_clarification_accepts_exact_and_partial_match() -> None:
    options = ["Adobe Reader", "Adobe Professional"]

    assert resolve_application_clarification("Adobe Reader", options) == "Adobe Reader"
    assert resolve_application_clarification("professional", options) == "Adobe Professional"
    assert resolve_application_clarification("Adobe", options) is None

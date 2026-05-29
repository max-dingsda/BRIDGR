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


class RepairingLlmClient:
    def __init__(self) -> None:
        self.calls = 0
        self.system_prompts: list[str] = []

    def generate_text(self, system_prompt: str, user_prompt: str) -> str:
        self.calls += 1
        self.system_prompts.append(system_prompt)
        if self.calls == 1:
            return "MATCH (a:Anwendung) RETURN count(a) AS applicationCount MATCH (p:Prozess) RETURN count(p) AS processCount"
        return "MATCH (a:Anwendung) WITH count(a) AS applicationCount MATCH (p:Prozess) RETURN applicationCount, count(p) AS processCount"


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
    assert "(:Anwendung)-[:RUNS_ON]->(:Server)" in llm_client.system_prompt
    assert "Never invent additional relationship types, labels, directions, or properties." in llm_client.system_prompt


def test_generate_cypher_from_question_retries_once_after_local_validation_error(tmp_path: Path) -> None:
    cypher_prompt_path = tmp_path / "cypher_gen.md"
    cypher_prompt_path.write_text("prompt", encoding="utf-8")
    llm_client = RepairingLlmClient()

    cypher_query = generate_cypher_from_question(
        question="Wie viele Anwendungen und Prozesse kennst du?",
        llm_client=llm_client,
        prompt_path=cypher_prompt_path,
    )

    assert cypher_query == "MATCH (a:Anwendung) WITH count(a) AS applicationCount MATCH (p:Prozess) RETURN applicationCount, count(p) AS processCount"
    assert llm_client.calls == 2
    assert "Validation error:" in llm_client.system_prompts[1]
    assert "Previous invalid Cypher:" in llm_client.system_prompts[1]


def test_generate_cypher_from_question_includes_follow_up_context_in_user_prompt(tmp_path: Path) -> None:
    cypher_prompt_path = tmp_path / "cypher_gen.md"
    cypher_prompt_path.write_text("prompt", encoding="utf-8")

    class ContextCapturingLlmClient:
        def __init__(self) -> None:
            self.user_prompt = ""

        def generate_text(self, system_prompt: str, user_prompt: str) -> str:
            self.user_prompt = user_prompt
            return "MATCH (s:Server) RETURN s.name AS server"

    llm_client = ContextCapturingLlmClient()

    generate_cypher_from_question(
        question="wieviele sind das jeweils?",
        llm_client=llm_client,
        prompt_path=cypher_prompt_path,
        conversation_messages=[
            {"role": "user", "content": "gibt es bei den servern eine unterscheidung zwischen physisch und virtuell?"},
            {"role": "assistant", "content": 'Ja, bei den Servern gibt es eine Unterscheidung; sie sind als "virtual" und "physical" eingestuft.'},
        ],
        focus_entity={"entity_type": "Server", "entity_name": "physical versus virtual"},
    )

    assert "conversation_history" in llm_client.user_prompt
    assert "current_focus_entity" in llm_client.user_prompt
    assert "current_question" in llm_client.user_prompt
    assert "physisch und virtuell" in llm_client.user_prompt


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
    assert "org_units_without_process_count" in prompt_text


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


def test_resolve_application_clarification_normalizes_type_words_and_quotes() -> None:
    options = ["Seller Service", "Seller Service Interface"]

    assert resolve_application_clarification('Ich meinte die Anwendung "Seller Service"', options) == "Seller Service"
    assert resolve_application_clarification("gemeint ist der prozess Seller Service", options) == "Seller Service"

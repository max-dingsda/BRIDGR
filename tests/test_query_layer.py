from pathlib import Path

from query_layer import answer_question


class FakeLlmClient:
    def generate_text(self, system_prompt: str, user_prompt: str) -> str:
        if "question" in user_prompt and "rows" in user_prompt:
            return "Es gibt den Prozess Auftragsabwicklung im Wissensgraphen."
        return "MATCH (p:Prozess) RETURN p.name AS process_name"


class FakeNeo4jClient:
    def execute_read(self, query: str, parameters=None):
        return [{"process_name": "Auftragsabwicklung"}]


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

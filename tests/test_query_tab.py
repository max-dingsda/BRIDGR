from pathlib import Path

from ui import query_tab


def test_has_no_matches_uses_stored_rows_not_table_visibility() -> None:
    message = {"role": "assistant", "cypher_query": "MATCH (p:Process) RETURN p.name", "table_visible": False}

    assert query_tab._has_no_matches(message, [{"process": "Forecast aktualisieren"}]) is False
    assert query_tab._has_no_matches(message, []) is True


def test_diagram_state_keeps_an_unavailable_result_distinct_from_a_new_request() -> None:
    assert query_tab._diagram_state({}) == "not_requested"
    assert query_tab._diagram_state({"diagram_html": ""}) == "unavailable"
    assert query_tab._diagram_state({"diagram_html": "Output/chat-diagrams/chat-1/diagram.html"}) == "ready"


def test_render_interactive_diagram_embeds_standalone_html(tmp_path: Path, monkeypatch) -> None:
    artifact = tmp_path / "diagram.html"
    artifact.write_text("<html><body><button>Zoom</button></body></html>", encoding="utf-8")
    captured: dict[str, object] = {}

    def fake_html(document: str, *, height: int, scrolling: bool) -> None:
        captured.update(document=document, height=height, scrolling=scrolling)

    monkeypatch.setattr(query_tab.components, "html", fake_html)

    assert query_tab._render_interactive_diagram(str(artifact)) is True
    assert captured == {
        "document": "<html><body><button>Zoom</button></body></html>",
        "height": query_tab._INTERACTIVE_DIAGRAM_HEIGHT,
        "scrolling": True,
    }


def test_render_interactive_diagram_returns_false_for_missing_artifact() -> None:
    assert query_tab._render_interactive_diagram("missing-diagram.html") is False

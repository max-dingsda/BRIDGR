from pathlib import Path

from ui import query_tab


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

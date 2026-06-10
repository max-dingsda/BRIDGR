from pathlib import Path
import types

import pytest

from skills.extract.extract_docx import DocxExtractor, DocxExtractorError


class FakeLlmClient:
    def generate_json(self, system_prompt: str, user_prompt: str) -> dict:
        return {
            "prozess": "Bestellabwicklung",
            "prozess_id": "",
            "org_einheit": "Einkauf",
            "folgt_auf": [],
            "anwendungen": [
                {"name": "Microsoft Outlook", "konfidenz": "stark"},
            ],
        }


def test_docx_extractor_reads_paragraphs_and_tables(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source_path = tmp_path / "process.docx"
    prompt_path = tmp_path / "prompt.md"
    source_path.write_bytes(b"docx")
    prompt_path.write_text("prompt", encoding="utf-8")

    class FakeParagraph:
        def __init__(self, text: str) -> None:
            self.text = text

    class FakeCell:
        def __init__(self, text: str) -> None:
            self.text = text

    class FakeRow:
        def __init__(self, cells) -> None:
            self.cells = cells

    class FakeTable:
        def __init__(self, rows) -> None:
            self.rows = rows

    class FakeDocument:
        def __init__(self, path: str) -> None:
            self.paragraphs = [FakeParagraph("Bestellabwicklung nutzt Outlook.")]
            self.tables = [FakeTable([FakeRow([FakeCell("ERP"), FakeCell("CRM")])])]

    fake_docx_module = types.ModuleType("docx")
    fake_docx_module.Document = FakeDocument
    monkeypatch.setitem(__import__("sys").modules, "docx", fake_docx_module)

    extractor = DocxExtractor(prompt_path=prompt_path, llm_client=FakeLlmClient())
    result = extractor.extract(source_path)

    assert result.process_name == "Bestellabwicklung"
    assert result.process_id == "process"
    assert result.applications[0].name == "Microsoft Outlook"


def test_docx_extractor_rejects_documents_without_text(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source_path = tmp_path / "process.docx"
    prompt_path = tmp_path / "prompt.md"
    source_path.write_bytes(b"docx")
    prompt_path.write_text("prompt", encoding="utf-8")

    class EmptyDocument:
        def __init__(self, path: str) -> None:
            self.paragraphs = []
            self.tables = []

    fake_docx_module = types.ModuleType("docx")
    fake_docx_module.Document = EmptyDocument
    monkeypatch.setitem(__import__("sys").modules, "docx", fake_docx_module)

    extractor = DocxExtractor(prompt_path=prompt_path, llm_client=FakeLlmClient())

    with pytest.raises(DocxExtractorError, match="did not contain extractable text"):
        extractor.extract(source_path)


def test_docx_extractor_splits_comma_separated_roles_and_org_candidates(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source_path = tmp_path / "process.docx"
    prompt_path = tmp_path / "prompt.md"
    source_path.write_bytes(b"docx")
    prompt_path.write_text("prompt", encoding="utf-8")

    class FakeParagraph:
        def __init__(self, text: str) -> None:
            self.text = text

    class FakeDocument:
        def __init__(self, path: str) -> None:
            self.paragraphs = [FakeParagraph("Beteiligte: Buchhaltung, Controlling")]
            self.tables = []

    class CombinedLlmClient:
        def generate_json(self, system_prompt: str, user_prompt: str) -> dict:
            return {
                "prozess": "Zahlungsabwicklung",
                "prozess_id": "",
                "rolle": "Buchhaltung, Controlling",
                "prozess_eigentuemer": "",
                "org_einheit_kandidaten": ["Buchhaltung, Auftragsbearbeitung"],
                "folgt_auf": [],
                "anwendungen": [],
            }

    fake_docx_module = types.ModuleType("docx")
    fake_docx_module.Document = FakeDocument
    monkeypatch.setitem(__import__("sys").modules, "docx", fake_docx_module)

    extractor = DocxExtractor(prompt_path=prompt_path, llm_client=CombinedLlmClient())
    result = extractor.extract(source_path)

    assert result.roles == ["Buchhaltung", "Controlling"]
    assert result.org_unit_candidates == ["Buchhaltung", "Auftragsbearbeitung"]

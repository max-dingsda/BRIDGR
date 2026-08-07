from pathlib import Path
import types

import pytest

from skills.extract.extract_pdf import PdfExtractor, PdfExtractorError


class FakeLlmClient:
    def generate_json(self, system_prompt: str, user_prompt: str) -> dict:
        return {
            "process": "Incident Management",
            "process_id": "",
            "org_unit": "Support",
            "follows_after": [],
            "applications": [
                {"name": "Mail System", "confidence": "schwach"},
            ],
        }


def test_pdf_extractor_reads_page_text(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source_path = tmp_path / "process.pdf"
    prompt_path = tmp_path / "prompt.md"
    source_path.write_bytes(b"pdf")
    prompt_path.write_text("prompt", encoding="utf-8")

    class FakePage:
        def __init__(self, text: str) -> None:
            self._text = text

        def extract_text(self) -> str:
            return self._text

    class FakeReader:
        def __init__(self, path: str) -> None:
            self.pages = [FakePage("Incident Management uses mail.")]

    fake_pypdf_module = types.ModuleType("pypdf")
    fake_pypdf_module.PdfReader = FakeReader
    monkeypatch.setitem(__import__("sys").modules, "pypdf", fake_pypdf_module)

    extractor = PdfExtractor(prompt_path=prompt_path, llm_client=FakeLlmClient())
    result = extractor.extract(source_path)

    assert result.process_name == "Incident Management"
    assert result.process_id == "process"
    assert result.applications[0].name == "Mail System"


def test_pdf_extractor_rejects_documents_without_text(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source_path = tmp_path / "process.pdf"
    prompt_path = tmp_path / "prompt.md"
    source_path.write_bytes(b"pdf")
    prompt_path.write_text("prompt", encoding="utf-8")

    class EmptyPage:
        def extract_text(self) -> str:
            return ""

    class EmptyReader:
        def __init__(self, path: str) -> None:
            self.pages = [EmptyPage()]

    fake_pypdf_module = types.ModuleType("pypdf")
    fake_pypdf_module.PdfReader = EmptyReader
    monkeypatch.setitem(__import__("sys").modules, "pypdf", fake_pypdf_module)

    extractor = PdfExtractor(prompt_path=prompt_path, llm_client=FakeLlmClient())

    with pytest.raises(PdfExtractorError, match="did not contain extractable text"):
        extractor.extract(source_path)


def test_pdf_extractor_splits_comma_separated_roles_and_org_candidates(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source_path = tmp_path / "process.pdf"
    prompt_path = tmp_path / "prompt.md"
    source_path.write_bytes(b"pdf")
    prompt_path.write_text("prompt", encoding="utf-8")

    class FakePage:
        def extract_text(self) -> str:
            return "Beteiligte: Buchhaltung, Auftragsbearbeitung"

    class FakeReader:
        def __init__(self, path: str) -> None:
            self.pages = [FakePage()]

    class CombinedLlmClient:
        def generate_json(self, system_prompt: str, user_prompt: str) -> dict:
            return {
                "process": "Rechnungsstellung",
                "process_id": "",
                "role": "Buchhaltung, Auftragsbearbeitung",
                "process_owner": "",
                "org_unit_candidates": ["Buchhaltung, Controlling"],
                "follows_after": [],
                "applications": [],
            }

    fake_pypdf_module = types.ModuleType("pypdf")
    fake_pypdf_module.PdfReader = FakeReader
    monkeypatch.setitem(__import__("sys").modules, "pypdf", fake_pypdf_module)

    extractor = PdfExtractor(prompt_path=prompt_path, llm_client=CombinedLlmClient())
    result = extractor.extract(source_path)

    assert result.roles == ["Buchhaltung", "Auftragsbearbeitung"]
    assert result.org_unit_candidates == ["Buchhaltung", "Controlling"]

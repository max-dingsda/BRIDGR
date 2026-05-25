from pathlib import Path

import pytest

from skills.extract.extract_txt import TextExtractor, TextExtractorError


class FakeLlmClient:
    def generate_json(self, system_prompt: str, user_prompt: str) -> dict:
        return {
            "prozess": "Incident Handling",
            "prozess_id": "",
            "org_einheit": "Support",
            "folgt_auf": ["Ticket Intake"],
            "anwendungen": [
                {"name": "Ticket System", "konfidenz": "stark"},
                {"name": "Mail Service", "konfidenz": "schwach"},
            ],
        }


def test_text_extractor_returns_domain_model(tmp_path: Path) -> None:
    source_path = tmp_path / "process.txt"
    prompt_path = tmp_path / "prompt.md"
    source_path.write_text("Incident Handling uses Ticket System.", encoding="utf-8")
    prompt_path.write_text("prompt", encoding="utf-8")

    extractor = TextExtractor(prompt_path=prompt_path, llm_client=FakeLlmClient())
    result = extractor.extract(source_path)

    assert result.process_name == "Incident Handling"
    assert result.process_id == "process"
    assert [application.name for application in result.raw_applications] == [
        "Ticket System",
        "Mail Service",
    ]
    assert [application.name for application in result.applications] == [
        "Ticket System",
        "Mail Service",
    ]


def test_text_extractor_uses_payload_process_id_when_present(tmp_path: Path) -> None:
    source_path = tmp_path / "process.txt"
    prompt_path = tmp_path / "prompt.md"
    source_path.write_text("Incident Handling uses Ticket System.", encoding="utf-8")
    prompt_path.write_text("prompt", encoding="utf-8")

    class ProcessIdLlmClient(FakeLlmClient):
        def generate_json(self, system_prompt: str, user_prompt: str) -> dict:
            payload = super().generate_json(system_prompt, user_prompt)
            payload["prozess_id"] = "text-001"
            return payload

    extractor = TextExtractor(prompt_path=prompt_path, llm_client=ProcessIdLlmClient())
    result = extractor.extract(source_path)

    assert result.process_id == "text-001"


def test_text_extractor_rejects_invalid_payload(tmp_path: Path) -> None:
    source_path = tmp_path / "process.txt"
    prompt_path = tmp_path / "prompt.md"
    source_path.write_text("text", encoding="utf-8")
    prompt_path.write_text("prompt", encoding="utf-8")

    class InvalidLlmClient:
        def generate_json(self, system_prompt: str, user_prompt: str) -> dict:
            return {"prozess": "Broken"}

    extractor = TextExtractor(prompt_path=prompt_path, llm_client=InvalidLlmClient())

    with pytest.raises(TextExtractorError):
        extractor.extract(source_path)

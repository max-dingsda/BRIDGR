from pathlib import Path

import pytest

from skills.extract.extract_bpmn import BpmnExtractor, BpmnExtractorError


class FakeLlmClient:
    def generate_json(self, system_prompt: str, user_prompt: str) -> dict:
        return {
            "prozess": "Auftragsabwicklung",
            "prozess_id": "proc_001",
            "org_einheit": "Vertrieb",
            "folgt_auf": ["Angebotserstellung"],
            "anwendungen": [
                {"name": "SAP SD", "konfidenz": "stark"},
            ],
        }


def test_bpmn_extractor_returns_domain_model(tmp_path: Path) -> None:
    source_path = tmp_path / "process.bpmn"
    prompt_path = tmp_path / "prompt.md"
    source_path.write_text("<definitions><process id='proc_001' /></definitions>", encoding="utf-8")
    prompt_path.write_text("prompt", encoding="utf-8")

    extractor = BpmnExtractor(prompt_path=prompt_path, llm_client=FakeLlmClient())
    result = extractor.extract(source_path)

    assert result.process_name == "Auftragsabwicklung"
    assert result.process_id == "proc_001"
    assert result.applications[0].name == "SAP SD"


def test_bpmn_extractor_rejects_invalid_xml(tmp_path: Path) -> None:
    source_path = tmp_path / "process.bpmn"
    prompt_path = tmp_path / "prompt.md"
    source_path.write_text("<definitions>", encoding="utf-8")
    prompt_path.write_text("prompt", encoding="utf-8")

    extractor = BpmnExtractor(prompt_path=prompt_path, llm_client=FakeLlmClient())

    with pytest.raises(BpmnExtractorError):
        extractor.extract(source_path)

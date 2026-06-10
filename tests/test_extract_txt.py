from pathlib import Path

import pytest

from skills.extract.extract_txt import TextExtractor, TextExtractorError


class FakeLlmClient:
    def generate_json(self, system_prompt: str, user_prompt: str) -> dict:
        return {
            "prozess": "Incident Handling",
            "prozess_id": "",
            "rolle": "Support",
            "org_einheit_kandidaten": ["Support Team"],
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
    assert result.roles == ["Support"]
    assert result.org_units == []
    assert result.org_unit_candidates == ["Support Team"]
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


def test_text_extractor_prefers_explicit_process_id_from_document_text(tmp_path: Path) -> None:
    source_path = tmp_path / "process.txt"
    prompt_path = tmp_path / "prompt.md"
    source_path.write_text(
        "BRIDGR BPMN Transform\n\nProcess Name: Incident Handling\nProcess ID: _cd26e6af-958f-8ed4-29e2-a0a586ee7850\n",
        encoding="utf-8",
    )
    prompt_path.write_text("prompt", encoding="utf-8")

    class MutatingProcessIdLlmClient(FakeLlmClient):
        def generate_json(self, system_prompt: str, user_prompt: str) -> dict:
            payload = super().generate_json(system_prompt, user_prompt)
            payload["prozess_id"] = "c d26e6af-958f-8ed4-29e2-a0a586ee7850"
            return payload

    extractor = TextExtractor(prompt_path=prompt_path, llm_client=MutatingProcessIdLlmClient())
    result = extractor.extract(source_path)

    assert result.process_id == "_cd26e6af-958f-8ed4-29e2-a0a586ee7850"
    assert result.roles == []
    assert result.org_unit_candidates == []


def test_text_extractor_reads_lane_labels_from_bpmn_transform_text_as_roles(tmp_path: Path) -> None:
    source_path = tmp_path / "process.txt"
    prompt_path = tmp_path / "prompt.md"
    source_path.write_text(
        "BRIDGR BPMN Transform\nSource File: A.bpmn\n\nProcess Name: Incident Handling\nProcess ID: proc-1\nLane Labels: Support, Service Desk\nApplications: none\n",
        encoding="utf-8",
    )
    prompt_path.write_text("prompt", encoding="utf-8")

    extractor = TextExtractor(prompt_path=prompt_path, llm_client=FakeLlmClient())
    result = extractor.extract(source_path)

    assert result.roles == ["Support", "Service Desk"]
    assert result.org_unit_candidates == []


def test_text_extractor_extracts_explicit_process_owner(tmp_path: Path) -> None:
    source_path = tmp_path / "process.txt"
    prompt_path = tmp_path / "prompt.md"
    source_path.write_text("Prozessverantwortlicher: Einkauf", encoding="utf-8")
    prompt_path.write_text("prompt", encoding="utf-8")

    class OwnerLlmClient:
        def generate_json(self, system_prompt: str, user_prompt: str) -> dict:
            return {
                "prozess": "Bestellabwicklung",
                "prozess_id": "",
                "rolle": "",
                "prozess_eigentuemer": "Einkauf",
                "org_einheit_kandidaten": [],
                "folgt_auf": [],
                "anwendungen": [],
            }

    extractor = TextExtractor(prompt_path=prompt_path, llm_client=OwnerLlmClient())
    result = extractor.extract(source_path)

    assert result.process_owner_candidate == "Einkauf"


def test_text_extractor_returns_empty_process_owner_when_not_stated(tmp_path: Path) -> None:
    source_path = tmp_path / "process.txt"
    prompt_path = tmp_path / "prompt.md"
    source_path.write_text("Incident Handling uses Ticket System.", encoding="utf-8")
    prompt_path.write_text("prompt", encoding="utf-8")

    extractor = TextExtractor(prompt_path=prompt_path, llm_client=FakeLlmClient())
    result = extractor.extract(source_path)

    assert result.process_owner_candidate == ""


def test_text_extractor_ignores_process_owner_in_bpmn_transform(tmp_path: Path) -> None:
    source_path = tmp_path / "process.txt"
    prompt_path = tmp_path / "prompt.md"
    source_path.write_text(
        "BRIDGR BPMN Transform\nProcess Name: Bestellabwicklung\nProcess ID: proc-1\nLane Labels: Einkauf\n",
        encoding="utf-8",
    )
    prompt_path.write_text("prompt", encoding="utf-8")

    class OwnerLlmClient:
        def generate_json(self, system_prompt: str, user_prompt: str) -> dict:
            return {
                "prozess": "Bestellabwicklung",
                "prozess_id": "proc-1",
                "rolle": "",
                "prozess_eigentuemer": "Einkauf",
                "org_einheit_kandidaten": [],
                "folgt_auf": [],
                "anwendungen": [],
            }

    extractor = TextExtractor(prompt_path=prompt_path, llm_client=OwnerLlmClient())
    result = extractor.extract(source_path)

    assert result.process_owner_candidate == ""


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


def test_text_extractor_splits_comma_separated_roles_and_org_candidates(tmp_path: Path) -> None:
    source_path = tmp_path / "process.txt"
    prompt_path = tmp_path / "prompt.md"
    source_path.write_text("Beteiligte:\n- Buchhaltung\n- Auftragsbearbeitung", encoding="utf-8")
    prompt_path.write_text("prompt", encoding="utf-8")

    class CombinedLlmClient:
        def generate_json(self, system_prompt: str, user_prompt: str) -> dict:
            return {
                "prozess": "Rechnungsstellung",
                "prozess_id": "",
                "rolle": "Buchhaltung, Auftragsbearbeitung",
                "prozess_eigentuemer": "",
                "org_einheit_kandidaten": ["Buchhaltung, Controlling"],
                "folgt_auf": [],
                "anwendungen": [],
            }

    extractor = TextExtractor(prompt_path=prompt_path, llm_client=CombinedLlmClient())
    result = extractor.extract(source_path)

    assert result.roles == ["Buchhaltung", "Auftragsbearbeitung"]
    assert result.org_unit_candidates == ["Buchhaltung", "Controlling"]

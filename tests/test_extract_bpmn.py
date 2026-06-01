from pathlib import Path

import pytest

from skills.extract.extract_bpmn import BpmnExtractor, BpmnExtractorError


class FakeLlmClient:
    def generate_json(self, system_prompt: str, user_prompt: str) -> dict:
        return {
            "prozess": "Auftragsabwicklung",
            "prozess_id": "proc_001",
            "rollen": ["Vertrieb", "Einkauf"],
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
    assert result.roles == ["Vertrieb", "Einkauf"]
    assert result.org_units == []
    assert result.org_unit_candidates == []
    assert result.raw_applications[0].name == "SAP SD"
    assert result.applications[0].name == "SAP SD"


def test_bpmn_extractor_returns_empty_roles_when_no_lanes(tmp_path: Path) -> None:
    source_path = tmp_path / "process.bpmn"
    prompt_path = tmp_path / "prompt.md"
    source_path.write_text("<definitions><process id='proc_002' /></definitions>", encoding="utf-8")
    prompt_path.write_text("prompt", encoding="utf-8")

    class NoLanesClient:
        def generate_json(self, system_prompt: str, user_prompt: str) -> dict:
            return {
                "prozess": "Einfacher Prozess",
                "prozess_id": "proc_002",
                "rollen": [],
                "folgt_auf": [],
                "anwendungen": [],
            }

    extractor = BpmnExtractor(prompt_path=prompt_path, llm_client=NoLanesClient())
    result = extractor.extract(source_path)

    assert result.roles == []


def test_bpmn_extractor_deduplicates_roles(tmp_path: Path) -> None:
    source_path = tmp_path / "process.bpmn"
    prompt_path = tmp_path / "prompt.md"
    source_path.write_text("<definitions><process id='proc_003' /></definitions>", encoding="utf-8")
    prompt_path.write_text("prompt", encoding="utf-8")

    class DuplicateRolesClient:
        def generate_json(self, system_prompt: str, user_prompt: str) -> dict:
            return {
                "prozess": "Prozess mit Duplikaten",
                "prozess_id": "proc_003",
                "rollen": ["Sales Team", "sales team", "Einkauf"],
                "folgt_auf": [],
                "anwendungen": [],
            }

    extractor = BpmnExtractor(prompt_path=prompt_path, llm_client=DuplicateRolesClient())
    result = extractor.extract(source_path)

    assert result.roles == ["Sales Team", "Einkauf"]


def test_bpmn_extractor_rejects_invalid_xml(tmp_path: Path) -> None:
    source_path = tmp_path / "process.bpmn"
    prompt_path = tmp_path / "prompt.md"
    source_path.write_text("<definitions>", encoding="utf-8")
    prompt_path.write_text("prompt", encoding="utf-8")

    extractor = BpmnExtractor(prompt_path=prompt_path, llm_client=FakeLlmClient())

    with pytest.raises(BpmnExtractorError):
        extractor.extract(source_path)


class DuplicateApplicationLlmClient:
    def generate_json(self, system_prompt: str, user_prompt: str) -> dict:
        return {
            "prozess": "Incident Management",
            "prozess_id": "WFP-1-1",
            "rollen": ["Support"],
            "folgt_auf": [],
            "anwendungen": [
                {"name": "Product Backlog Interface (com.camunda.examples.incidentmanagement.ProductBacklog)", "konfidenz": "stark"},
                {"name": "ProductBacklog (com.camunda.examples.incidentmanagement.ProductBacklog)", "konfidenz": "stark"},
                {"name": "sendMailToIssueReporterOperation", "konfidenz": "schwach"},
            ],
        }


def test_bpmn_extractor_prefers_modeled_application_name_and_deduplicates_variants(tmp_path: Path) -> None:
    source_path = tmp_path / "process.bpmn"
    prompt_path = tmp_path / "prompt.md"
    source_path.write_text("<definitions><process id='WFP-1-1' /></definitions>", encoding="utf-8")
    prompt_path.write_text("prompt", encoding="utf-8")

    extractor = BpmnExtractor(prompt_path=prompt_path, llm_client=DuplicateApplicationLlmClient())
    result = extractor.extract(source_path)

    assert [application.name for application in result.raw_applications] == [
        "Product Backlog Interface (com.camunda.examples.incidentmanagement.ProductBacklog)",
        "ProductBacklog (com.camunda.examples.incidentmanagement.ProductBacklog)",
        "sendMailToIssueReporterOperation",
    ]
    assert [application.name for application in result.applications] == [
        "Product Backlog Interface",
    ]

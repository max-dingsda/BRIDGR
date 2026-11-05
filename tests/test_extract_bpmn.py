from pathlib import Path

import pytest

from skills.extract.extract_bpmn import BpmnExtractor, BpmnExtractorError


class FakeLlmClient:
    def generate_json(self, system_prompt: str, user_prompt: str) -> dict:
        return {
            "process": "Auftragsabwicklung",
            "process_id": "proc_001",
            "roles": ["Vertrieb", "Einkauf"],
            "follows_after": ["Angebotserstellung"],
            "applications": [
                {"name": "SAP SD", "confidence": "stark"},
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
                "process": "Einfacher Process",
                "process_id": "proc_002",
                "roles": [],
                "follows_after": [],
                "applications": [],
            }

    extractor = BpmnExtractor(prompt_path=prompt_path, llm_client=NoLanesClient())
    result = extractor.extract(source_path)

    assert result.roles == []


def test_bpmn_extractor_extracts_each_process_with_isolated_context(tmp_path: Path) -> None:
    source_path = tmp_path / "multiple.bpmn"
    prompt_path = tmp_path / "prompt.md"
    source_path.write_text(
        """<bpmn:definitions xmlns:bpmn="http://www.omg.org/spec/BPMN/20100524/MODEL">
  <bpmn:process id="sales" name="Sales"><bpmn:laneSet><bpmn:lane name="Sales" /></bpmn:laneSet></bpmn:process>
  <bpmn:process id="purchasing" name="Purchasing"><bpmn:laneSet><bpmn:lane name="Purchasing" /></bpmn:laneSet></bpmn:process>
  <bpmn:collaboration><bpmn:participant name="Sales Portal" processRef="sales" /><bpmn:participant name="Buying API" processRef="purchasing" /></bpmn:collaboration>
</bpmn:definitions>""",
        encoding="utf-8",
    )
    prompt_path.write_text("prompt", encoding="utf-8")

    class ProcessScopedLlmClient:
        def __init__(self) -> None:
            self.prompts: list[str] = []

        def generate_json(self, system_prompt: str, user_prompt: str) -> dict:
            self.prompts.append(user_prompt)
            if 'id="sales"' in user_prompt:
                return {"process": "Sales", "process_id": "ignored", "roles": ["Sales"], "applications": [{"name": "Sales Portal", "confidence": "stark"}]}
            return {"process": "Purchasing", "process_id": "ignored", "roles": ["Purchasing"], "applications": [{"name": "Buying API", "confidence": "stark"}]}

    llm_client = ProcessScopedLlmClient()
    results = BpmnExtractor(prompt_path=prompt_path, llm_client=llm_client).extract_many(source_path)

    assert [result.process_id for result in results] == ["sales", "purchasing"]
    assert [application.name for application in results[0].applications] == ["Sales Portal"]
    assert [application.name for application in results[1].applications] == ["Buying API"]
    assert 'Buying API' not in llm_client.prompts[0]
    assert 'Sales Portal' not in llm_client.prompts[1]


def test_bpmn_extractor_deduplicates_roles(tmp_path: Path) -> None:
    source_path = tmp_path / "process.bpmn"
    prompt_path = tmp_path / "prompt.md"
    source_path.write_text("<definitions><process id='proc_003' /></definitions>", encoding="utf-8")
    prompt_path.write_text("prompt", encoding="utf-8")

    class DuplicateRolesClient:
        def generate_json(self, system_prompt: str, user_prompt: str) -> dict:
            return {
                "process": "Process mit Duplikaten",
                "process_id": "proc_003",
                "roles": ["Sales Team", "sales team", "Einkauf"],
                "follows_after": [],
                "applications": [],
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
            "process": "Incident Management",
            "process_id": "WFP-1-1",
            "roles": ["Support"],
            "follows_after": [],
            "applications": [
                {"name": "Product Backlog Interface (com.camunda.examples.incidentmanagement.ProductBacklog)", "confidence": "stark"},
                {"name": "ProductBacklog (com.camunda.examples.incidentmanagement.ProductBacklog)", "confidence": "stark"},
                {"name": "sendMailToIssueReporterOperation", "confidence": "schwach"},
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

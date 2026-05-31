from pathlib import Path

import pytest

from app_config import AppConfig
from neo4j_utils import Neo4jServiceUnavailableError
from pipeline import (
    apply_org_unit_mapping,
    build_extractor_for_path,
    list_bpmn_files,
    resolve_cmdb_owner_assignments,
    run_document,
    run_pipeline,
    should_skip_file,
    update_organization_knowledge_from_cmdb,
)
from run_artifacts import LATEST_RUN_FILENAME, STATE_FILENAME
from skills.graph_writer import GraphWriter
from skills.extract.extract_base import ApplicationReference, ExtractedProcess
from skills.extract.extract_bpmn import BpmnExtractor
from skills.extract.extract_docx import DocxExtractor
from skills.extract.extract_pdf import PdfExtractor
from skills.extract.extract_txt import TextExtractor
from knowledge_base import KnowledgeBase


class FakeLlmClient:
    def generate_json(self, system_prompt: str, user_prompt: str) -> dict:
        return {
            "prozess": "Auftragsabwicklung",
            "prozess_id": "proc_001",
            "org_einheit": "Vertrieb",
            "folgt_auf": ["Angebotserstellung"],
            "anwendungen": [
                {"name": "SAP Sales", "konfidenz": "stark"},
                {"name": "Unbekanntes System", "konfidenz": "schwach"},
            ],
        }


def test_list_bpmn_files_returns_supported_process_documents(tmp_path: Path) -> None:
    (tmp_path / "a.bpmn").write_text("<definitions />", encoding="utf-8")
    (tmp_path / "c.xml").write_text("<definitions />", encoding="utf-8")
    (tmp_path / "b.txt").write_text("incident text", encoding="utf-8")

    result = list_bpmn_files(tmp_path)

    assert result == [tmp_path / "a.bpmn", tmp_path / "b.txt", tmp_path / "c.xml"]


def test_build_extractor_for_path_uses_text_extractor_for_txt(monkeypatch, tmp_path: Path) -> None:
    prompt_path = tmp_path / "prompts" / "extract_generic.md"
    prompt_path.parent.mkdir()
    prompt_path.write_text("prompt", encoding="utf-8")
    monkeypatch.setattr("app_config.PROJECT_ROOT", tmp_path)

    extractor = build_extractor_for_path(tmp_path / "process.txt", object())

    assert isinstance(extractor, TextExtractor)


def test_build_extractor_for_path_uses_docx_extractor_for_docx(monkeypatch, tmp_path: Path) -> None:
    prompt_path = tmp_path / "prompts" / "extract_generic.md"
    prompt_path.parent.mkdir()
    prompt_path.write_text("prompt", encoding="utf-8")
    monkeypatch.setattr("app_config.PROJECT_ROOT", tmp_path)

    extractor = build_extractor_for_path(tmp_path / "process.docx", object())

    assert isinstance(extractor, DocxExtractor)


def test_build_extractor_for_path_uses_pdf_extractor_for_pdf(monkeypatch, tmp_path: Path) -> None:
    prompt_path = tmp_path / "prompts" / "extract_generic.md"
    prompt_path.parent.mkdir()
    prompt_path.write_text("prompt", encoding="utf-8")
    monkeypatch.setattr("app_config.PROJECT_ROOT", tmp_path)

    extractor = build_extractor_for_path(tmp_path / "process.pdf", object())

    assert isinstance(extractor, PdfExtractor)


def test_run_document_builds_matches_and_review_items(tmp_path: Path) -> None:
    bpmn_path = tmp_path / "process.bpmn"
    prompt_path = tmp_path / "prompt.md"
    bpmn_path.write_text("<definitions><process id='proc_001' /></definitions>", encoding="utf-8")
    prompt_path.write_text("prompt", encoding="utf-8")
    extractor = BpmnExtractor(prompt_path=prompt_path, llm_client=FakeLlmClient())

    result = run_document(
        source_path=bpmn_path,
        file_hash="hash-1",
        extractor=extractor,
        config=AppConfig(
            cmdb_uuid_column="app_id",
            cmdb_name_column="application_name",
            fuzzy_threshold=0.85,
        ),
        knowledge_base=KnowledgeBase(
            confirmed=[
                {
                    "prozess": "Auftragsabwicklung",
                    "anwendung_name": "Manuelles CRM",
                    "cmdb_id": "cmdb-2",
                    "resolved_to": "Manual CRM",
                    "quelle": "manueller_link",
                }
            ],
            rejected=[],
            disambiguation=[],
            process_identity=[],
            org_units=[],
            org_unit_candidates=[],
        ),
        cmdb_rows=[{"app_id": "cmdb-1", "application_name": "SAP Sales"}],
        graph_writer=GraphWriter(),
    )

    assert result.status == "processed"
    assert result.matches[0].cmdb_id == "cmdb-1"
    assert result.matches[1].cmdb_id is None
    assert result.matches[2].application_name == "Manuelles CRM"
    assert result.matches[2].source == "knowledge_base_manual"
    assert result.review_items[0].application_name == "Unbekanntes System"
    assert result.graph_payload.process.process_id == "proc_001"


def test_run_document_does_not_revive_absent_confirmed_non_manual_matches(tmp_path: Path) -> None:
    bpmn_path = tmp_path / "process.bpmn"
    prompt_path = tmp_path / "prompt.md"
    bpmn_path.write_text("<definitions><process id='proc_001' /></definitions>", encoding="utf-8")
    prompt_path.write_text("prompt", encoding="utf-8")
    extractor = BpmnExtractor(prompt_path=prompt_path, llm_client=FakeLlmClient())

    result = run_document(
        source_path=bpmn_path,
        file_hash="hash-1",
        extractor=extractor,
        config=AppConfig(
            cmdb_uuid_column="app_id",
            cmdb_name_column="application_name",
            fuzzy_threshold=0.85,
        ),
        knowledge_base=KnowledgeBase(
            confirmed=[
                {
                    "prozess": "Auftragsabwicklung",
                    "anwendung_name": "Historisches CRM",
                    "cmdb_id": "cmdb-9",
                    "resolved_to": "Historic CRM",
                    "quelle": "manuell_bestaetigt",
                }
            ],
            rejected=[],
            disambiguation=[],
            process_identity=[],
            org_units=[],
            org_unit_candidates=[],
        ),
        cmdb_rows=[{"app_id": "cmdb-1", "application_name": "SAP Sales"}],
        graph_writer=GraphWriter(),
    )

    assert all(match.application_name != "Historisches CRM" for match in result.matches)


def test_should_skip_file_only_for_unchanged_delta_runs(tmp_path: Path) -> None:
    source_path = tmp_path / "process.bpmn"
    source_path.write_text("<definitions />", encoding="utf-8")

    assert should_skip_file("partial", None, source_path, "same-hash", {str(source_path): "same-hash"}) is False
    assert should_skip_file("full", None, source_path, "same-hash", {str(source_path): "same-hash"}) is False
    assert should_skip_file("partial", [source_path], source_path, "same-hash", {str(source_path): "same-hash"}) is False


def test_run_pipeline_writes_artifacts_for_full_runs(tmp_path: Path, monkeypatch) -> None:
    input_dir = tmp_path / "Input"
    output_dir = tmp_path / "Output"
    prompts_dir = tmp_path / "prompts"
    input_dir.mkdir()
    output_dir.mkdir()
    prompts_dir.mkdir()

    bpmn_path = input_dir / "process.bpmn"
    bpmn_path.write_text("<definitions><process id='proc_001' /></definitions>", encoding="utf-8")
    (input_dir / "cmdb.csv").write_text("app_id,application_name\ncmdb-1,SAP Sales\n", encoding="utf-8")
    (prompts_dir / "extract_bpmn.md").write_text("prompt", encoding="utf-8")

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("app_config.PROJECT_ROOT", tmp_path)

    class PipelineLlmClient:
        def __init__(self, config) -> None:
            self._config = config

        def list_models(self) -> list[str]:
            return ["test-model"]

        def generate_json(self, system_prompt: str, user_prompt: str) -> dict:
            return {
                "prozess": "Auftragsabwicklung",
                "prozess_id": "proc_001",
                "org_einheit": "Vertrieb",
                "folgt_auf": [],
                "anwendungen": [{"name": "SAP Sales", "konfidenz": "stark"}],
            }

    class FakeNeo4jClient:
        def __init__(self) -> None:
            self.cleanup_called = False

        def close(self) -> None:
            return None

        def execute_write(self, query: str, parameters=None):
            if "MATCH (p:Prozess {placeholder: true})" in query:
                self.cleanup_called = True
            return []

        def ensure_constraints(self) -> None:
            return None

    monkeypatch.setattr("pipeline.OpenAICompatibleClient", PipelineLlmClient)
    fake_client = FakeNeo4jClient()
    monkeypatch.setattr("pipeline.build_neo4j_client", lambda config: fake_client)

    config = AppConfig(
        llm_base_url="http://localhost:11434/v1",
        llm_model="test-model",
        neo4j_password="test-password",
        input_path="Input",
        cmdb_filename="cmdb.csv",
        output_path="Output",
        last_run_mode="full",
    )

    first_run = run_pipeline(config)

    assert first_run.documents[0].status == "processed"
    assert first_run.documents[0].process_write_action == "inserted"
    assert first_run.output_path == str(output_dir)
    assert first_run.used_output_fallback is False
    assert (output_dir / STATE_FILENAME).exists()
    assert (output_dir / LATEST_RUN_FILENAME).exists()
    assert fake_client.cleanup_called is True


def test_run_pipeline_partial_without_explicit_files_returns_empty_run(tmp_path: Path, monkeypatch) -> None:
    input_dir = tmp_path / "Input"
    output_dir = tmp_path / "Output"
    prompts_dir = tmp_path / "prompts"
    input_dir.mkdir()
    output_dir.mkdir()
    prompts_dir.mkdir()

    (input_dir / "process.bpmn").write_text("<definitions><process id='proc_001' /></definitions>", encoding="utf-8")
    (input_dir / "cmdb.csv").write_text("app_id,application_name\ncmdb-1,SAP Sales\n", encoding="utf-8")
    (prompts_dir / "extract_bpmn.md").write_text("prompt", encoding="utf-8")

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("app_config.PROJECT_ROOT", tmp_path)

    class FakeNeo4jClient:
        def close(self) -> None:
            return None

        def execute_write(self, query: str, parameters=None):
            return []

        def ensure_constraints(self) -> None:
            return None

    monkeypatch.setattr("pipeline.build_neo4j_client", lambda config: FakeNeo4jClient())
    monkeypatch.setattr("pipeline.OpenAICompatibleClient", lambda config: None)

    result = run_pipeline(
        AppConfig(
            llm_model="test-model",
            neo4j_password="test-password",
            input_path="Input",
            cmdb_filename="cmdb.csv",
            output_path="Output",
            last_run_mode="partial",
        )
    )

    assert result.documents == []


def test_run_pipeline_reports_progress_updates(tmp_path: Path, monkeypatch) -> None:
    input_dir = tmp_path / "Input"
    output_dir = tmp_path / "Output"
    prompts_dir = tmp_path / "prompts"
    input_dir.mkdir()
    output_dir.mkdir()
    prompts_dir.mkdir()

    first_path = input_dir / "a.bpmn"
    second_path = input_dir / "b.bpmn"
    first_path.write_text("<definitions><process id='proc_001' /></definitions>", encoding="utf-8")
    second_path.write_text("<definitions><process id='proc_002' /></definitions>", encoding="utf-8")
    (input_dir / "cmdb.csv").write_text("app_id,application_name\ncmdb-1,SAP Sales\n", encoding="utf-8")
    (prompts_dir / "extract_bpmn.md").write_text("prompt", encoding="utf-8")

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("app_config.PROJECT_ROOT", tmp_path)

    class PipelineLlmClient:
        def __init__(self, config) -> None:
            self._config = config

        def generate_json(self, system_prompt: str, user_prompt: str) -> dict:
            return {
                "prozess": "Auftragsabwicklung",
                "prozess_id": "proc_001",
                "org_einheit": "Vertrieb",
                "folgt_auf": [],
                "anwendungen": [{"name": "SAP Sales", "konfidenz": "stark"}],
            }

    class FakeNeo4jClient:
        def close(self) -> None:
            return None

        def execute_write(self, query: str, parameters=None):
            return []

        def ensure_constraints(self) -> None:
            return None

    progress_updates: list[dict] = []
    monkeypatch.setattr("pipeline.OpenAICompatibleClient", PipelineLlmClient)
    monkeypatch.setattr("pipeline.build_neo4j_client", lambda config: FakeNeo4jClient())

    config = AppConfig(
        llm_base_url="http://localhost:11434/v1",
        llm_model="test-model",
        neo4j_password="test-password",
        input_path="Input",
        cmdb_filename="cmdb.csv",
        output_path="Output",
        last_run_mode="full",
    )

    run_pipeline(config, progress_callback=progress_updates.append)

    assert progress_updates[0] == {
        "phase": "start",
        "completed": 0,
        "total": 2,
        "source_path": "",
        "status": "",
    }
    assert progress_updates[1]["phase"] == "document"
    assert progress_updates[1]["completed"] == 1
    assert progress_updates[1]["total"] == 2
    assert progress_updates[1]["source_path"] == str(first_path)
    assert progress_updates[2]["phase"] == "document"
    assert progress_updates[2]["completed"] == 2
    assert progress_updates[2]["total"] == 2
    assert progress_updates[2]["source_path"] == str(second_path)
    assert progress_updates[3] == {
        "phase": "done",
        "completed": 2,
        "total": 2,
        "source_path": "",
        "status": "",
    }


def test_run_pipeline_propagates_neo4j_write_failures(tmp_path: Path, monkeypatch) -> None:
    input_dir = tmp_path / "Input"
    output_dir = tmp_path / "Output"
    prompts_dir = tmp_path / "prompts"
    input_dir.mkdir()
    output_dir.mkdir()
    prompts_dir.mkdir()

    bpmn_path = input_dir / "process.bpmn"
    bpmn_path.write_text("<definitions><process id='proc_001' /></definitions>", encoding="utf-8")
    (input_dir / "cmdb.csv").write_text("app_id,application_name\ncmdb-1,SAP Sales\n", encoding="utf-8")
    (prompts_dir / "extract_bpmn.md").write_text("prompt", encoding="utf-8")

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("app_config.PROJECT_ROOT", tmp_path)

    class PipelineLlmClient:
        def __init__(self, config) -> None:
            self._config = config

        def generate_json(self, system_prompt: str, user_prompt: str) -> dict:
            return {
                "prozess": "Auftragsabwicklung",
                "prozess_id": "proc_001",
                "org_einheit": "Vertrieb",
                "folgt_auf": [],
                "anwendungen": [{"name": "SAP Sales", "konfidenz": "stark"}],
            }

    class FailingNeo4jClient:
        def close(self) -> None:
            return None

        def execute_write(self, query: str, parameters=None):
            raise Neo4jServiceUnavailableError("Neo4j is currently unavailable: boom")

        def ensure_constraints(self) -> None:
            return None

    monkeypatch.setattr("pipeline.OpenAICompatibleClient", PipelineLlmClient)
    monkeypatch.setattr("pipeline.build_neo4j_client", lambda config: FailingNeo4jClient())

    config = AppConfig(
        llm_base_url="http://localhost:11434/v1",
        llm_model="test-model",
        neo4j_password="test-password",
        input_path="Input",
        cmdb_filename="cmdb.csv",
        output_path="Output",
        last_run_mode="full",
    )

    with pytest.raises(Neo4jServiceUnavailableError, match="Neo4j is currently unavailable"):
        run_pipeline(config)


def test_apply_org_unit_mapping_uses_exact_role_matches_from_curated_org_units() -> None:
    extracted_process = ExtractedProcess(
        process_name="Incident Handling",
        process_id="proc-1",
        org_unit="",
        roles=["People & Culture"],
        org_units=[],
        org_unit_candidates=[],
        follows_after=[],
        raw_applications=[ApplicationReference(name="Mail", confidence="stark")],
        applications=[ApplicationReference(name="Mail", confidence="stark")],
        source_path="Input/process.txt",
    )
    knowledge_base = KnowledgeBase(
        confirmed=[],
        rejected=[],
        disambiguation=[],
        process_identity=[],
        org_units=[{"name": "People & Culture", "created_at": "2026-05-27", "source": "manual"}],
        org_unit_candidates=[],
    )

    result = apply_org_unit_mapping(extracted_process, knowledge_base)

    assert result.org_unit == "People & Culture"
    assert result.org_units == ["People & Culture"]


def test_apply_org_unit_mapping_uses_confirmed_candidates_for_unstructured_documents() -> None:
    extracted_process = ExtractedProcess(
        process_name="Incident Handling",
        process_id="proc-1",
        org_unit="",
        roles=["HR Manager"],
        org_units=[],
        org_unit_candidates=["People Ops"],
        follows_after=[],
        raw_applications=[ApplicationReference(name="Mail", confidence="stark")],
        applications=[ApplicationReference(name="Mail", confidence="stark")],
        source_path="Input/process.txt",
    )
    knowledge_base = KnowledgeBase(
        confirmed=[],
        rejected=[],
        disambiguation=[],
        process_identity=[],
        org_units=[{"name": "People & Culture", "created_at": "2026-05-27", "source": "manual"}],
        org_unit_candidates=[
            {
                "candidate_name": "People Ops",
                "normalized_name": "people ops",
                "source_paths": ["Input/process.txt"],
                "process_names": ["Incident Handling"],
                "role_names": ["HR Manager"],
                "status": "mapped",
                "mapped_org_unit": "People & Culture",
                "first_seen": "2026-05-27",
                "last_seen": "2026-05-27",
            }
        ],
    )

    result = apply_org_unit_mapping(extracted_process, knowledge_base)

    assert result.org_unit == "People & Culture"
    assert result.org_units == ["People & Culture"]


def test_update_organization_knowledge_from_cmdb_adds_only_unresolved_owner_candidates() -> None:
    knowledge_base = KnowledgeBase(
        confirmed=[],
        rejected=[],
        disambiguation=[],
        process_identity=[],
        org_units=[{"name": "Team Platform", "created_at": "2026-05-28", "source": "manual"}],
        org_unit_candidates=[],
    )
    normalized_cmdb = type(
        "Normalized",
        (),
        {
            "entities": [
                type("Entity", (), {"entity_id": "srv-1", "owner_name": "Team Platform"})(),
                type("Entity", (), {"entity_id": "srv-2", "owner_name": "Team Plattform"})(),
            ]
        },
    )()

    updated = update_organization_knowledge_from_cmdb(
        knowledge_base,
        normalized_cmdb,
        source_path="Input/cmdb_entities.csv",
    )

    assert len(updated.org_unit_candidates) == 1
    assert updated.org_unit_candidates[0]["candidate_name"] == "Team Plattform"


def test_resolve_cmdb_owner_assignments_returns_exact_and_mapped_matches() -> None:
    knowledge_base = KnowledgeBase(
        confirmed=[],
        rejected=[],
        disambiguation=[],
        process_identity=[],
        org_units=[{"name": "Team Platform", "created_at": "2026-05-28", "source": "manual"}],
        org_unit_candidates=[
            {
                "candidate_name": "Team Infrastruktur",
                "normalized_name": "team infrastruktur",
                "source_paths": ["Input/cmdb_entities.csv"],
                "process_names": [],
                "role_names": [],
                "status": "mapped",
                "mapped_org_unit": "Team Infrastructure",
                "first_seen": "2026-05-28",
                "last_seen": "2026-05-28",
            }
        ],
    )
    normalized_cmdb = type(
        "Normalized",
        (),
        {
            "entities": [
                type("Entity", (), {"entity_id": "srv-1", "owner_name": "Team Platform"})(),
                type("Entity", (), {"entity_id": "srv-2", "owner_name": "Team Infrastruktur"})(),
                type("Entity", (), {"entity_id": "srv-3", "owner_name": "Unknown Team"})(),
            ]
        },
    )()

    assignments = resolve_cmdb_owner_assignments(knowledge_base, normalized_cmdb)

    assert assignments == {
        "srv-1": "Team Platform",
        "srv-2": "Team Infrastructure",
    }

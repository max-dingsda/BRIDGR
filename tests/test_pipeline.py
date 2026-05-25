from pathlib import Path

import pytest

from app_config import AppConfig
from neo4j_utils import Neo4jServiceUnavailableError
from pipeline import build_extractor_for_path, list_bpmn_files, run_document, run_pipeline, should_skip_file
from run_artifacts import LATEST_RUN_FILENAME, STATE_FILENAME
from skills.graph_writer import GraphWriter
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
            confirmed=[{"prozess": "Auftragsabwicklung", "anwendung_name": "Manuelles CRM", "cmdb_id": "cmdb-2", "resolved_to": "Manual CRM"}],
            rejected=[],
            disambiguation=[],
            process_identity=[],
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


def test_should_skip_file_only_for_unchanged_delta_runs(tmp_path: Path) -> None:
    source_path = tmp_path / "process.bpmn"
    source_path.write_text("<definitions />", encoding="utf-8")

    assert should_skip_file("delta", None, source_path, "same-hash", {str(source_path): "same-hash"}) is True
    assert should_skip_file("full", None, source_path, "same-hash", {str(source_path): "same-hash"}) is False
    assert should_skip_file("delta", [source_path], source_path, "same-hash", {str(source_path): "same-hash"}) is False


def test_run_pipeline_writes_artifacts_and_skips_unchanged_delta_files(tmp_path: Path, monkeypatch) -> None:
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
        def close(self) -> None:
            return None

        def execute_write(self, query: str, parameters=None):
            return []

        def ensure_constraints(self) -> None:
            return None

    monkeypatch.setattr("pipeline.OpenAICompatibleClient", PipelineLlmClient)
    monkeypatch.setattr("pipeline.build_neo4j_client", lambda config: FakeNeo4jClient())

    config = AppConfig(
        llm_base_url="http://localhost:11434/v1",
        llm_model="test-model",
        neo4j_password="test-password",
        input_path="Input",
        cmdb_filename="cmdb.csv",
        output_path="Output",
        last_run_mode="delta",
    )

    first_run = run_pipeline(config)
    second_run = run_pipeline(config)

    assert first_run.documents[0].status == "processed"
    assert first_run.output_path == str(output_dir)
    assert first_run.used_output_fallback is False
    assert second_run.documents[0].status == "skipped_unchanged"
    assert (output_dir / STATE_FILENAME).exists()
    assert (output_dir / LATEST_RUN_FILENAME).exists()


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
        last_run_mode="initial",
    )

    with pytest.raises(Neo4jServiceUnavailableError, match="Neo4j is currently unavailable"):
        run_pipeline(config)

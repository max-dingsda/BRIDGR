from pathlib import Path

from core.app_config import AppConfig
from processing.knowledge_base import KnowledgeBase
from services.cmdb_service import sync_cmdb_to_neo4j


class RecordingNeo4jClient:
    def __init__(self) -> None:
        self.queries: list[tuple[str, dict | None]] = []

    def ensure_constraints(self) -> None:
        self.queries.append(("ENSURE_CONSTRAINTS", None))

    def execute_write(self, query: str, parameters=None):
        self.queries.append((query, parameters))
        return []


def test_sync_cmdb_to_neo4j_writes_entities_relations_and_owner_assignments(tmp_path: Path, monkeypatch) -> None:
    input_dir = tmp_path / "Input"
    input_dir.mkdir()
    (input_dir / "cmdb_entities.csv").write_text(
        "id,name,entity_type,owner_name\n"
        "app-1,Seller Service,application,Team Commerce IT\n"
        "if-1,Seller API,interface,\n",
        encoding="utf-8",
    )
    (input_dir / "cmdb_relations.csv").write_text(
        "source_id,relation_type,target_id\napp-1,USES_INTERFACE,if-1\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("core.app_config.PROJECT_ROOT", tmp_path)

    config = AppConfig(
        input_path="Input",
        cmdb_filename="cmdb_entities.csv",
        cmdb_relations_filename="cmdb_relations.csv",
        cmdb_uuid_column="id",
        cmdb_name_column="name",
        cmdb_entity_type_column="entity_type",
        cmdb_server_type_column="server_type",
        cmdb_owner_name_column="owner_name",
    )
    knowledge_base = KnowledgeBase(
        confirmed=[],
        rejected=[],
        disambiguation=[],
        process_identity=[],
        org_units=[{"name": "Team Commerce IT", "created_at": "2026-05-31", "source": "manual"}],
        org_unit_candidates=[],
    )
    client = RecordingNeo4jClient()

    result, updated_kb = sync_cmdb_to_neo4j(config, client, knowledge_base)

    queries = [query for query, _ in client.queries]
    assert result.entity_count == 2
    assert result.relation_count == 1
    assert result.owner_assignment_count == 1
    assert any("MERGE (a:Anwendung {cmdb_id: $entity_id})" in query for query in queries)
    assert any("MERGE (i:Schnittstelle {id: $entity_id})" in query for query in queries)
    assert any("MERGE (source)-[:USES_INTERFACE]->(target)" in query for query in queries)
    assert any("MERGE (o)-[:VERANTWORTET]->(target)" in query for query in queries)
    assert updated_kb.org_unit_candidates == []


def test_sync_cmdb_to_neo4j_adds_unresolved_owner_candidates(tmp_path: Path, monkeypatch) -> None:
    input_dir = tmp_path / "Input"
    input_dir.mkdir()
    (input_dir / "cmdb_entities.csv").write_text(
        "id,name,entity_type,owner_name\n"
        "srv-1,vm-app-01,server,Team Plattform\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("core.app_config.PROJECT_ROOT", tmp_path)

    config = AppConfig(
        input_path="Input",
        cmdb_filename="cmdb_entities.csv",
        cmdb_uuid_column="id",
        cmdb_name_column="name",
        cmdb_entity_type_column="entity_type",
        cmdb_server_type_column="server_type",
        cmdb_owner_name_column="owner_name",
    )
    knowledge_base = KnowledgeBase(
        confirmed=[],
        rejected=[],
        disambiguation=[],
        process_identity=[],
        org_units=[],
        org_unit_candidates=[],
    )

    result, updated_kb = sync_cmdb_to_neo4j(config, RecordingNeo4jClient(), knowledge_base)

    assert result.entity_count == 1
    assert result.owner_assignment_count == 0
    assert len(updated_kb.org_unit_candidates) == 1
    assert updated_kb.org_unit_candidates[0]["candidate_name"] == "Team Plattform"

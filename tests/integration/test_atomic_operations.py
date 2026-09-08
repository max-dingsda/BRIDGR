from dataclasses import replace
import json

import pytest

from core.neo4j_utils import Neo4jExecutionError
from services import review_service
from skills.graph_writer import GraphWriter
from services.review_service import reconstruct_extracted_process


def test_process_update_rolls_back_after_deletion(graph_client, monkeypatch):
    graph_client.execute_write("""
        CREATE (p:Process {process_id:'p1', name:'Before'})
        CREATE (a:Application {cmdb_id:'a1', name:'ERP'})
        CREATE (a)-[:SERVES {source:'strong', confidence:'stark'}]->(p)
    """)
    original = graph_client._execute
    def failing(query, parameters=None):
        if "MERGE (r:Role" in query:
            raise RuntimeError("injected role failure")
        return original(query, parameters)
    monkeypatch.setattr(graph_client, "_execute", failing)
    process = reconstruct_extracted_process({"process_id": "p1", "process_name": "After", "roles": ["Owner"]})
    with pytest.raises(RuntimeError, match="injected"):
        GraphWriter().write_payload(graph_client, GraphWriter().build_payload(process, []))
    assert original("MATCH (:Application)-[r:SERVES]->(p:Process) RETURN p.name AS name, r.source AS source") == [
        {"name": "Before", "source": "strong"}]


def test_confirmation_rolls_back_when_audit_fails(graph_client, isolated_neo4j_config, monkeypatch):
    monkeypatch.setattr(review_service, "get_session_neo4j_client", lambda _: graph_client)
    def fail(*args, **kwargs):
        raise RuntimeError("injected audit failure")
    monkeypatch.setattr(review_service, "create_manual_decision", fail)
    with pytest.raises(RuntimeError, match="audit"):
        review_service.confirm_review_link(isolated_neo4j_config, "Order", "SAP", "a1", "ERP", "p1", "", [])
    assert graph_client.execute_read_unvalidated("MATCH (p:Process) RETURN count(p) AS n") == [{"n": 0}]
    assert graph_client.execute_read_unvalidated("MATCH (d:ManualDecision) RETURN count(d) AS n") == [{"n": 0}]


def test_failed_projection_replays_without_repeating_graph_operation(graph_client, tmp_path, monkeypatch):
    from processing import run_artifacts
    path = tmp_path / "latest_run.json"
    original = run_artifacts.atomic_write_json
    def fail(*args, **kwargs):
        raise OSError("injected file failure")
    monkeypatch.setattr(run_artifacts, "atomic_write_json", fail)
    with pytest.raises(Neo4jExecutionError, match="Graph wurde gespeichert"):
        with graph_client.transaction():
            graph_client.execute_write("CREATE (:ManualDecision {decision_id:'once'})")
            graph_client.stage_artifact(path, {"status": "committed"})
    assert not path.exists()
    assert graph_client.execute_read_unvalidated("MATCH (d:ManualDecision) RETURN count(d) AS n") == [{"n": 1}]
    monkeypatch.setattr(run_artifacts, "atomic_write_json", original)
    with graph_client.transaction():
        pass
    assert json.loads(path.read_text(encoding="utf-8")) == {"status": "committed"}
    assert graph_client.execute_read_unvalidated("MATCH (d:ManualDecision) RETURN count(d) AS n") == [{"n": 1}]
    assert graph_client.execute_read_unvalidated("MATCH (a:__BridgrArtifact) RETURN count(a) AS n") == [{"n": 0}]


def test_artifact_is_not_published_if_domain_transaction_rolls_back(graph_client, tmp_path):
    path = tmp_path / "latest_run.json"
    with pytest.raises(ValueError):
        with graph_client.transaction():
            graph_client.stage_artifact(path, {"wrong": True})
            raise ValueError("rollback")
    assert not path.exists()
    assert graph_client.read_staged_artifact(path) is None


def test_unwritable_old_artifact_does_not_block_unrelated_write(graph_client, tmp_path, monkeypatch):
    from processing import run_artifacts
    def fail(*args, **kwargs):
        raise OSError("read-only artifact destination")
    monkeypatch.setattr(run_artifacts, "atomic_write_json", fail)
    with pytest.raises(Neo4jExecutionError):
        with graph_client.transaction():
            graph_client.stage_artifact(tmp_path / "old.json", {"old": True})
    graph_client.execute_write("CREATE (:Process {process_id:'independent', name:'New'})")
    assert graph_client.execute_read("MATCH (p:Process) RETURN p.name AS name") == [{"name": "New"}]
    assert graph_client.read_staged_artifact(tmp_path / "old.json") == {"old": True}
    # Leave the fixture clean without requiring publication.
    graph_client.execute_write("MATCH (a:__BridgrArtifact) DELETE a")


def test_separate_clients_serialize_snapshot_and_writes(graph_client, isolated_neo4j_config, tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event
    from core.neo4j_utils import Neo4jClient, Neo4jConfig
    from services.snapshot_service import create_snapshot
    config = replace(isolated_neo4j_config, output_path=str(tmp_path))
    second = Neo4jClient(Neo4jConfig(config.neo4j_url, config.neo4j_user,
                                   config.neo4j_password, config.neo4j_database))
    second.ensure_constraints()
    started, entered = Event(), Event()
    def mutate():
        started.set()
        with second.transaction():
            entered.set()
            second.execute_write("CREATE (:Process {process_id:'later', name:'Later'})")
    try:
        with ThreadPoolExecutor(max_workers=1) as pool:
            with graph_client.serialized_writes():
                task = pool.submit(mutate)
                assert started.wait(5)
                assert not entered.wait(0.2)
                snapshot = create_snapshot(config, graph_client, trigger="test", operation="concurrent")
                assert snapshot.valid and snapshot.node_count == 0
                assert not entered.is_set()
            task.result(timeout=10)
        assert entered.is_set()
        assert graph_client.execute_read("MATCH (p:Process) RETURN count(p) AS n") == [{"n": 1}]
    finally:
        second.close()


def test_batch_keeps_query_error_type_and_rolls_back(graph_client):
    from core.neo4j_utils import Neo4jQuerySyntaxError
    with pytest.raises(Neo4jQuerySyntaxError):
        graph_client.execute_write_batch([
            ("CREATE (:Process {process_id:'rollback'})", {}),
            ("THIS IS INVALID CYPHER", {}),
        ])
    assert graph_client.execute_read("MATCH (p:Process) RETURN count(p) AS n") == [{"n": 0}]


def test_archive_uses_committed_pending_projection_instead_of_stale_disk(graph_client, isolated_neo4j_config, tmp_path, monkeypatch):
    from processing import run_artifacts
    from services import import_service
    monkeypatch.setattr(import_service, "get_session_neo4j_client", lambda _: graph_client)
    monkeypatch.setattr("core.app_config.PROJECT_ROOT", tmp_path)
    source = tmp_path / "Input" / "process.txt"
    source.parent.mkdir()
    source.write_text("process", encoding="utf-8")
    output = tmp_path / "Output"
    run_artifacts.write_latest_run({"run_id": "old", "documents": []}, output)
    original = run_artifacts.atomic_write_json
    def fail(*args, **kwargs):
        raise OSError("injected pending projection")
    monkeypatch.setattr(run_artifacts, "atomic_write_json", fail)
    with pytest.raises(Neo4jExecutionError):
        with graph_client.transaction():
            run_artifacts.write_latest_run({"run_id": "current", "marker": "retain", "documents": []}, output, graph_client)
    monkeypatch.setattr(run_artifacts, "atomic_write_json", original)
    archive, paths = import_service.finalize_import_artifacts(
        isolated_neo4j_config, output, source.parent, "full", [str(source)], expected_run_id="current")
    latest = run_artifacts.load_latest_run(output)
    assert latest["run_id"] == "current" and latest["marker"] == "retain"
    assert latest["import_archive_path"] == archive and paths == ["process.txt"]

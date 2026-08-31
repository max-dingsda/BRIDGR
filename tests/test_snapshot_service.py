from __future__ import annotations

import json
from pathlib import Path
from hashlib import sha256

import pytest

from core.app_config import AppConfig
from core.i18n import translate_snapshot_error
from services.snapshot_service import SnapshotError, create_snapshot, list_snapshots, restore_snapshot


def test_translate_snapshot_schema_version_error_uses_selected_locale() -> None:
    error = "Snapshot uses graph schema version unknown; BRIDGR requires version 2."

    assert translate_snapshot_error(error, "de") == "Snapshot verwendet Graph-Schema-Version unknown; BRIDGR benötigt Version 2."
    assert translate_snapshot_error(error, "en") == error


class FakeNeo4jClient:
    def __init__(self) -> None:
        self.batches: list[list[tuple[str, dict]]] = []
        self.current_node_count = 2
        self.current_relationship_count = 1

    def execute_read_unvalidated(self, query: str, _parameters=None) -> list[dict]:
        if "RETURN elementId(n) AS snapshot_node_id" in query:
            return [
                {"snapshot_node_id": "old-a", "labels": ["Process"], "properties": {"process_id": "P-1", "name": "Rechnung"}},
                {"snapshot_node_id": "old-b", "labels": ["Application"], "properties": {"cmdb_id": "A-1", "name": "SAP"}},
            ]
        if "source_snapshot_node_id" in query:
            return [{"source_snapshot_node_id": "old-b", "target_snapshot_node_id": "old-a", "relationship_type": "SERVES", "properties": {"source": "stark"}}]
        if "relationship_count" in query:
            return [{"node_count": self.current_node_count, "relationship_count": self.current_relationship_count}]
        return []

    def execute_write_batch(self, statements: list[tuple[str, dict]]) -> list[list[dict]]:
        self.batches.append(statements)
        if statements and "DETACH DELETE" in statements[0][0]:
            self.current_node_count = len(statements) - 1
            self.current_relationship_count = sum(":`SERVES`" in query for query, _ in statements)
            self.current_node_count -= self.current_relationship_count + 1
            return [[] for _ in statements]
        self.current_relationship_count = len(statements)
        return [[] for _ in statements]


def _config(tmp_path: Path, retention: int = 10) -> AppConfig:
    return AppConfig(
        output_path=str(tmp_path / "Output"),
        neo4j_database="bridgr-test",
        snapshot_retention_count=retention,
    )


def test_create_snapshot_writes_validated_graph_and_manifest(tmp_path: Path) -> None:
    snapshot = create_snapshot(_config(tmp_path), FakeNeo4jClient(), trigger="pipeline", operation="process_import")

    assert snapshot.valid is True
    assert snapshot.node_count == 2
    assert snapshot.relationship_count == 1
    graph_path = tmp_path / "Output" / "snapshots" / snapshot.snapshot_id / "graph.json"
    assert json.loads(graph_path.read_text(encoding="utf-8"))["nodes"][0]["labels"] == ["Process"]
    manifest = json.loads((graph_path.parent / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["graph_schema_version"] == 2
    assert list_snapshots(_config(tmp_path))[0] == snapshot


def test_create_snapshot_prunes_only_old_valid_snapshots(tmp_path: Path) -> None:
    client = FakeNeo4jClient()
    config = _config(tmp_path, retention=1)

    first = create_snapshot(config, client, trigger="pipeline", operation="first")
    second = create_snapshot(config, client, trigger="pipeline", operation="second")

    snapshots = list_snapshots(config)
    assert [snapshot.snapshot_id for snapshot in snapshots] == [second.snapshot_id]
    assert not (tmp_path / "Output" / "snapshots" / first.snapshot_id).exists()


def test_restore_snapshot_recreates_nodes_relationships_and_verifies_counts(tmp_path: Path) -> None:
    client = FakeNeo4jClient()
    snapshot = create_snapshot(_config(tmp_path), client, trigger="pipeline", operation="process_import")

    restored = restore_snapshot(_config(tmp_path), client, snapshot.snapshot_id)

    assert restored.snapshot_id == snapshot.snapshot_id
    assert len(client.batches) == 1
    restore_batch = client.batches[0]
    assert "DETACH DELETE" in restore_batch[0][0]
    assert ":`Process`" in restore_batch[1][0]
    assert any(":`SERVES`" in query for query, _ in restore_batch)


def test_restore_snapshot_keeps_target_until_pre_restore_snapshot_is_created(tmp_path: Path) -> None:
    client = FakeNeo4jClient()
    config = _config(tmp_path, retention=1)
    snapshot = create_snapshot(config, client, trigger="pipeline", operation="process_import")

    restore_snapshot(config, client, snapshot.snapshot_id)

    snapshots = list_snapshots(config)
    assert len(snapshots) == 1
    assert snapshots[0].operation == f"pre_restore:{snapshot.snapshot_id}"


def test_restore_snapshot_rejects_dangling_relationship_before_any_graph_write(tmp_path: Path) -> None:
    client = FakeNeo4jClient()
    config = _config(tmp_path)
    snapshot = create_snapshot(config, client, trigger="pipeline", operation="process_import")
    snapshot_dir = tmp_path / "Output" / "snapshots" / snapshot.snapshot_id
    graph_path = snapshot_dir / "graph.json"
    payload = json.loads(graph_path.read_text(encoding="utf-8"))
    payload["relationships"][0]["target_snapshot_node_id"] = "missing-node"
    graph_bytes = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    graph_path.write_bytes(graph_bytes)
    manifest_path = snapshot_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["graph_sha256"] = sha256(graph_bytes).hexdigest()
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(SnapshotError, match="unbekanntem Knotenbezug"):
        restore_snapshot(config, client, snapshot.snapshot_id)

    assert client.batches == []


def test_restore_snapshot_requires_explicit_database_name(tmp_path: Path) -> None:
    snapshot = create_snapshot(_config(tmp_path), FakeNeo4jClient(), trigger="pipeline", operation="process_import")

    with pytest.raises(SnapshotError, match="explizit konfigurierte"):
        restore_snapshot(AppConfig(output_path=str(tmp_path / "Output")), FakeNeo4jClient(), snapshot.snapshot_id)


def test_restore_snapshot_rejects_tampered_graph(tmp_path: Path) -> None:
    client = FakeNeo4jClient()
    snapshot = create_snapshot(_config(tmp_path), client, trigger="pipeline", operation="process_import")
    graph_path = tmp_path / "Output" / "snapshots" / snapshot.snapshot_id / "graph.json"
    graph_path.write_text("{}", encoding="utf-8")

    with pytest.raises(SnapshotError, match="nicht verwendbar"):
        restore_snapshot(_config(tmp_path), client, snapshot.snapshot_id)


def test_restore_snapshot_rejects_invalid_snapshot_identifier(tmp_path: Path) -> None:
    with pytest.raises(SnapshotError, match="Ungültige Snapshot-ID"):
        restore_snapshot(_config(tmp_path), FakeNeo4jClient(), "../outside")


def test_restore_snapshot_rejects_legacy_schema_snapshot(tmp_path: Path) -> None:
    client = FakeNeo4jClient()
    snapshot = create_snapshot(_config(tmp_path), client, trigger="pipeline", operation="process_import")
    manifest_path = tmp_path / "Output" / "snapshots" / snapshot.snapshot_id / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest.pop("graph_schema_version")
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(SnapshotError, match="schema version"):
        restore_snapshot(_config(tmp_path), client, snapshot.snapshot_id)

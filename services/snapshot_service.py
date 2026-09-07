from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date, datetime, time, timezone
from hashlib import sha256
import json
from pathlib import Path
import shutil
from typing import Any
from uuid import uuid4

from core.app_config import AppConfig, resolve_runtime_output_path
from core.debug_utils import write_debug_log
from core.neo4j_utils import Neo4jClient, Neo4jExecutionError


SNAPSHOT_DIRECTORY_NAME = "snapshots"
SNAPSHOT_GRAPH_FILENAME = "graph.json"
SNAPSHOT_MANIFEST_FILENAME = "manifest.json"
RESTORE_LABEL = "__BridgrSnapshotRestore"
RESTORE_REFERENCE_PROPERTY = "__bridgr_snapshot_ref"
GRAPH_SCHEMA_VERSION = 2


class SnapshotError(RuntimeError):
    """Raised when a snapshot cannot safely be created or restored."""


@dataclass(frozen=True, slots=True)
class SnapshotInfo:
    snapshot_id: str
    created_at: str
    trigger: str
    operation: str
    node_count: int
    relationship_count: int
    valid: bool
    error: str = ""


def create_snapshot(
    config: AppConfig,
    neo4j_client: Neo4jClient,
    *,
    trigger: str,
    operation: str,
    protected_snapshot_ids: set[str] | None = None,
) -> SnapshotInfo:
    """Export and validate the complete BRIDGR graph before a write operation."""
    with neo4j_client.serialized_writes():
        try:
            nodes = neo4j_client.execute_read_unvalidated(
                """
                MATCH (n)
            WHERE NOT n:__BridgrWriteLock AND NOT n:__BridgrArtifact
                RETURN elementId(n) AS snapshot_node_id, labels(n) AS labels, properties(n) AS properties
                ORDER BY elementId(n)
                """,
                {},
            )
            relationships = neo4j_client.execute_read_unvalidated(
                """
                MATCH (source)-[relationship]->(target)
                RETURN elementId(source) AS source_snapshot_node_id,
                       elementId(target) AS target_snapshot_node_id,
                       type(relationship) AS relationship_type,
                       properties(relationship) AS properties
                ORDER BY elementId(source), type(relationship), elementId(target)
                """,
                {},
            )
        except Neo4jExecutionError as exc:
            raise SnapshotError(f"Snapshot konnte nicht aus Neo4j gelesen werden: {exc}") from exc

        graph_payload = {
            "nodes": [_normalize_node(row) for row in nodes],
            "relationships": [_normalize_relationship(row) for row in relationships],
        }
        graph_bytes = json.dumps(graph_payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        snapshot_id = _new_snapshot_id()
        created_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        output_path, _ = resolve_runtime_output_path(config.output_path)
        snapshot_root = output_path / SNAPSHOT_DIRECTORY_NAME
        temporary_path = snapshot_root / f".{snapshot_id}.tmp"
        final_path = snapshot_root / snapshot_id

        try:
            snapshot_root.mkdir(parents=True, exist_ok=True)
            temporary_path.mkdir(parents=False, exist_ok=False)
            (temporary_path / SNAPSHOT_GRAPH_FILENAME).write_bytes(graph_bytes)
            manifest = {
                "graph_schema_version": GRAPH_SCHEMA_VERSION,
                "snapshot_id": snapshot_id,
                "created_at": created_at,
                "trigger": trigger,
                "operation": operation,
                "node_count": len(graph_payload["nodes"]),
                "relationship_count": len(graph_payload["relationships"]),
                "graph_filename": SNAPSHOT_GRAPH_FILENAME,
                "graph_sha256": sha256(graph_bytes).hexdigest(),
                "config_hint": _safe_config_hint(config),
            }
            (temporary_path / SNAPSHOT_MANIFEST_FILENAME).write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
            )
            info = _validate_snapshot_directory(temporary_path)
            if not info.valid:
                raise SnapshotError(info.error)
            temporary_path.replace(final_path)
            removed_snapshot_ids = _prune_snapshots(
                snapshot_root,
                max(1, int(config.snapshot_retention_count)),
                keep_snapshot_id=snapshot_id,
                protected_snapshot_ids=protected_snapshot_ids or set(),
            )
            write_debug_log(
                config,
                "snapshot_created",
                {**asdict(info), "removed_snapshot_ids": removed_snapshot_ids},
            )
            return info
        except (OSError, ValueError, TypeError) as exc:
            raise SnapshotError(f"Snapshot konnte nicht geschrieben werden: {exc}") from exc
        finally:
            if temporary_path.exists():
                shutil.rmtree(temporary_path, ignore_errors=True)


def list_snapshots(config: AppConfig) -> list[SnapshotInfo]:
    output_path, _ = resolve_runtime_output_path(config.output_path)
    snapshot_root = output_path / SNAPSHOT_DIRECTORY_NAME
    if not snapshot_root.exists():
        return []
    snapshots = [
        _validate_snapshot_directory(path)
        for path in snapshot_root.iterdir()
        if path.is_dir() and not path.name.startswith(".")
    ]
    return sorted(snapshots, key=lambda item: item.created_at, reverse=True)


def restore_snapshot(config: AppConfig, neo4j_client: Neo4jClient, snapshot_id: str) -> SnapshotInfo:
    """Restore a validated graph snapshot after first protecting the current state."""
    with neo4j_client.serialized_writes():
        if not config.neo4j_database.strip():
            raise SnapshotError(
                "Wiederherstellung erfordert eine explizit konfigurierte, ausschließlich für BRIDGR verwendete Neo4j-Datenbank."
            )
        target_path = _snapshot_path(config, snapshot_id)
        target_info, graph_payload = _load_validated_graph(target_path)
        pre_restore = create_snapshot(
            config,
            neo4j_client,
            trigger="restore",
            operation=f"pre_restore:{snapshot_id}",
            protected_snapshot_ids={snapshot_id},
        )
        if not pre_restore.valid:
            raise SnapshotError("Pre-Restore-Snapshot ist nicht valide.")

        restore_statements: list[tuple[str, dict[str, Any]]] = [("MATCH (n) WHERE NOT n:__BridgrWriteLock DETACH DELETE n", {})]
        for node in graph_payload["nodes"]:
            restore_statements.append(
                (
                    _create_node_query(node["labels"]),
                    {"properties": node["properties"], "snapshot_node_id": node["snapshot_node_id"]},
                )
            )
        for relationship in graph_payload["relationships"]:
            restore_statements.append(
                (
                    _create_relationship_query(relationship["relationship_type"]),
                    {
                        "source_snapshot_node_id": relationship["source_snapshot_node_id"],
                        "target_snapshot_node_id": relationship["target_snapshot_node_id"],
                        "properties": relationship["properties"],
                    },
                )
            )
        restore_statements.append(
            (f"MATCH (n:`{RESTORE_LABEL}`) REMOVE n:`{RESTORE_LABEL}`, n.`{RESTORE_REFERENCE_PROPERTY}`", {})
        )
        try:
            with neo4j_client.transaction():
                neo4j_client.execute_write_batch(restore_statements)
                _verify_restored_counts(neo4j_client, target_info)
        except Neo4jExecutionError as exc:
            raise SnapshotError(f"Wiederherstellung von Snapshot '{snapshot_id}' fehlgeschlagen: {exc}") from exc

        output_path, _ = resolve_runtime_output_path(config.output_path)
        _prune_snapshots(
            output_path / SNAPSHOT_DIRECTORY_NAME,
            max(1, int(config.snapshot_retention_count)),
            keep_snapshot_id=pre_restore.snapshot_id,
            protected_snapshot_ids=set(),
        )
        write_debug_log(config, "snapshot_restored", asdict(target_info))
        return target_info


def _load_validated_graph(snapshot_path: Path) -> tuple[SnapshotInfo, dict[str, list[dict[str, Any]]]]:
    info = _validate_snapshot_directory(snapshot_path)
    if not info.valid:
        raise SnapshotError(f"Snapshot ist nicht verwendbar: {info.error}")
    try:
        graph_payload = json.loads((snapshot_path / SNAPSHOT_GRAPH_FILENAME).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SnapshotError(f"Snapshot-Graph kann nicht gelesen werden: {exc}") from exc
    if not isinstance(graph_payload.get("nodes"), list) or not isinstance(graph_payload.get("relationships"), list):
        raise SnapshotError("Snapshot-Graph hat ein ungültiges Format.")
    _validate_graph_references(graph_payload)
    return info, graph_payload


def _validate_snapshot_directory(snapshot_path: Path) -> SnapshotInfo:
    fallback = SnapshotInfo(snapshot_path.name, "", "", "", 0, 0, False, "Manifest fehlt oder ist ungültig.")
    try:
        manifest = json.loads((snapshot_path / SNAPSHOT_MANIFEST_FILENAME).read_text(encoding="utf-8"))
        if manifest.get("graph_schema_version") != GRAPH_SCHEMA_VERSION:
            return SnapshotInfo(
                str(manifest.get("snapshot_id", snapshot_path.name)), "", "", "", 0, 0, False,
                f"Snapshot uses graph schema version {manifest.get('graph_schema_version', 'unknown')}; "
                f"BRIDGR requires version {GRAPH_SCHEMA_VERSION}.",
            )
        graph_path = snapshot_path / str(manifest.get("graph_filename", ""))
        graph_bytes = graph_path.read_bytes()
        if sha256(graph_bytes).hexdigest() != manifest.get("graph_sha256"):
            return SnapshotInfo(str(manifest.get("snapshot_id", snapshot_path.name)), "", "", "", 0, 0, False, "Prüfsumme stimmt nicht überein.")
        graph_payload = json.loads(graph_bytes)
        nodes = graph_payload.get("nodes")
        relationships = graph_payload.get("relationships")
        if not isinstance(nodes, list) or not isinstance(relationships, list):
            return SnapshotInfo(str(manifest.get("snapshot_id", snapshot_path.name)), "", "", "", 0, 0, False, "Graph-Format ist ungültig.")
        if len(nodes) != int(manifest.get("node_count", -1)) or len(relationships) != int(manifest.get("relationship_count", -1)):
            return SnapshotInfo(str(manifest.get("snapshot_id", snapshot_path.name)), "", "", "", 0, 0, False, "Objektzähler stimmen nicht überein.")
        return SnapshotInfo(
            snapshot_id=str(manifest["snapshot_id"]),
            created_at=str(manifest["created_at"]),
            trigger=str(manifest["trigger"]),
            operation=str(manifest["operation"]),
            node_count=len(nodes),
            relationship_count=len(relationships),
            valid=True,
        )
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        return SnapshotInfo(fallback.snapshot_id, "", "", "", 0, 0, False, str(exc))


def _verify_restored_counts(neo4j_client: Neo4jClient, snapshot_info: SnapshotInfo) -> None:
    rows = neo4j_client.execute_read_unvalidated(
        "MATCH (n) WHERE NOT n:__BridgrWriteLock AND NOT n:__BridgrArtifact WITH count(n) AS node_count OPTIONAL MATCH ()-[r]->() RETURN node_count, count(r) AS relationship_count",
        {},
    )
    row = rows[0] if rows else {}
    if int(row.get("node_count", -1)) != snapshot_info.node_count or int(row.get("relationship_count", -1)) != snapshot_info.relationship_count:
        raise SnapshotError("Wiederherstellung konnte nicht über Objektzähler verifiziert werden.")


def _normalize_node(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "snapshot_node_id": str(row.get("snapshot_node_id", "")),
        "labels": [str(label) for label in row.get("labels", [])],
        "properties": _to_json_value(row.get("properties", {})),
    }


def _normalize_relationship(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "source_snapshot_node_id": str(row.get("source_snapshot_node_id", "")),
        "target_snapshot_node_id": str(row.get("target_snapshot_node_id", "")),
        "relationship_type": str(row.get("relationship_type", "")),
        "properties": _to_json_value(row.get("properties", {})),
    }


def _to_json_value(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, (date, datetime, time)):
        return value.isoformat()
    if isinstance(value, list):
        return [_to_json_value(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _to_json_value(item) for key, item in value.items()}
    raise SnapshotError(f"Nicht serialisierbarer Property-Typ im Snapshot: {type(value).__name__}")


def _create_node_query(labels: list[str]) -> str:
    if not labels or not all(label.isidentifier() for label in labels):
        raise SnapshotError("Snapshot enthält ungültige Knotenlabels.")
    labels_cypher = "".join(f":`{label}`" for label in labels)
    return (
        f"CREATE (n{labels_cypher}:`{RESTORE_LABEL}`) SET n = $properties, "
        f"n.`{RESTORE_REFERENCE_PROPERTY}` = $snapshot_node_id"
    )


def _create_relationship_query(relationship_type: str) -> str:
    if not relationship_type.isidentifier():
        raise SnapshotError("Snapshot enthält einen ungültigen Beziehungstyp.")
    return (
        f"MATCH (source:`{RESTORE_LABEL}` {{`{RESTORE_REFERENCE_PROPERTY}`: $source_snapshot_node_id}}) "
        f"MATCH (target:`{RESTORE_LABEL}` {{`{RESTORE_REFERENCE_PROPERTY}`: $target_snapshot_node_id}}) "
        f"CREATE (source)-[relationship:`{relationship_type}`]->(target) SET relationship = $properties"
    )


def _validate_graph_references(graph_payload: dict[str, list[dict[str, Any]]]) -> None:
    snapshot_node_ids: set[str] = set()
    for node in graph_payload["nodes"]:
        if not isinstance(node, dict):
            raise SnapshotError("Snapshot enthält einen ungültigen Knoten.")
        snapshot_node_id = node.get("snapshot_node_id")
        labels = node.get("labels")
        properties = node.get("properties")
        if not isinstance(snapshot_node_id, str) or not snapshot_node_id or snapshot_node_id in snapshot_node_ids:
            raise SnapshotError("Snapshot enthält leere oder doppelte Knotenreferenzen.")
        if not isinstance(labels, list) or not labels or not all(isinstance(label, str) and label.isidentifier() for label in labels):
            raise SnapshotError("Snapshot enthält ungültige Knotenlabels.")
        if not isinstance(properties, dict):
            raise SnapshotError("Snapshot enthält ungültige Knotenproperties.")
        snapshot_node_ids.add(snapshot_node_id)

    for relationship in graph_payload["relationships"]:
        if not isinstance(relationship, dict):
            raise SnapshotError("Snapshot enthält eine ungültige Beziehung.")
        source_id = relationship.get("source_snapshot_node_id")
        target_id = relationship.get("target_snapshot_node_id")
        relationship_type = relationship.get("relationship_type")
        properties = relationship.get("properties")
        if source_id not in snapshot_node_ids or target_id not in snapshot_node_ids:
            raise SnapshotError("Snapshot enthält eine Beziehung mit unbekanntem Knotenbezug.")
        if not isinstance(relationship_type, str) or not relationship_type.isidentifier():
            raise SnapshotError("Snapshot enthält einen ungültigen Beziehungstyp.")
        if not isinstance(properties, dict):
            raise SnapshotError("Snapshot enthält ungültige Beziehungsproperties.")


def _prune_snapshots(
    snapshot_root: Path,
    retention_count: int,
    *,
    keep_snapshot_id: str,
    protected_snapshot_ids: set[str],
) -> list[str]:
    valid_snapshots = [item for item in list_snapshots_from_root(snapshot_root) if item.valid]
    removed_snapshot_ids: list[str] = []
    for snapshot in valid_snapshots[retention_count:]:
        if snapshot.snapshot_id != keep_snapshot_id and snapshot.snapshot_id not in protected_snapshot_ids:
            shutil.rmtree(snapshot_root / snapshot.snapshot_id)
            removed_snapshot_ids.append(snapshot.snapshot_id)
    return removed_snapshot_ids


def list_snapshots_from_root(snapshot_root: Path) -> list[SnapshotInfo]:
    return sorted(
        [_validate_snapshot_directory(path) for path in snapshot_root.iterdir() if path.is_dir() and not path.name.startswith(".")],
        key=lambda item: item.created_at,
        reverse=True,
    )


def _snapshot_path(config: AppConfig, snapshot_id: str) -> Path:
    if not snapshot_id or snapshot_id != Path(snapshot_id).name:
        raise SnapshotError("Ungültige Snapshot-ID.")
    output_path, _ = resolve_runtime_output_path(config.output_path)
    return output_path / SNAPSHOT_DIRECTORY_NAME / snapshot_id


def _new_snapshot_id() -> str:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"{timestamp}_{uuid4().hex[:8]}"


def _safe_config_hint(config: AppConfig) -> dict[str, Any]:
    return {
        "input_path": config.input_path,
        "output_path": config.output_path,
        "last_run_mode": config.last_run_mode,
        "cmdb_type_files": config.cmdb_type_files,
    }

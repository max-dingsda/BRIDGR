from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from services.decision_service import create_manual_decision
from services.runtime_service import get_session_neo4j_client
from services.snapshot_service import SnapshotError, create_snapshot


@dataclass(frozen=True, slots=True)
class MergePreview:
    entity_type: str
    source_ref: str
    target_ref: str
    source_name: str
    target_name: str
    source_properties: dict[str, Any]
    target_properties: dict[str, Any]
    source_outgoing: list[dict[str, str]]
    source_incoming: list[dict[str, str]]
    target_outgoing_keys: list[str]
    target_incoming_keys: list[str]
    source_alias_names: list[str]
    target_alias_names: list[str]


def merge_org_units(config, source_name: str, target_name: str) -> tuple[str, str]:
    source = " ".join(source_name.strip().split())
    target = " ".join(target_name.strip().split())
    if not source or not target or source.casefold() == target.casefold():
        return "error", "Quelle und Ziel dürfen nicht leer oder identisch sein."
    return _perform_merge(config, "OrgUnit", source, target)


def get_org_unit_merge_preview(config, source_name: str, target_name: str) -> MergePreview:
    cleaned_source = " ".join(source_name.strip().split())
    cleaned_target = " ".join(target_name.strip().split())
    neo4j_client = get_session_neo4j_client(config)
    return _collect_org_unit_preview(neo4j_client, cleaned_source, cleaned_target)


def load_process_merge_candidates(config) -> list[dict[str, str]]:
    neo4j_client = get_session_neo4j_client(config)
    rows = neo4j_client.execute_read_unvalidated(
        """
        MATCH (p:Process)
        WHERE coalesce(p.placeholder, false) = false
        RETURN elementId(p) AS element_id,
               coalesce(p.process_id, '') AS process_id,
               coalesce(p.name, '') AS process_name
        ORDER BY toLower(coalesce(p.name, '')), toLower(coalesce(p.process_id, ''))
        """,
        {},
    )
    return [
        {
            "element_id": str(row.get("element_id", "")).strip(),
            "process_id": str(row.get("process_id", "")).strip(),
            "process_name": str(row.get("process_name", "")).strip(),
        }
        for row in rows
        if str(row.get("element_id", "")).strip()
    ]


def get_process_merge_preview(config, source_element_id: str, target_element_id: str) -> MergePreview:
    neo4j_client = get_session_neo4j_client(config)
    return _collect_process_preview(neo4j_client, source_element_id.strip(), target_element_id.strip())


def merge_processes(config, source_element_id: str, target_element_id: str) -> tuple[str, str]:
    source, target = source_element_id.strip(), target_element_id.strip()
    if not source or not target or source == target:
        return "error", "Quelle und Ziel dürfen nicht leer oder identisch sein."
    return _perform_merge(config, "Process", source, target)


def _perform_merge(config, label, source_ref, target_ref):
    from services.merge_state import merge
    from core.neo4j_utils import Neo4jExecutionError

    client = get_session_neo4j_client(config)
    try:
        with client.serialized_writes():
            create_snapshot(config, client, trigger="merge", operation="merge_org_unit" if label == "OrgUnit" else "merge_process")
            with client.transaction():
                if label == "OrgUnit":
                    rows = client.execute_read_unvalidated(
                        "MATCH (s:OrgUnit {name:$source}), (t:OrgUnit {name:$target}) "
                        "RETURN elementId(s) AS source, elementId(t) AS target",
                        {"source": source_ref, "target": target_ref},
                    )
                    if len(rows) != 1:
                        raise ValueError("Quelle oder Ziel wurde nicht eindeutig gefunden.")
                    source_ref, target_ref = rows[0]["source"], rows[0]["target"]
                payload = merge(client, label, source_ref, target_ref)
                create_manual_decision(client, "entity_merge", payload)
        return "success", f"{payload['source_name']} wurde in {payload['target_name']} überführt."
    except (ValueError, SnapshotError, Neo4jExecutionError) as exc:
        return "error", f"Merge wurde nicht durchgeführt: {exc}"




def _reference_projection(node_alias: str) -> str:
    return (
        "CASE "
        f"WHEN {node_alias}:Process THEN coalesce({node_alias}.process_id, {node_alias}.name, elementId({node_alias}), '') "
        f"WHEN {node_alias}:Application THEN coalesce({node_alias}.cmdb_id, {node_alias}.name, '') "
        f"WHEN {node_alias}:Interface OR {node_alias}:Server OR {node_alias}:Infrastructure THEN coalesce({node_alias}.id, {node_alias}.name, '') "
        f"WHEN {node_alias}:Alias THEN coalesce({node_alias}.name, {node_alias}.normalized_name, '') "
        f"ELSE coalesce({node_alias}.name, {node_alias}.cmdb_id, {node_alias}.id, {node_alias}.process_id, elementId({node_alias}), '') "
        "END"
    )


def _collect_org_unit_preview(neo4j_client, source_name: str, target_name: str) -> MergePreview:
    source_properties = _load_node_properties(
        neo4j_client,
        """
        MATCH (source:OrgUnit {name: $source_name})
        RETURN properties(source) AS props
        """,
        {"source_name": source_name},
    )
    target_properties = _load_node_properties(
        neo4j_client,
        """
        MATCH (target:OrgUnit {name: $target_name})
        RETURN properties(target) AS props
        """,
        {"target_name": target_name},
    )
    source_outgoing = _load_relationship_rows(
        neo4j_client,
        f"""
        MATCH (source:OrgUnit {{name: $source_name}})-[r]->(target)
        RETURN type(r) AS rel_type,
               [label IN labels(target) WHERE label <> '__BridgrIdentity'][0] AS other_label,
               {_reference_projection("target")} AS other_ref
        ORDER BY rel_type, other_label, other_ref
        """,
        {"source_name": source_name},
    )
    source_incoming = _load_relationship_rows(
        neo4j_client,
        f"""
        MATCH (other)-[r]->(source:OrgUnit {{name: $source_name}})
        RETURN type(r) AS rel_type,
               [label IN labels(other) WHERE label <> '__BridgrIdentity'][0] AS other_label,
               {_reference_projection("other")} AS other_ref
        ORDER BY rel_type, other_label, other_ref
        """,
        {"source_name": source_name},
    )
    target_outgoing_keys = _load_relationship_keys(
        neo4j_client,
        f"""
        MATCH (target:OrgUnit {{name: $target_name}})-[r]->(other)
        RETURN type(r) + '|' + [label IN labels(other) WHERE label <> '__BridgrIdentity'][0] + '|' + {_reference_projection("other")} AS rel_key
        ORDER BY rel_key
        """,
        {"target_name": target_name},
    )
    target_incoming_keys = _load_relationship_keys(
        neo4j_client,
        f"""
        MATCH (other)-[r]->(target:OrgUnit {{name: $target_name}})
        RETURN type(r) + '|' + [label IN labels(other) WHERE label <> '__BridgrIdentity'][0] + '|' + {_reference_projection("other")} AS rel_key
        ORDER BY rel_key
        """,
        {"target_name": target_name},
    )
    source_alias_names = _load_alias_names(
        neo4j_client,
        """
        MATCH (alias:Alias)-[:MAY_REFER_TO]->(:OrgUnit {name: $source_name})
        RETURN alias.name AS alias_name
        ORDER BY alias.name
        """,
        {"source_name": source_name},
    )
    target_alias_names = _load_alias_names(
        neo4j_client,
        """
        MATCH (alias:Alias)-[:MAY_REFER_TO]->(:OrgUnit {name: $target_name})
        RETURN alias.name AS alias_name
        ORDER BY alias.name
        """,
        {"target_name": target_name},
    )
    return MergePreview(
        entity_type="OrgUnit",
        source_ref=source_name,
        target_ref=target_name,
        source_name=source_name,
        target_name=target_name,
        source_properties=source_properties,
        target_properties=target_properties,
        source_outgoing=source_outgoing,
        source_incoming=source_incoming,
        target_outgoing_keys=target_outgoing_keys,
        target_incoming_keys=target_incoming_keys,
        source_alias_names=source_alias_names,
        target_alias_names=target_alias_names,
    )


def _collect_process_preview(neo4j_client, source_element_id: str, target_element_id: str) -> MergePreview:
    rows = neo4j_client.execute_read_unvalidated(
        """
        MATCH (source:Process)
        WHERE elementId(source) = $source_element_id
        MATCH (target:Process)
        WHERE elementId(target) = $target_element_id
        RETURN coalesce(source.name, source.process_id, '') AS source_name,
               coalesce(target.name, target.process_id, '') AS target_name,
               properties(source) AS source_props
        """,
        {
            "source_element_id": source_element_id,
            "target_element_id": target_element_id,
        },
    )
    row = rows[0] if rows else {}
    source_outgoing = _load_relationship_rows(
        neo4j_client,
        f"""
        MATCH (source:Process)-[r]->(target)
        WHERE elementId(source) = $source_element_id
        RETURN type(r) AS rel_type,
               [label IN labels(target) WHERE label <> '__BridgrIdentity'][0] AS other_label,
               {_reference_projection("target")} AS other_ref
        ORDER BY rel_type, other_label, other_ref
        """,
        {"source_element_id": source_element_id},
    )
    target_properties = _load_node_properties(
        neo4j_client,
        """
        MATCH (target:Process)
        WHERE elementId(target) = $target_element_id
        RETURN properties(target) AS props
        """,
        {"target_element_id": target_element_id},
    )
    source_incoming = _load_relationship_rows(
        neo4j_client,
        f"""
        MATCH (other)-[r]->(source:Process)
        WHERE elementId(source) = $source_element_id
        RETURN type(r) AS rel_type,
               [label IN labels(other) WHERE label <> '__BridgrIdentity'][0] AS other_label,
               {_reference_projection("other")} AS other_ref
        ORDER BY rel_type, other_label, other_ref
        """,
        {"source_element_id": source_element_id},
    )
    target_outgoing_keys = _load_relationship_keys(
        neo4j_client,
        f"""
        MATCH (target:Process)-[r]->(other)
        WHERE elementId(target) = $target_element_id
        RETURN type(r) + '|' + [label IN labels(other) WHERE label <> '__BridgrIdentity'][0] + '|' + {_reference_projection("other")} AS rel_key
        ORDER BY rel_key
        """,
        {"target_element_id": target_element_id},
    )
    target_incoming_keys = _load_relationship_keys(
        neo4j_client,
        f"""
        MATCH (other)-[r]->(target:Process)
        WHERE elementId(target) = $target_element_id
        RETURN type(r) + '|' + [label IN labels(other) WHERE label <> '__BridgrIdentity'][0] + '|' + {_reference_projection("other")} AS rel_key
        ORDER BY rel_key
        """,
        {"target_element_id": target_element_id},
    )
    source_alias_names = _load_alias_names(
        neo4j_client,
        """
        MATCH (alias:Alias)-[:MAY_REFER_TO]->(source:Process)
        WHERE elementId(source) = $source_element_id
        RETURN alias.name AS alias_name
        ORDER BY alias.name
        """,
        {"source_element_id": source_element_id},
    )
    target_alias_names = _load_alias_names(
        neo4j_client,
        """
        MATCH (alias:Alias)-[:MAY_REFER_TO]->(target:Process)
        WHERE elementId(target) = $target_element_id
        RETURN alias.name AS alias_name
        ORDER BY alias.name
        """,
        {"target_element_id": target_element_id},
    )
    return MergePreview(
        entity_type="Process",
        source_ref=source_element_id,
        target_ref=target_element_id,
        source_name=str(row.get("source_name", "")).strip(),
        target_name=str(row.get("target_name", "")).strip(),
        source_properties=dict(row.get("source_props") or {}),
        target_properties=target_properties,
        source_outgoing=source_outgoing,
        source_incoming=source_incoming,
        target_outgoing_keys=target_outgoing_keys,
        target_incoming_keys=target_incoming_keys,
        source_alias_names=source_alias_names,
        target_alias_names=target_alias_names,
    )


def _load_node_properties(neo4j_client, query: str, parameters: dict[str, str]) -> dict[str, Any]:
    rows = neo4j_client.execute_read_unvalidated(query, parameters)
    return dict((rows[0] if rows else {}).get("props") or {})


def _load_relationship_rows(neo4j_client, query: str, parameters: dict[str, str]) -> list[dict[str, str]]:
    rows = neo4j_client.execute_read_unvalidated(query, parameters)
    return [
        {
            "rel_type": str(row.get("rel_type", "")).strip(),
            "other_label": str(row.get("other_label", "")).strip(),
            "other_ref": str(row.get("other_ref", "")).strip(),
        }
        for row in rows
        if str(row.get("rel_type", "")).strip() and str(row.get("other_label", "")).strip()
    ]


def _load_relationship_keys(neo4j_client, query: str, parameters: dict[str, str]) -> list[str]:
    rows = neo4j_client.execute_read_unvalidated(query, parameters)
    return [str(row.get("rel_key", "")).strip() for row in rows if str(row.get("rel_key", "")).strip()]


def _load_alias_names(neo4j_client, query: str, parameters: dict[str, str]) -> list[str]:
    rows = neo4j_client.execute_read_unvalidated(query, parameters)
    return [str(row.get("alias_name", "")).strip() for row in rows if str(row.get("alias_name", "")).strip()]

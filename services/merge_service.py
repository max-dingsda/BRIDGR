from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from services.alias_service import write_merged_org_unit_alias, write_merged_process_alias
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
    cleaned_source = " ".join(source_name.strip().split())
    cleaned_target = " ".join(target_name.strip().split())
    if not cleaned_source or not cleaned_target:
        return "error", "Quelle und Goal dürfen nicht leer sein."
    if cleaned_source.casefold() == cleaned_target.casefold():
        return "error", "Quelle und Goal dürfen nicht identisch sein."

    neo4j_client = get_session_neo4j_client(config)
    try:
        create_snapshot(
            config,
            neo4j_client,
            trigger="merge",
            operation="merge_org_unit",
        )
    except SnapshotError as exc:
        return "error", f"Merge wurde nicht gestartet: {exc}"
    preview = _collect_org_unit_preview(neo4j_client, cleaned_source, cleaned_target)
    _merge_org_unit_relationships(neo4j_client, cleaned_source, cleaned_target)
    write_merged_org_unit_alias(neo4j_client, cleaned_source, cleaned_target)
    neo4j_client.execute_write(
        """
        MATCH (source:OrgUnit {name: $source_name})
        DETACH DELETE source
        """,
        {
            "source_name": cleaned_source,
        },
    )
    create_manual_decision(
        neo4j_client,
        "entity_merge",
        {
            "entity_type": "OrgUnit",
            "source_name": cleaned_source,
            "target_name": cleaned_target,
            "source_ref": cleaned_source,
            "target_ref": cleaned_target,
            "merge_preview": _serialize_preview(preview),
        },
    )
    return "success", f"Organisationseinheit '{cleaned_source}' wurde in '{cleaned_target}' überführt."


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
    source_ref = source_element_id.strip()
    target_ref = target_element_id.strip()
    if not source_ref or not target_ref:
        return "error", "Quelle und Goal dürfen nicht leer sein."
    if source_ref == target_ref:
        return "error", "Quelle und Goal dürfen nicht identisch sein."

    neo4j_client = get_session_neo4j_client(config)
    try:
        create_snapshot(
            config,
            neo4j_client,
            trigger="merge",
            operation="merge_process",
        )
    except SnapshotError as exc:
        return "error", f"Merge wurde nicht gestartet: {exc}"
    preview = _collect_process_preview(neo4j_client, source_ref, target_ref)
    if preview.source_name.casefold() == preview.target_name.casefold() and preview.source_properties.get("process_id", "").strip() == preview.source_properties.get("process_id", "").strip():
        # same element ids are already blocked above; this only keeps messages stable for near-identical selections
        pass
    _merge_process_properties(neo4j_client, source_ref, target_ref)
    _merge_process_relationships(neo4j_client, source_ref, target_ref)
    write_merged_process_alias(neo4j_client, preview.source_name, target_element_id=target_ref)
    neo4j_client.execute_write(
        """
        MATCH (source:Process)
        WHERE elementId(source) = $source_element_id
        DETACH DELETE source
        """,
        {"source_element_id": source_ref},
    )
    create_manual_decision(
        neo4j_client,
        "entity_merge",
        {
            "entity_type": "Process",
            "source_name": preview.source_name,
            "target_name": preview.target_name,
            "source_ref": source_ref,
            "target_ref": target_ref,
            "merge_preview": _serialize_preview(preview),
        },
    )
    return "success", f"Process '{preview.source_name}' wurde in '{preview.target_name}' überführt."


def _serialize_preview(preview: MergePreview) -> dict[str, Any]:
    return {
        "entity_type": preview.entity_type,
        "source_ref": preview.source_ref,
        "target_ref": preview.target_ref,
        "source_name": preview.source_name,
        "target_name": preview.target_name,
        "source_properties": preview.source_properties,
        "target_properties": preview.target_properties,
        "source_outgoing": preview.source_outgoing,
        "source_incoming": preview.source_incoming,
        "target_outgoing_keys": preview.target_outgoing_keys,
        "target_incoming_keys": preview.target_incoming_keys,
        "source_alias_names": preview.source_alias_names,
        "target_alias_names": preview.target_alias_names,
    }


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
               labels(target)[0] AS other_label,
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
               labels(other)[0] AS other_label,
               {_reference_projection("other")} AS other_ref
        ORDER BY rel_type, other_label, other_ref
        """,
        {"source_name": source_name},
    )
    target_outgoing_keys = _load_relationship_keys(
        neo4j_client,
        f"""
        MATCH (target:OrgUnit {{name: $target_name}})-[r]->(other)
        RETURN type(r) + '|' + labels(other)[0] + '|' + {_reference_projection("other")} AS rel_key
        ORDER BY rel_key
        """,
        {"target_name": target_name},
    )
    target_incoming_keys = _load_relationship_keys(
        neo4j_client,
        f"""
        MATCH (other)-[r]->(target:OrgUnit {{name: $target_name}})
        RETURN type(r) + '|' + labels(other)[0] + '|' + {_reference_projection("other")} AS rel_key
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
               labels(target)[0] AS other_label,
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
               labels(other)[0] AS other_label,
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
        RETURN type(r) + '|' + labels(other)[0] + '|' + {_reference_projection("other")} AS rel_key
        ORDER BY rel_key
        """,
        {"target_element_id": target_element_id},
    )
    target_incoming_keys = _load_relationship_keys(
        neo4j_client,
        f"""
        MATCH (other)-[r]->(target:Process)
        WHERE elementId(target) = $target_element_id
        RETURN type(r) + '|' + labels(other)[0] + '|' + {_reference_projection("other")} AS rel_key
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


def _merge_org_unit_relationships(neo4j_client, source_name: str, target_name: str) -> None:
    neo4j_client.execute_write(
        """
        MATCH (source:OrgUnit {name: $source_name})
        MATCH (target:OrgUnit {name: $target_name})
        MATCH (source)-[:RESPONSIBLE_FOR]->(p:Process)
        WHERE elementId(source) <> elementId(target)
        MERGE (target)-[:RESPONSIBLE_FOR]->(p)
        """,
        {"source_name": source_name, "target_name": target_name},
    )
    neo4j_client.execute_write(
        """
        MATCH (source:OrgUnit {name: $source_name})
        MATCH (target:OrgUnit {name: $target_name})
        MATCH (source)-[:RESPONSIBLE_FOR]->(a:Application)
        WHERE elementId(source) <> elementId(target)
        MERGE (target)-[:RESPONSIBLE_FOR]->(a)
        """,
        {"source_name": source_name, "target_name": target_name},
    )
    neo4j_client.execute_write(
        """
        MATCH (source:OrgUnit {name: $source_name})
        MATCH (target:OrgUnit {name: $target_name})
        MATCH (source)-[:RESPONSIBLE_FOR]->(i:Interface)
        WHERE elementId(source) <> elementId(target)
        MERGE (target)-[:RESPONSIBLE_FOR]->(i)
        """,
        {"source_name": source_name, "target_name": target_name},
    )
    neo4j_client.execute_write(
        """
        MATCH (source:OrgUnit {name: $source_name})
        MATCH (target:OrgUnit {name: $target_name})
        MATCH (source)-[:RESPONSIBLE_FOR]->(s:Server)
        WHERE elementId(source) <> elementId(target)
        MERGE (target)-[:RESPONSIBLE_FOR]->(s)
        """,
        {"source_name": source_name, "target_name": target_name},
    )
    neo4j_client.execute_write(
        """
        MATCH (source:OrgUnit {name: $source_name})
        MATCH (target:OrgUnit {name: $target_name})
        MATCH (source)-[:RESPONSIBLE_FOR]->(i:Infrastructure)
        WHERE elementId(source) <> elementId(target)
        MERGE (target)-[:RESPONSIBLE_FOR]->(i)
        """,
        {"source_name": source_name, "target_name": target_name},
    )
    neo4j_client.execute_write(
        """
        MATCH (source:OrgUnit {name: $source_name})
        MATCH (target:OrgUnit {name: $target_name})
        MATCH (source)-[:CAN_ASSUME]->(r:Role)
        WHERE elementId(source) <> elementId(target)
        MERGE (target)-[:CAN_ASSUME]->(r)
        """,
        {"source_name": source_name, "target_name": target_name},
    )
    neo4j_client.execute_write(
        """
        MATCH (source:OrgUnit {name: $source_name})
        MATCH (target:OrgUnit {name: $target_name})
        MATCH (source)-[:CONNECTED_TO]->(n)
        WHERE elementId(source) <> elementId(target)
        MERGE (target)-[:CONNECTED_TO]->(n)
        """,
        {"source_name": source_name, "target_name": target_name},
    )
    neo4j_client.execute_write(
        """
        MATCH (source:OrgUnit {name: $source_name})
        MATCH (target:OrgUnit {name: $target_name})
        MATCH (alias:Alias)-[:MAY_REFER_TO]->(source)
        WHERE elementId(source) <> elementId(target)
        MERGE (alias)-[:MAY_REFER_TO]->(target)
        """,
        {"source_name": source_name, "target_name": target_name},
    )


def _merge_process_properties(neo4j_client, source_element_id: str, target_element_id: str) -> None:
    neo4j_client.execute_write(
        """
        MATCH (source:Process)
        WHERE elementId(source) = $source_element_id
        MATCH (target:Process)
        WHERE elementId(target) = $target_element_id
        SET target.process_id = coalesce(target.process_id, source.process_id),
            target.archimate_id = coalesce(target.archimate_id, source.archimate_id),
            target.archimate_type = coalesce(target.archimate_type, source.archimate_type),
            target.archimate_source = coalesce(target.archimate_source, source.archimate_source),
            target.name = coalesce(target.name, source.name),
            target.placeholder = coalesce(target.placeholder, source.placeholder, false)
        """,
        {
            "source_element_id": source_element_id,
            "target_element_id": target_element_id,
        },
    )


def _merge_process_relationships(neo4j_client, source_element_id: str, target_element_id: str) -> None:
    for query in (
        """
        MATCH (source:Process)
        WHERE elementId(source) = $source_element_id
        MATCH (target:Process)
        WHERE elementId(target) = $target_element_id
        MATCH (a:Application)-[r:SERVES]->(source)
        WHERE elementId(source) <> elementId(target)
        MERGE (a)-[merged:SERVES]->(target)
        SET merged.confidence = coalesce(merged.confidence, r.confidence),
            merged.raw_name = coalesce(merged.raw_name, r.raw_name),
            merged.source = coalesce(merged.source, r.source)
        """,
        """
        MATCH (source:Process)
        WHERE elementId(source) = $source_element_id
        MATCH (target:Process)
        WHERE elementId(target) = $target_element_id
        MATCH (a:Application)-[r:MAY_SERVE]->(source)
        WHERE elementId(source) <> elementId(target)
        MERGE (a)-[merged:MAY_SERVE]->(target)
        SET merged.score = coalesce(merged.score, r.score)
        """,
        """
        MATCH (source:Process)
        WHERE elementId(source) = $source_element_id
        MATCH (target:Process)
        WHERE elementId(target) = $target_element_id
        MATCH (role:Role)-[:PARTICIPATES_IN]->(source)
        WHERE elementId(source) <> elementId(target)
        MERGE (role)-[:PARTICIPATES_IN]->(target)
        """,
        """
        MATCH (source:Process)
        WHERE elementId(source) = $source_element_id
        MATCH (target:Process)
        WHERE elementId(target) = $target_element_id
        MATCH (org:OrgUnit)-[:RESPONSIBLE_FOR]->(source)
        WHERE elementId(source) <> elementId(target)
        MERGE (org)-[:RESPONSIBLE_FOR]->(target)
        """,
        """
        MATCH (source:Process)
        WHERE elementId(source) = $source_element_id
        MATCH (target:Process)
        WHERE elementId(target) = $target_element_id
        MATCH (source)-[:FOLLOWS]->(previous:Process)
        WHERE elementId(source) <> elementId(target) AND elementId(previous) <> elementId(target)
        MERGE (target)-[:FOLLOWS]->(previous)
        """,
        """
        MATCH (source:Process)
        WHERE elementId(source) = $source_element_id
        MATCH (target:Process)
        WHERE elementId(target) = $target_element_id
        MATCH (successor:Process)-[:FOLLOWS]->(source)
        WHERE elementId(source) <> elementId(target) AND elementId(successor) <> elementId(target)
        MERGE (successor)-[:FOLLOWS]->(target)
        """,
        """
        MATCH (source:Process)
        WHERE elementId(source) = $source_element_id
        MATCH (target:Process)
        WHERE elementId(target) = $target_element_id
        MATCH (n)-[:REALIZES]->(source)
        WHERE elementId(source) <> elementId(target)
        MERGE (n)-[:REALIZES]->(target)
        """,
        """
        MATCH (source:Process)
        WHERE elementId(source) = $source_element_id
        MATCH (target:Process)
        WHERE elementId(target) = $target_element_id
        MATCH (n)-[:SUPPORTS]->(source)
        WHERE elementId(source) <> elementId(target)
        MERGE (n)-[:SUPPORTS]->(target)
        """,
        """
        MATCH (source:Process)
        WHERE elementId(source) = $source_element_id
        MATCH (target:Process)
        WHERE elementId(target) = $target_element_id
        MATCH (n)-[:REQUIRES]->(source)
        WHERE elementId(source) <> elementId(target)
        MERGE (n)-[:REQUIRES]->(target)
        """,
        """
        MATCH (source:Process)
        WHERE elementId(source) = $source_element_id
        MATCH (target:Process)
        WHERE elementId(target) = $target_element_id
        MATCH (n)-[:PROCESSES]->(source)
        WHERE elementId(source) <> elementId(target)
        MERGE (n)-[:PROCESSES]->(target)
        """,
        """
        MATCH (source:Process)
        WHERE elementId(source) = $source_element_id
        MATCH (target:Process)
        WHERE elementId(target) = $target_element_id
        MATCH (n)-[:AFFECTS]->(source)
        WHERE elementId(source) <> elementId(target)
        MERGE (n)-[:AFFECTS]->(target)
        """,
        """
        MATCH (source:Process)
        WHERE elementId(source) = $source_element_id
        MATCH (target:Process)
        WHERE elementId(target) = $target_element_id
        MATCH (n)-[:INFLUENCES]->(source)
        WHERE elementId(source) <> elementId(target)
        MERGE (n)-[:INFLUENCES]->(target)
        """,
        """
        MATCH (source:Process)
        WHERE elementId(source) = $source_element_id
        MATCH (target:Process)
        WHERE elementId(target) = $target_element_id
        MATCH (source)-[:SUPPORTS]->(n)
        WHERE elementId(source) <> elementId(target) AND elementId(n) <> elementId(target)
        MERGE (target)-[:SUPPORTS]->(n)
        """,
        """
        MATCH (source:Process)
        WHERE elementId(source) = $source_element_id
        MATCH (target:Process)
        WHERE elementId(target) = $target_element_id
        MATCH (source)-[:REQUIRES]->(n)
        WHERE elementId(source) <> elementId(target) AND elementId(n) <> elementId(target)
        MERGE (target)-[:REQUIRES]->(n)
        """,
        """
        MATCH (source:Process)
        WHERE elementId(source) = $source_element_id
        MATCH (target:Process)
        WHERE elementId(target) = $target_element_id
        MATCH (source)-[:PROCESSES]->(n)
        WHERE elementId(source) <> elementId(target) AND elementId(n) <> elementId(target)
        MERGE (target)-[:PROCESSES]->(n)
        """,
        """
        MATCH (source:Process)
        WHERE elementId(source) = $source_element_id
        MATCH (target:Process)
        WHERE elementId(target) = $target_element_id
        MATCH (alias:Alias)-[:MAY_REFER_TO]->(source)
        WHERE elementId(source) <> elementId(target)
        MERGE (alias)-[:MAY_REFER_TO]->(target)
        """,
    ):
        neo4j_client.execute_write(
            query,
            {
                "source_element_id": source_element_id,
                "target_element_id": target_element_id,
            },
        )

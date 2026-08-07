from __future__ import annotations

import json

from core.app_config import AppConfig
from core.constants import ALIAS_SOURCE_KIND_CONFIRMED_MATCH, ALIAS_SOURCE_KIND_MERGED_ENTITY
from core.neo4j_utils import Neo4jExecutionError
from services.cmdb_service import load_all_cmdb_rows
from services.alias_service import (
    delete_application_alias,
    delete_org_unit_alias,
    delete_process_alias,
    normalize_alias_name,
)
from services.decision_service import (
    create_manual_decision,
    get_manual_decision,
    mark_manual_decision_reverted,
)
from services.review_service import persist_single_document_refresh
from services.runtime_service import get_session_neo4j_client


def revert_manual_decision(config: AppConfig, decision_id: str) -> tuple[str, str]:
    neo4j_client = get_session_neo4j_client(config)
    decision = get_manual_decision(neo4j_client, decision_id)
    if decision is None:
        return "error", "Entscheidung wurde nicht gefunden."
    if decision.status != "active":
        return "warning", "Entscheidung ist bereits zurückgenommen oder nicht aktiv."

    payload = json.loads(decision.payload_json or "{}")
    handlers = {
        "manual_link": _revert_manual_link,
        "confirmed_candidate_link": _revert_confirmed_candidate_link,
        "manual_process_owner_assignment": _revert_process_owner_assignment,
        "manual_role_assignment": _revert_role_assignment,
        "entity_merge": _revert_entity_merge,
    }
    handler = handlers.get(decision.decision_type)
    if handler is None:
        return "error", f"Entscheidungstyp `{decision.decision_type}` wird noch nicht unterstützt."

    try:
        message = handler(config, neo4j_client, payload)
    except ValueError as exc:
        return "error", str(exc)
    except Neo4jExecutionError as exc:
        return "error", str(exc)
    except Exception as exc:
        return "error", f"Rücknahme fehlgeschlagen: {exc}"
    mark_manual_decision_reverted(neo4j_client, decision_id)
    try:
        create_manual_decision(
            neo4j_client,
            "decision_revert",
            {"reverted_decision_id": decision_id, "reverted_type": decision.decision_type},
            status="reverted",
            supersedes_decision_id=decision_id,
        )
    except Neo4jExecutionError as exc:
        return "warning", (
            "Rücknahme wurde fachlich ausgeführt, aber der Rücknahme-Eintrag konnte nicht vollständig protokolliert werden: "
            f"{exc}"
        )
    return "success", message


def _revert_manual_link(config: AppConfig, neo4j_client, payload: dict) -> str:
    process_id = str(payload.get("process_id", ""))
    cmdb_id = str(payload.get("cmdb_id", ""))
    application_name = str(payload.get("application_name", ""))
    source_path = str(payload.get("source_path", ""))
    neo4j_client.execute_write(
        """
        MATCH (a:Application {cmdb_id: $cmdb_id})-[r:SERVES]->(p:Process {process_id: $process_id})
        WHERE r.source = 'manueller_link' AND r.raw_name = $raw_name
        DELETE r
        """,
        {
            "cmdb_id": cmdb_id,
            "process_id": process_id,
            "raw_name": application_name,
        },
    )
    _refresh_document_if_possible(config, source_path)
    return f"Manueller Link fuer '{application_name}' wurde zurückgenommen."


def _revert_confirmed_candidate_link(config: AppConfig, neo4j_client, payload: dict) -> str:
    process_id = str(payload.get("process_id", ""))
    cmdb_id = str(payload.get("cmdb_id", ""))
    application_name = str(payload.get("application_name", ""))
    matched_name = str(payload.get("matched_name", ""))
    source_path = str(payload.get("source_path", ""))
    neo4j_client.execute_write(
        """
        MATCH (a:Application {cmdb_id: $cmdb_id})-[r:SERVES]->(p:Process {process_id: $process_id})
        WHERE r.source = 'manuell_bestaetigt' AND r.raw_name = $raw_name
        DELETE r
        """,
        {
            "cmdb_id": cmdb_id,
            "process_id": process_id,
            "raw_name": application_name,
        },
    )
    if normalize_alias_name(application_name) != normalize_alias_name(matched_name):
        delete_application_alias(
            neo4j_client,
            application_name,
            cmdb_id,
            source_kind=ALIAS_SOURCE_KIND_CONFIRMED_MATCH,
        )
    _refresh_document_if_possible(config, source_path)
    return f"Bestätigter Kandidat fuer '{application_name}' wurde zurückgenommen."


def _revert_process_owner_assignment(config: AppConfig, neo4j_client, payload: dict) -> str:
    process_id = str(payload.get("process_id", ""))
    org_unit_name = str(payload.get("org_unit_name", ""))
    neo4j_client.execute_write(
        """
        MATCH (o:OrgUnit {name: $org_unit_name})-[r:RESPONSIBLE_FOR]->(p:Process {process_id: $process_id})
        DELETE r
        """,
        {
            "org_unit_name": org_unit_name,
            "process_id": process_id,
        },
    )
    return f"Eigentümer-Zuordnung fuer Process '{process_id}' wurde entfernt."


def _revert_role_assignment(config: AppConfig, neo4j_client, payload: dict) -> str:
    role_name = str(payload.get("role_name", ""))
    org_unit_name = str(payload.get("org_unit_name", ""))
    neo4j_client.execute_write(
        """
        MATCH (o:OrgUnit {name: $org_unit_name})-[r:CAN_ASSUME]->(role:Role {name: $role_name})
        DELETE r
        """,
        {
            "org_unit_name": org_unit_name,
            "role_name": role_name,
        },
    )
    return f"Rolenzuordnung '{role_name}' -> '{org_unit_name}' wurde entfernt."


def _revert_entity_merge(config: AppConfig, neo4j_client, payload: dict) -> str:
    merge_preview = payload.get("merge_preview") or {}
    entity_type = str(payload.get("entity_type", "")).strip()
    if entity_type == "OrgUnit":
        return _revert_org_unit_merge(neo4j_client, payload, merge_preview)
    if entity_type == "Process":
        return _revert_process_merge(neo4j_client, payload, merge_preview)
    raise ValueError(f"Nicht unterstützter Merge-Typ: {entity_type}")


def _revert_org_unit_merge(neo4j_client, payload: dict, merge_preview: dict) -> str:
    source_name = str(payload.get("source_name", "")).strip()
    target_name = str(payload.get("target_name", "")).strip()
    source_properties = dict(merge_preview.get("source_properties") or {})
    if not source_name or not target_name:
        raise ValueError("Merge-Payload ist unvollständig.")

    neo4j_client.execute_write(
        """
        MERGE (source:OrgUnit {name: $source_name})
        SET source += $source_properties
        """,
        {
            "source_name": source_name,
            "source_properties": source_properties,
        },
    )

    _restore_snapshot_relationships(
        neo4j_client,
        source_ref=source_name,
        target_ref=target_name,
        merge_preview=merge_preview,
        entity_type="OrgUnit",
    )
    delete_org_unit_alias(
        neo4j_client,
        source_name,
        target_name,
        source_kind=ALIAS_SOURCE_KIND_MERGED_ENTITY,
    )
    return f"Merge für Organisationseinheit '{source_name}' wurde zurückgenommen."


def _revert_process_merge(neo4j_client, payload: dict, merge_preview: dict) -> str:
    source_name = str(payload.get("source_name", "")).strip()
    target_ref = str(payload.get("target_ref", "")).strip()
    source_properties = dict(merge_preview.get("source_properties") or {})
    target_properties = dict(merge_preview.get("target_properties") or {})
    process_id = str(source_properties.get("process_id", "")).strip()
    target_process_id = str(target_properties.get("process_id", "")).strip()
    if not target_ref or not source_name:
        raise ValueError("Merge-Payload ist unvollständig.")

    if target_process_id:
        neo4j_client.execute_write(
            """
            MATCH (target:Process)
            WHERE elementId(target) = $target_ref
            SET target.process_id = $target_process_id
            """,
            {"target_ref": target_ref, "target_process_id": target_process_id},
        )
    else:
        neo4j_client.execute_write(
            """
            MATCH (target:Process)
            WHERE elementId(target) = $target_ref
            REMOVE target.process_id
            """,
            {"target_ref": target_ref},
        )

    restored_rows = neo4j_client.execute_read_unvalidated(
        """
        MATCH (source:Process)
        WHERE ($process_id <> '' AND coalesce(source.process_id, '') = $process_id)
           OR ($process_id = '' AND source.name = $source_name)
        RETURN elementId(source) AS element_id
        ORDER BY elementId(source) DESC
        LIMIT 1
        """,
        {
            "process_id": process_id,
            "source_name": source_name,
        },
    )
    if restored_rows:
        source_ref = str(restored_rows[0].get("element_id", "")).strip()
        neo4j_client.execute_write(
            """
            MATCH (source:Process)
            WHERE elementId(source) = $source_ref
            SET source += $source_properties
            """,
            {
                "source_ref": source_ref,
                "source_properties": source_properties,
            },
        )
    else:
        neo4j_client.execute_write(
            """
            CREATE (source:Process)
            SET source += $source_properties
            RETURN elementId(source) AS element_id
            """,
            {"source_properties": source_properties},
        )

        restored_rows = neo4j_client.execute_read_unvalidated(
            """
            MATCH (source:Process)
            WHERE ($process_id <> '' AND coalesce(source.process_id, '') = $process_id)
               OR ($process_id = '' AND source.name = $source_name)
            RETURN elementId(source) AS element_id
            ORDER BY elementId(source) DESC
            LIMIT 1
            """,
            {
                "process_id": process_id,
                "source_name": source_name,
            },
        )
        source_ref = str((restored_rows[0] if restored_rows else {}).get("element_id", "")).strip()
    if not source_ref:
        raise ValueError("Quellprozess konnte für die Rücknahme nicht wiedergefunden werden.")

    _restore_snapshot_relationships(
        neo4j_client,
        source_ref=source_ref,
        target_ref=target_ref,
        merge_preview=merge_preview,
        entity_type="Process",
    )
    delete_process_alias(
        neo4j_client,
        source_name,
        target_element_id=target_ref,
        source_kind=ALIAS_SOURCE_KIND_MERGED_ENTITY,
    )
    return f"Merge für Process '{source_name}' wurde zurückgenommen."


def _restore_snapshot_relationships(
    neo4j_client,
    *,
    source_ref: str,
    target_ref: str,
    merge_preview: dict,
    entity_type: str,
) -> None:
    target_outgoing_keys = set(str(entry).strip() for entry in merge_preview.get("target_outgoing_keys", []) if str(entry).strip())
    target_incoming_keys = set(str(entry).strip() for entry in merge_preview.get("target_incoming_keys", []) if str(entry).strip())

    for rel in merge_preview.get("source_outgoing", []):
        rel_type = str(rel.get("rel_type", "")).strip()
        other_label = str(rel.get("other_label", "")).strip()
        other_ref = str(rel.get("other_ref", "")).strip()
        if not rel_type or not other_label:
            continue
        rel_key = f"{rel_type}|{other_label}|{other_ref}"
        _recreate_relationship(neo4j_client, entity_type, source_ref, rel_type, other_label, other_ref, outgoing=True)
        if rel_key not in target_outgoing_keys:
            _delete_relationship(neo4j_client, entity_type, target_ref, rel_type, other_label, other_ref, outgoing=True)

    for rel in merge_preview.get("source_incoming", []):
        rel_type = str(rel.get("rel_type", "")).strip()
        other_label = str(rel.get("other_label", "")).strip()
        other_ref = str(rel.get("other_ref", "")).strip()
        if not rel_type or not other_label:
            continue
        rel_key = f"{rel_type}|{other_label}|{other_ref}"
        _recreate_relationship(neo4j_client, entity_type, source_ref, rel_type, other_label, other_ref, outgoing=False)
        if rel_key not in target_incoming_keys:
            _delete_relationship(neo4j_client, entity_type, target_ref, rel_type, other_label, other_ref, outgoing=False)


def _recreate_relationship(neo4j_client, entity_type: str, source_ref: str, rel_type: str, other_label: str, other_ref: str, *, outgoing: bool) -> None:
    match_source = _node_match("source", entity_type)
    match_other = _node_match("other", other_label)
    if outgoing:
        query = f"""
        {match_source}
        {match_other}
        MERGE (source)-[:{rel_type}]->(other)
        """
    else:
        query = f"""
        {match_source}
        {match_other}
        MERGE (other)-[:{rel_type}]->(source)
        """
    neo4j_client.execute_write(query, {"source_ref": source_ref, "other_ref": other_ref})


def _delete_relationship(neo4j_client, entity_type: str, source_ref: str, rel_type: str, other_label: str, other_ref: str, *, outgoing: bool) -> None:
    match_source = _node_match("source", entity_type)
    match_other = _node_match("other", other_label)
    if outgoing:
        query = f"""
        {match_source}
        {match_other}
        MATCH (source)-[r:{rel_type}]->(other)
        DELETE r
        """
    else:
        query = f"""
        {match_source}
        {match_other}
        MATCH (other)-[r:{rel_type}]->(source)
        DELETE r
        """
    neo4j_client.execute_write(query, {"source_ref": source_ref, "other_ref": other_ref})


def _node_match(alias: str, label: str) -> str:
    parameter = "$source_ref" if alias == "source" else "$other_ref"
    if label == "OrgUnit":
        return f"MATCH ({alias}:OrgUnit {{name: {parameter}}})"
    if label in {"Requirement", "Capability", "Context", "Resource", "Risk", "Stakeholder", "Goal"}:
        return f"MATCH ({alias}:{label} {{name: {parameter}}})"
    if label == "Process":
        return (
            f"MATCH ({alias}:Process) "
            f"WHERE elementId({alias}) = {parameter} "
            f"   OR coalesce({alias}.process_id, '') = {parameter} "
            f"   OR coalesce({alias}.name, '') = {parameter}"
        )
    if label == "Application":
        return (
            f"MATCH ({alias}:Application) "
            f"WHERE coalesce({alias}.cmdb_id, '') = {parameter} "
            f"   OR coalesce({alias}.name, '') = {parameter}"
        )
    if label in {"Interface", "Server", "Infrastructure"}:
        return (
            f"MATCH ({alias}:{label}) "
            f"WHERE coalesce({alias}.id, '') = {parameter} "
            f"   OR coalesce({alias}.name, '') = {parameter}"
        )
    if label == "Role":
        return f"MATCH ({alias}:Role {{name: {parameter}}})"
    if label == "Alias":
        return (
            f"MATCH ({alias}:Alias) "
            f"WHERE coalesce({alias}.name, '') = {parameter} "
            f"   OR coalesce({alias}.normalized_name, '') = {parameter}"
        )
    raise ValueError(f"Nicht unterstütztes Label in Merge-Rücknahme: {label}")


def _refresh_document_if_possible(config: AppConfig, source_path: str) -> None:
    if not source_path:
        return
    cmdb_rows = load_all_cmdb_rows(config)
    persist_single_document_refresh(config, source_path, cmdb_rows)

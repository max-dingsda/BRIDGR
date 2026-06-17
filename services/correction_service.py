from __future__ import annotations

import json

from core.app_config import AppConfig, resolve_input_cmdb_path
from core.constants import ALIAS_SOURCE_KIND_CONFIRMED_MATCH
from processing.cmdb import CmdbLoadError, load_cmdb_rows
from services.alias_service import delete_application_alias, normalize_alias_name
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
    }
    handler = handlers.get(decision.decision_type)
    if handler is None:
        return "error", f"Entscheidungstyp `{decision.decision_type}` wird noch nicht unterstützt."

    message = handler(config, neo4j_client, payload)
    mark_manual_decision_reverted(neo4j_client, decision_id)
    create_manual_decision(
        neo4j_client,
        "decision_revert",
        {"reverted_decision_id": decision_id, "reverted_type": decision.decision_type},
        supersedes_decision_id=decision_id,
    )
    return "success", message


def _revert_manual_link(config: AppConfig, neo4j_client, payload: dict) -> str:
    process_id = str(payload.get("process_id", ""))
    cmdb_id = str(payload.get("cmdb_id", ""))
    application_name = str(payload.get("application_name", ""))
    source_path = str(payload.get("source_path", ""))
    neo4j_client.execute_write(
        """
        MATCH (a:Anwendung {cmdb_id: $cmdb_id})-[r:DIENT]->(p:Prozess {prozess_id: $process_id})
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
        MATCH (a:Anwendung {cmdb_id: $cmdb_id})-[r:DIENT]->(p:Prozess {prozess_id: $process_id})
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
        MATCH (o:OrgEinheit {name: $org_unit_name})-[r:VERANTWORTET]->(p:Prozess {prozess_id: $process_id})
        DELETE r
        """,
        {
            "org_unit_name": org_unit_name,
            "process_id": process_id,
        },
    )
    return f"Eigentümer-Zuordnung fuer Prozess '{process_id}' wurde entfernt."


def _revert_role_assignment(config: AppConfig, neo4j_client, payload: dict) -> str:
    role_name = str(payload.get("role_name", ""))
    org_unit_name = str(payload.get("org_unit_name", ""))
    neo4j_client.execute_write(
        """
        MATCH (o:OrgEinheit {name: $org_unit_name})-[r:KANN_EINNEHMEN]->(role:Rolle {name: $role_name})
        DELETE r
        """,
        {
            "org_unit_name": org_unit_name,
            "role_name": role_name,
        },
    )
    return f"Rollenzuordnung '{role_name}' -> '{org_unit_name}' wurde entfernt."


def _refresh_document_if_possible(config: AppConfig, source_path: str) -> None:
    if not source_path:
        return
    try:
        cmdb_rows = load_cmdb_rows(
            resolve_input_cmdb_path(config),
            config.cmdb_uuid_column,
            config.cmdb_name_column,
        )
    except CmdbLoadError:
        return
    persist_single_document_refresh(config, source_path, cmdb_rows)

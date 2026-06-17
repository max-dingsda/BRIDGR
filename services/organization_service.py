from __future__ import annotations

from pathlib import Path

from core.app_config import AppConfig, resolve_input_cmdb_path, resolve_runtime_output_path
from processing.cmdb import CmdbLoadError, load_cmdb_rows
from processing.knowledge_base import (
    KnowledgeBase,
    accept_org_unit_candidate_as_new,
    add_org_unit,
    is_explicit_role,
    load_knowledge_base,
    mark_role_as_explicit,
    map_org_unit_candidate,
    normalize_org_unit_name,
    reject_org_unit_candidate,
    save_knowledge_base,
)
from core.neo4j_utils import Neo4jQueryError
from processing.run_artifacts import load_latest_run, write_latest_run
from services.alias_service import sync_knowledge_base_aliases
from services.review_service import (
    persist_latest_run_refresh,
    reconstruct_extracted_process,
    reconstruct_match_result,
    rerun_single_document_from_artifact,
)
from services.runtime_service import get_session_neo4j_client, write_debug_log
from skills.graph_writer import GraphWriter


def load_org_units_from_neo4j(config: AppConfig) -> list[dict]:
    """Return all OrgEinheit nodes from Neo4j as list of {name} dicts, sorted by name."""
    neo4j_client = get_session_neo4j_client(config)
    rows = neo4j_client.execute_read(
        "MATCH (o:OrgEinheit) WHERE o.name IS NOT NULL RETURN o.name AS name ORDER BY toLower(o.name)",
        {},
    )
    return [{"name": row["name"]} for row in rows]


def persist_org_unit_node(config: AppConfig, org_unit_name: str) -> None:
    cleaned_name = " ".join(org_unit_name.strip().split())
    if not cleaned_name:
        return

    neo4j_client = get_session_neo4j_client(config)
    rows = neo4j_client.execute_write(
        """
        MERGE (o:OrgEinheit {name: $org_unit_name})
        RETURN o.name AS name
        """,
        {"org_unit_name": cleaned_name},
    )
    if not rows or rows[0].get("name") != cleaned_name:
        raise Neo4jQueryError(f"Organisationseinheit `{cleaned_name}` konnte in Neo4j nicht bestaetigt werden.")


def persist_organization_sync(config: AppConfig) -> tuple[int, int]:
    knowledge_base = load_knowledge_base()
    synced_org_units = 0
    synced_names: list[str] = []
    for entry in knowledge_base.org_units:
        org_unit_name = entry.get("name", "")
        if not org_unit_name:
            continue
        persist_org_unit_node(config, org_unit_name)
        synced_org_units += 1
        synced_names.append(org_unit_name)
    sync_knowledge_base_aliases(get_session_neo4j_client(config), knowledge_base)

    try:
        cmdb_rows = load_cmdb_rows(
            resolve_input_cmdb_path(config),
            config.cmdb_uuid_column,
            config.cmdb_name_column,
        )
    except CmdbLoadError:
        write_debug_log(
            config,
            "organization_sync",
            {
                "synced_org_units": synced_org_units,
                "synced_names": synced_names,
                "refreshed_documents": 0,
                "cmdb_refresh": "skipped",
            },
        )
        return synced_org_units, 0

    refreshed_documents = persist_latest_run_refresh(config, cmdb_rows)
    write_debug_log(
        config,
        "organization_sync",
        {
            "synced_org_units": synced_org_units,
            "synced_names": synced_names,
            "refreshed_documents": refreshed_documents,
            "cmdb_refresh": "completed",
        },
    )
    return synced_org_units, refreshed_documents


def persist_org_candidate_mapping_refresh(config: AppConfig, candidate_name: str) -> int:
    knowledge_base = load_knowledge_base()
    candidate_entry = next(
        (
            entry
            for entry in knowledge_base.org_unit_candidates
            if entry.get("candidate_name", "") == candidate_name
            or entry.get("normalized_name", "") == normalize_org_unit_name(candidate_name)
        ),
        None,
    )
    if candidate_entry is None:
        return 0

    mapped_org_unit = candidate_entry.get("mapped_org_unit", "").strip()
    neo4j_client = get_session_neo4j_client(config)
    if mapped_org_unit:
        persist_org_unit_node(config, mapped_org_unit)
        GraphWriter().write_org_unit_alias(neo4j_client, candidate_name, mapped_org_unit)
    sync_knowledge_base_aliases(neo4j_client, knowledge_base)

    runtime_output_path, _ = resolve_runtime_output_path(config.output_path)
    latest_run = load_latest_run(runtime_output_path)
    if latest_run is None:
        return 0

    try:
        cmdb_rows = load_cmdb_rows(
            resolve_input_cmdb_path(config),
            config.cmdb_uuid_column,
            config.cmdb_name_column,
        )
    except CmdbLoadError:
        cmdb_rows = []

    target_source_paths = set(candidate_entry.get("source_paths", []))
    target_process_names = set(candidate_entry.get("process_names", []))
    refreshed_count = 0
    updated_documents: list[dict] = []
    graph_writer = GraphWriter()
    neo4j_client = get_session_neo4j_client(config)
    org_units = graph_writer.load_org_units_from_neo4j(neo4j_client)
    org_unit_aliases = graph_writer.load_org_unit_aliases_from_neo4j(neo4j_client)

    for document in latest_run.get("documents", []):
        extracted_process_payload = document.get("extracted_process") or {}
        source_path = document.get("source_path", "")
        process_name = extracted_process_payload.get("process_name", "")
        if source_path not in target_source_paths and process_name not in target_process_names:
            updated_documents.append(document)
            continue

        refreshed_document = rerun_single_document_from_artifact(
            document, config, cmdb_rows, knowledge_base, org_units=org_units, org_unit_aliases=org_unit_aliases
        )
        updated_documents.append(refreshed_document)
        graph_payload = refreshed_document.get("graph_payload") or {}
        process_payload = graph_payload.get("process") or {}
        matches_payload = graph_payload.get("matches") or []
        process = reconstruct_extracted_process(process_payload)
        matches = [reconstruct_match_result(match_payload) for match_payload in matches_payload]
        graph_writer.write_payload(neo4j_client, graph_writer.build_payload(process, matches))
        refreshed_count += 1

    latest_run["documents"] = updated_documents
    write_latest_run(latest_run, runtime_output_path)
    return refreshed_count


def add_org_unit_entry(config: AppConfig, knowledge_base: KnowledgeBase, org_unit_name: str) -> tuple[str, str]:
    updated_kb = add_org_unit(knowledge_base, org_unit_name, source="manual")
    save_knowledge_base(updated_kb)
    try:
        persist_org_unit_node(config, org_unit_name)
        sync_knowledge_base_aliases(get_session_neo4j_client(config), updated_kb)
    except Exception as exc:
        return "warning", f"Organisationseinheit wurde in BRIDGR gespeichert, konnte aber nicht nach Neo4j synchronisiert werden: {exc}"
    return "success", "Organisationseinheit gespeichert und nach Neo4j synchronisiert."


def ensure_org_unit_registered(config: AppConfig, org_unit_name: str, source: str = "manual") -> str:
    cleaned_name = " ".join(org_unit_name.strip().split())
    if not cleaned_name:
        return cleaned_name

    knowledge_base = load_knowledge_base()
    updated_kb = add_org_unit(knowledge_base, cleaned_name, source=source)
    if updated_kb != knowledge_base:
        save_knowledge_base(updated_kb)
    try:
        persist_org_unit_node(config, cleaned_name)
        sync_knowledge_base_aliases(get_session_neo4j_client(config), updated_kb)
    except Exception:
        return cleaned_name
    return cleaned_name


def map_org_candidate(config: AppConfig, knowledge_base: KnowledgeBase, candidate_name: str, target_name: str) -> tuple[str, str]:
    updated_kb = map_org_unit_candidate(knowledge_base, candidate_name, target_name)
    save_knowledge_base(updated_kb)
    refreshed_count = persist_org_candidate_mapping_refresh(config, candidate_name)
    if refreshed_count:
        return "success", f"Kandidat wurde gemappt und {refreshed_count} betroffene Prozesse im Graph aktualisiert."
    return "success", "Kandidat wurde gemappt."


def accept_org_candidate(config: AppConfig, knowledge_base: KnowledgeBase, candidate_name: str, proposed_name: str) -> tuple[str, str]:
    updated_kb = accept_org_unit_candidate_as_new(knowledge_base, candidate_name, proposed_name)
    save_knowledge_base(updated_kb)
    refreshed_count = persist_org_candidate_mapping_refresh(config, candidate_name)
    if refreshed_count:
        return "success", f"Kandidat wurde als neue Organisationseinheit uebernommen und {refreshed_count} betroffene Prozesse im Graph aktualisiert."
    return "success", "Kandidat wurde als neue Organisationseinheit uebernommen."


def reject_org_candidate(knowledge_base: KnowledgeBase, candidate_name: str) -> tuple[str, str]:
    updated_kb = reject_org_unit_candidate(knowledge_base, candidate_name)
    save_knowledge_base(updated_kb)
    return "success", "Kandidat wurde abgewiesen."


def load_all_processes_with_owner(config: AppConfig) -> list[dict]:
    neo4j_client = get_session_neo4j_client(config)
    rows = neo4j_client.execute_write(
        """
        MATCH (p:Prozess)
        WHERE p.placeholder IS NULL OR p.placeholder = false
        OPTIONAL MATCH (o:OrgEinheit)-[:VERANTWORTET]->(p)
        RETURN p.prozess_id AS prozess_id, p.name AS prozess, o.name AS eigentuemer
        ORDER BY p.name
        """
    )
    return [
        {"prozess_id": row["prozess_id"], "prozess": row["prozess"], "eigentuemer": row["eigentuemer"]}
        for row in rows
    ]


def set_process_owner(config: AppConfig, process_id: str, org_unit_name: str) -> tuple[str, str]:
    cleaned = " ".join(org_unit_name.strip().split())
    if not cleaned:
        return "error", "Organisationseinheit darf nicht leer sein."
    ensure_org_unit_registered(config, cleaned, source="manual")
    neo4j_client = get_session_neo4j_client(config)
    GraphWriter().write_process_owner(neo4j_client, cleaned, process_id)
    return "success", f"Eigentümer gesetzt."


def clear_process_owner(config: AppConfig, process_id: str) -> tuple[str, str]:
    neo4j_client = get_session_neo4j_client(config)
    GraphWriter().remove_process_owner(neo4j_client, process_id)
    return "success", "Eigentümer entfernt."


def load_process_owner_candidates(config: AppConfig) -> list[dict]:
    output_path, _ = resolve_runtime_output_path(config.output_path)
    latest_run = load_latest_run(output_path)
    if not latest_run:
        return []

    neo4j_client = get_session_neo4j_client(config)
    owned_process_ids: set[str] = {
        row["prozess_id"]
        for row in neo4j_client.execute_write(
            "MATCH (:OrgEinheit)-[:VERANTWORTET]->(p:Prozess) RETURN p.prozess_id AS prozess_id"
        )
        if row.get("prozess_id")
    }

    candidates: list[dict] = []
    for document in latest_run.get("documents", []):
        extracted = document.get("extracted_process") or {}
        candidate_name = (extracted.get("process_owner_candidate") or "").strip()
        if not candidate_name:
            continue
        status = document.get("process_owner_candidate_status", "")
        if status in ("accepted", "rejected"):
            continue
        process_id = extracted.get("process_id", "")
        if process_id in owned_process_ids:
            continue
        candidates.append({
            "process_id": process_id,
            "process_name": extracted.get("process_name", ""),
            "candidate_org_unit": candidate_name,
            "source_path": extracted.get("source_path", ""),
        })
    return candidates


def _update_process_owner_candidate_status(config: AppConfig, process_id: str, status: str) -> None:
    output_path, _ = resolve_runtime_output_path(config.output_path)
    latest_run = load_latest_run(output_path)
    if not latest_run:
        return
    for document in latest_run.get("documents", []):
        extracted = document.get("extracted_process") or {}
        if extracted.get("process_id") == process_id:
            document["process_owner_candidate_status"] = status
    write_latest_run(latest_run, output_path)


def accept_process_owner_candidate(config: AppConfig, process_id: str, org_unit_name: str) -> tuple[str, str]:
    ensure_org_unit_registered(config, org_unit_name, source="candidate")
    level, message = set_process_owner(config, process_id, org_unit_name)
    if level == "success":
        _update_process_owner_candidate_status(config, process_id, "accepted")
    return level, message


def reject_process_owner_candidate(config: AppConfig, process_id: str) -> tuple[str, str]:
    _update_process_owner_candidate_status(config, process_id, "rejected")
    return "success", "Vorschlag abgewiesen."


def load_unassigned_roles(config: AppConfig) -> list[dict]:
    neo4j_client = get_session_neo4j_client(config)
    rows = neo4j_client.execute_write(
        """
        MATCH (r:Rolle)-[:BETEILIGT_AN]->(p:Prozess)
        WHERE NOT (:OrgEinheit)-[:KANN_EINNEHMEN]->(r)
          AND NOT EXISTS { MATCH (o:OrgEinheit) WHERE toLower(o.name) = toLower(r.name) }
          AND (r.role_only IS NULL OR r.role_only = false)
        RETURN r.name AS rolle, collect(p.name) AS prozesse
        ORDER BY r.name
        """
    )
    return [
        {"rolle": row["rolle"], "prozesse": row["prozesse"]}
        for row in rows
        if row.get("rolle")
    ]


def assign_role_to_org_unit(config: AppConfig, role_name: str, org_unit_name: str) -> tuple[str, str]:
    cleaned_org_unit = " ".join(org_unit_name.strip().split())
    if not cleaned_org_unit:
        return "error", "Organisationseinheit darf nicht leer sein."
    ensure_org_unit_registered(config, cleaned_org_unit, source="manual")
    neo4j_client = get_session_neo4j_client(config)
    GraphWriter().write_role_assignment(neo4j_client, cleaned_org_unit, role_name)
    return "success", f"Rolle \"{role_name}\" wurde \"{cleaned_org_unit}\" zugeordnet."


def mark_role_as_role_only(config: AppConfig, role_name: str) -> tuple[str, str]:
    knowledge_base = load_knowledge_base()
    updated_kb = mark_role_as_explicit(knowledge_base, role_name)
    save_knowledge_base(updated_kb)
    neo4j_client = get_session_neo4j_client(config)
    GraphWriter().write_role_only_decision(neo4j_client, role_name)
    return "success", f"Rolle \"{role_name}\" wurde als reine Rolle markiert."

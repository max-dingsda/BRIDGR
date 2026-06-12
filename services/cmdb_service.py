from __future__ import annotations

from dataclasses import dataclass

from core.app_config import AppConfig, resolve_input_cmdb_path, resolve_input_cmdb_relations_path
from processing.cmdb import load_cmdb_relation_rows, load_cmdb_rows, load_normalized_cmdb, normalize_cmdb_relations
from processing.knowledge_base import KnowledgeBase, load_knowledge_base, normalize_org_unit_name, save_knowledge_base, upsert_org_unit_candidate
from skills.graph_writer import GraphWriter


@dataclass(slots=True)
class CmdbSyncResult:
    entity_count: int
    relation_count: int
    owner_assignment_count: int
    owner_candidate_count: int
    refreshed_document_count: int


def persist_cmdb_sync(config: AppConfig) -> CmdbSyncResult:
    from services.runtime_service import get_session_neo4j_client, write_debug_log
    from services.review_service import persist_latest_run_refresh

    neo4j_client = get_session_neo4j_client(config)
    knowledge_base = load_knowledge_base()
    result, updated_knowledge_base = sync_cmdb_to_neo4j(config, neo4j_client, knowledge_base)
    save_knowledge_base(updated_knowledge_base)
    refreshed_document_count = persist_latest_run_refresh(
        config,
        load_cmdb_rows(
            resolve_input_cmdb_path(config),
            config.cmdb_uuid_column,
            config.cmdb_name_column,
        ),
    )
    result.refreshed_document_count = refreshed_document_count
    write_debug_log(
        config,
        "cmdb_sync",
        {
            "entity_count": result.entity_count,
            "relation_count": result.relation_count,
            "owner_assignment_count": result.owner_assignment_count,
            "owner_candidate_count": result.owner_candidate_count,
            "refreshed_document_count": result.refreshed_document_count,
            "cmdb_filename": config.cmdb_filename,
            "cmdb_relations_filename": config.cmdb_relations_filename,
        },
    )
    return result


def sync_cmdb_to_neo4j(
    config: AppConfig,
    neo4j_client,
    knowledge_base: KnowledgeBase,
) -> tuple[CmdbSyncResult, KnowledgeBase]:
    normalized_cmdb = load_normalized_cmdb(
        resolve_input_cmdb_path(config),
        id_column=config.cmdb_uuid_column,
        name_column=config.cmdb_name_column,
        entity_type_column=config.cmdb_entity_type_column,
        server_type_column=config.cmdb_server_type_column,
        owner_name_column=config.cmdb_owner_name_column,
    )
    relations_path = resolve_input_cmdb_relations_path(config)
    if relations_path is not None:
        normalized_cmdb.relations = normalize_cmdb_relations(
            load_cmdb_relation_rows(
                relations_path,
                source_id_column=config.cmdb_relation_source_column,
                relation_type_column=config.cmdb_relation_type_column,
                target_id_column=config.cmdb_relation_target_column,
            ),
            source_id_column=config.cmdb_relation_source_column,
            relation_type_column=config.cmdb_relation_type_column,
            target_id_column=config.cmdb_relation_target_column,
        )

    updated_knowledge_base = update_organization_knowledge_from_cmdb(
        knowledge_base,
        normalized_cmdb,
        source_path=str(resolve_input_cmdb_path(config)),
    )
    owner_assignments = resolve_cmdb_owner_assignments(updated_knowledge_base, normalized_cmdb)
    owner_candidates = resolve_cmdb_owner_candidates(updated_knowledge_base, normalized_cmdb)

    graph_writer = GraphWriter()
    graph_writer.sync_cmdb(
        neo4j_client,
        normalized_cmdb,
        owner_assignments=owner_assignments,
    )
    for entity_id, org_unit_name in owner_candidates.items():
        graph_writer.write_candidate_ownership(neo4j_client, org_unit_name, entity_id, score=0.0)

    result = CmdbSyncResult(
        entity_count=len(normalized_cmdb.entities),
        relation_count=len(normalized_cmdb.relations),
        owner_assignment_count=len(owner_assignments),
        owner_candidate_count=len(updated_knowledge_base.org_unit_candidates),
        refreshed_document_count=0,
    )
    return result, updated_knowledge_base


def update_organization_knowledge_from_cmdb(
    knowledge_base: KnowledgeBase,
    normalized_cmdb,
    source_path: str,
) -> KnowledgeBase:
    updated = knowledge_base
    known_org_units = {
        normalize_org_unit_name(entry.get("name", "")): entry.get("name", "")
        for entry in knowledge_base.org_units
        if entry.get("name")
    }
    mapped_candidates = {
        entry.get("normalized_name", ""): entry.get("mapped_org_unit", "")
        for entry in knowledge_base.org_unit_candidates
        if entry.get("status") == "mapped" and entry.get("mapped_org_unit")
    }
    for entity in normalized_cmdb.entities:
        owner_name = " ".join((entity.owner_name or "").split())
        if not owner_name:
            continue
        normalized_owner = normalize_org_unit_name(owner_name)
        if normalized_owner in known_org_units or normalized_owner in mapped_candidates:
            continue
        updated = upsert_org_unit_candidate(
            updated,
            candidate_name=owner_name,
            source_path=source_path,
            process_name="",
            role_name="",
        )
    return updated


def resolve_cmdb_owner_candidates(
    knowledge_base: KnowledgeBase,
    normalized_cmdb,
) -> dict[str, str]:
    known_org_units = {
        normalize_org_unit_name(entry.get("name", "")): entry.get("name", "")
        for entry in knowledge_base.org_units
        if entry.get("name")
    }
    mapped_candidates = {
        entry.get("normalized_name", ""): entry.get("mapped_org_unit", "")
        for entry in knowledge_base.org_unit_candidates
        if entry.get("status") == "mapped" and entry.get("mapped_org_unit")
    }
    candidates: dict[str, str] = {}
    for entity in normalized_cmdb.entities:
        owner_name = " ".join((entity.owner_name or "").split())
        if not owner_name:
            continue
        normalized_owner = normalize_org_unit_name(owner_name)
        if normalized_owner in known_org_units or normalized_owner in mapped_candidates:
            continue
        candidates[entity.entity_id] = owner_name
    return candidates


def resolve_cmdb_owner_assignments(
    knowledge_base: KnowledgeBase,
    normalized_cmdb,
) -> dict[str, str]:
    known_org_units = {
        normalize_org_unit_name(entry.get("name", "")): entry.get("name", "")
        for entry in knowledge_base.org_units
        if entry.get("name")
    }
    mapped_candidates = {
        entry.get("normalized_name", ""): entry.get("mapped_org_unit", "")
        for entry in knowledge_base.org_unit_candidates
        if entry.get("status") == "mapped" and entry.get("mapped_org_unit")
    }
    assignments: dict[str, str] = {}
    for entity in normalized_cmdb.entities:
        owner_name = " ".join((entity.owner_name or "").split())
        if not owner_name:
            continue
        normalized_owner = normalize_org_unit_name(owner_name)
        resolved_owner = known_org_units.get(normalized_owner) or mapped_candidates.get(normalized_owner)
        if resolved_owner:
            assignments[entity.entity_id] = resolved_owner
    return assignments

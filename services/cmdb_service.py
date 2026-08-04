from __future__ import annotations

from dataclasses import dataclass

from core.app_config import AppConfig, resolve_cmdb_type_file_paths
from processing.cmdb import CmdbLoadError, load_cmdb_rows, load_normalized_cmdb_from_type_files
from skills.graph_writer import GraphWriter, normalize_org_unit_name
from services.snapshot_service import create_snapshot


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
    create_snapshot(
        config,
        neo4j_client,
        trigger="cmdb_sync",
        operation="explicit_cmdb_sync",
    )
    result = sync_cmdb_to_neo4j(config, neo4j_client)

    cmdb_rows = load_all_cmdb_rows(config)
    refreshed_document_count = persist_latest_run_refresh(config, cmdb_rows)
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
            "cmdb_type_files": config.cmdb_type_files,
        },
    )
    return result


def load_all_cmdb_rows(config: AppConfig) -> list[dict[str, str]]:
    """Load raw CMDB rows from all configured type files."""
    all_rows: list[dict[str, str]] = []
    for path in resolve_cmdb_type_file_paths(config).values():
        if path.exists():
            try:
                all_rows.extend(load_cmdb_rows(path, config.cmdb_uuid_column, config.cmdb_name_column))
            except CmdbLoadError:
                pass
    return all_rows


def load_application_cmdb_rows(config: AppConfig) -> list[dict[str, str]]:
    """Load raw CMDB rows from the application type file only."""
    type_file_paths = resolve_cmdb_type_file_paths(config)
    app_path = type_file_paths.get("application")
    if app_path is None or not app_path.exists():
        return []
    try:
        return load_cmdb_rows(app_path, config.cmdb_uuid_column, config.cmdb_name_column)
    except CmdbLoadError:
        return []


def sync_cmdb_to_neo4j(
    config: AppConfig,
    neo4j_client,
) -> CmdbSyncResult:
    normalized_cmdb = load_normalized_cmdb_from_type_files(
        resolve_cmdb_type_file_paths(config),
        id_column=config.cmdb_uuid_column,
        name_column=config.cmdb_name_column,
        server_type_column=config.cmdb_server_type_column,
        owner_name_column=config.cmdb_owner_name_column,
        runs_on_column=config.cmdb_runs_on_column,
        uses_interfaces_column=config.cmdb_uses_interfaces_column,
        multivalue_separator=config.cmdb_multivalue_separator,
    )

    graph_writer = GraphWriter()
    org_units = graph_writer.load_org_units_from_neo4j(neo4j_client)
    org_unit_aliases = graph_writer.load_org_unit_aliases_from_neo4j(neo4j_client)

    update_organization_knowledge_from_cmdb(
        graph_writer, neo4j_client, normalized_cmdb,
        source_path="cmdb_sync",
        org_units=org_units, org_unit_aliases=org_unit_aliases,
    )
    owner_assignments = resolve_cmdb_owner_assignments(normalized_cmdb, org_units, org_unit_aliases)

    graph_writer.sync_cmdb(neo4j_client, normalized_cmdb, owner_assignments=owner_assignments)

    open_candidate_count = len(graph_writer.load_org_unit_candidates(neo4j_client, status="open"))
    return CmdbSyncResult(
        entity_count=len(normalized_cmdb.entities),
        relation_count=len(normalized_cmdb.relations),
        owner_assignment_count=len(owner_assignments),
        owner_candidate_count=open_candidate_count,
        refreshed_document_count=0,
    )


def update_organization_knowledge_from_cmdb(
    graph_writer: GraphWriter,
    neo4j_client,
    normalized_cmdb,
    source_path: str,
    org_units: dict[str, str],
    org_unit_aliases: dict[str, str],
) -> None:
    """Record CMDB owner strings that are not yet a known OrgEinheit as :OrgKandidat nodes."""
    for entity in normalized_cmdb.entities:
        owner_name = " ".join((entity.owner_name or "").split())
        if not owner_name:
            continue
        normalized_owner = normalize_org_unit_name(owner_name)
        if normalized_owner in org_units or normalized_owner in org_unit_aliases:
            continue
        graph_writer.upsert_org_unit_candidate(
            neo4j_client,
            candidate_name=owner_name,
            source_path=source_path,
            process_name="",
            role_name="",
        )


def resolve_cmdb_owner_assignments(
    normalized_cmdb,
    org_units: dict[str, str],
    org_unit_aliases: dict[str, str],
) -> dict[str, str]:
    """Return {entity_id: canonical_org_unit_name} for CMDB entities with a known owner."""
    assignments: dict[str, str] = {}
    for entity in normalized_cmdb.entities:
        owner_name = " ".join((entity.owner_name or "").split())
        if not owner_name:
            continue
        normalized_owner = normalize_org_unit_name(owner_name)
        resolved_owner = org_units.get(normalized_owner) or org_unit_aliases.get(normalized_owner)
        if resolved_owner:
            assignments[entity.entity_id] = resolved_owner
    return assignments

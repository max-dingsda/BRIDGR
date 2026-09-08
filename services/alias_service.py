from __future__ import annotations

from datetime import date

from core.constants import ALIAS_SOURCE_KIND_MERGED_ENTITY
from core.neo4j_utils import Neo4jClient

ALIAS_SOURCE_KIND_KNOWLEDGE_BASE = "knowledge_base"


def normalize_alias_name(value: str) -> str:
    return " ".join(value.strip().casefold().split())


def lookup_alias_matches(neo4j_client: Neo4jClient, alias_name: str) -> list[dict[str, str]]:
    normalized_name = normalize_alias_name(alias_name)
    if not normalized_name:
        return []
    branches = []
    for label, identity in (("Application", "target.cmdb_id"), ("Process", "target.process_id"), ("OrgUnit", "target.name")):
        branches.append(
            f"MATCH (alias:Alias {{normalized_name: $normalized_name}})-[:MAY_REFER_TO]->(target:{label}) "
            f"RETURN '{label}' AS entity_type, target.name AS entity_name, "
            f"coalesce({identity}, '') AS entity_id, alias.name AS alias_name"
        )
    rows = neo4j_client.execute_read(
        " UNION ALL ".join(branches) + " ORDER BY entity_type, entity_name, entity_id",
        {"normalized_name": normalized_name},
    )
    return [
        {
            "entity_type": str(row.get("entity_type", "")).strip(),
            "entity_name": str(row.get("entity_name", "")).strip(),
            "entity_id": str(row.get("entity_id", "")).strip(),
            "alias_name": str(row.get("alias_name", "")).strip(),
        }
        for row in rows
        if str(row.get("entity_type", "")).strip() and str(row.get("entity_name", "")).strip()
    ]


def sync_curated_aliases(
    neo4j_client: Neo4jClient,
    confirmed_links: list[dict],
    org_unit_candidates: list[dict],
) -> int:
    """Rebuild the Alias projection derived from confirmed application links and mapped org candidates.

    confirmed_links: from GraphWriter.get_confirmed_links_from_neo4j (Neo4j SERVES edges).
    org_unit_candidates: from GraphWriter.load_org_unit_candidates (Neo4j OrgCandidate nodes).
    """
    neo4j_client.ensure_constraints()
    neo4j_client.execute_write(
        """
        MATCH (:Alias)-[r:MAY_REFER_TO]->()
        WHERE r.source_kind = $source_kind
        DELETE r
        """,
        {"source_kind": ALIAS_SOURCE_KIND_KNOWLEDGE_BASE},
    )
    written_aliases = 0
    written_keys: set[tuple[str, str, str]] = set()

    for entry in confirmed_links:
        alias_name = str(entry.get("anwendung_name", "")).strip()
        resolved_name = str(entry.get("resolved_to", "")).strip()
        cmdb_id = str(entry.get("cmdb_id", "")).strip()
        alias_key = (
            "Application",
            normalize_alias_name(alias_name),
            cmdb_id,
        )
        if alias_key in written_keys:
            continue
        if _should_skip_alias(alias_name, resolved_name) or not cmdb_id:
            continue
        _merge_application_alias(neo4j_client, alias_name, resolved_name, cmdb_id)
        written_keys.add(alias_key)
        written_aliases += 1

    for entry in org_unit_candidates:
        if entry.get("status") != "mapped":
            continue
        alias_name = str(entry.get("candidate_name", "")).strip()
        target_name = str(entry.get("mapped_org_unit", "")).strip()
        alias_key = (
            "OrgUnit",
            normalize_alias_name(alias_name),
            normalize_alias_name(target_name),
        )
        if alias_key in written_keys:
            continue
        if _should_skip_alias(alias_name, target_name):
            continue
        _merge_org_unit_alias(neo4j_client, alias_name, target_name)
        written_keys.add(alias_key)
        written_aliases += 1

    neo4j_client.execute_write(
        """
        MATCH (alias:Alias)
        WHERE NOT (alias)-[:MAY_REFER_TO]->()
        DELETE alias
        """
    )
    return written_aliases


def _should_skip_alias(alias_name: str, target_name: str) -> bool:
    return not alias_name or not target_name or normalize_alias_name(alias_name) == normalize_alias_name(target_name)


def _merge_alias_node(neo4j_client: Neo4jClient, alias_name: str) -> None:
    neo4j_client.execute_write(
        """
        MERGE (alias:Alias {normalized_name: $normalized_name})
        ON CREATE SET alias.name = $alias_name,
                      alias.created_at = $created_at,
                      alias.source_kind = $source_kind
        SET alias.name = coalesce(alias.name, $alias_name)
        """,
        {
            "normalized_name": normalize_alias_name(alias_name),
            "alias_name": alias_name.strip(),
            "created_at": date.today().isoformat(),
            "source_kind": ALIAS_SOURCE_KIND_KNOWLEDGE_BASE,
        },
    )


def _merge_application_alias(
    neo4j_client: Neo4jClient,
    alias_name: str,
    resolved_name: str,
    cmdb_id: str,
) -> None:
    _merge_alias_node(neo4j_client, alias_name)
    neo4j_client.execute_write(
        """
        MERGE (application:Application {cmdb_id: $cmdb_id})
        SET application.id = $cmdb_id,
            application.name = coalesce(application.name, $resolved_name)
        WITH application
        MATCH (alias:Alias {normalized_name: $normalized_name})
        MERGE (alias)-[r:MAY_REFER_TO]->(application)
        SET r.source_kind = $source_kind
        """,
        {
            "cmdb_id": cmdb_id,
            "resolved_name": resolved_name.strip(),
            "normalized_name": normalize_alias_name(alias_name),
            "source_kind": ALIAS_SOURCE_KIND_KNOWLEDGE_BASE,
        },
    )


def _merge_org_unit_alias(
    neo4j_client: Neo4jClient,
    alias_name: str,
    target_name: str,
) -> None:
    _merge_org_unit_alias_with_source_kind(
        neo4j_client,
        alias_name,
        target_name,
        source_kind=ALIAS_SOURCE_KIND_KNOWLEDGE_BASE,
    )


def _merge_org_unit_alias_with_source_kind(
    neo4j_client: Neo4jClient,
    alias_name: str,
    target_name: str,
    *,
    source_kind: str,
) -> None:
    _merge_alias_node(neo4j_client, alias_name)
    neo4j_client.execute_write(
        """
        MERGE (org_unit:OrgUnit {name: $target_name})
        WITH org_unit
        MATCH (alias:Alias {normalized_name: $normalized_name})
        MERGE (alias)-[r:MAY_REFER_TO]->(org_unit)
        SET r.source_kind = $source_kind
        """,
        {
            "target_name": target_name.strip(),
            "normalized_name": normalize_alias_name(alias_name),
            "source_kind": source_kind,
        },
    )


def write_merged_org_unit_alias(
    neo4j_client: Neo4jClient,
    source_name: str,
    target_name: str,
) -> None:
    if _should_skip_alias(source_name, target_name):
        return
    _merge_org_unit_alias_with_source_kind(
        neo4j_client,
        source_name,
        target_name,
        source_kind=ALIAS_SOURCE_KIND_MERGED_ENTITY,
    )


def write_merged_process_alias(
    neo4j_client: Neo4jClient,
    source_name: str,
    *,
    target_element_id: str,
) -> None:
    if not source_name.strip() or not target_element_id.strip():
        return
    _merge_alias_node(neo4j_client, source_name)
    neo4j_client.execute_write(
        """
        MATCH (process:Process)
        WHERE elementId(process) = $target_element_id
        WITH process
        MATCH (alias:Alias {normalized_name: $normalized_name})
        MERGE (alias)-[r:MAY_REFER_TO]->(process)
        SET r.source_kind = $source_kind
        """,
        {
            "target_element_id": target_element_id,
            "normalized_name": normalize_alias_name(source_name),
            "source_kind": ALIAS_SOURCE_KIND_MERGED_ENTITY,
        },
    )


def delete_application_alias(
    neo4j_client: Neo4jClient,
    alias_name: str,
    cmdb_id: str,
    *,
    source_kind: str,
) -> None:
    normalized_name = normalize_alias_name(alias_name)
    if not normalized_name or not cmdb_id:
        return
    neo4j_client.execute_write(
        """
        MATCH (alias:Alias {normalized_name: $normalized_name})-[r:MAY_REFER_TO]->(application:Application {cmdb_id: $cmdb_id})
        WHERE r.source_kind = $source_kind
        DELETE r
        """,
        {
            "normalized_name": normalized_name,
            "cmdb_id": cmdb_id,
            "source_kind": source_kind,
        },
    )
    neo4j_client.execute_write(
        """
        MATCH (alias:Alias {normalized_name: $normalized_name})
        WHERE NOT (alias)-[:MAY_REFER_TO]->()
        DELETE alias
        """,
        {"normalized_name": normalized_name},
    )


def delete_org_unit_alias(
    neo4j_client: Neo4jClient,
    alias_name: str,
    target_name: str,
    *,
    source_kind: str,
) -> None:
    _delete_alias_relation(
        neo4j_client,
        """
        MATCH (alias:Alias {normalized_name: $normalized_name})-[r:MAY_REFER_TO]->(target:OrgUnit {name: $target_name})
        WHERE r.source_kind = $source_kind
        DELETE r
        """,
        {
            "normalized_name": normalize_alias_name(alias_name),
            "target_name": target_name,
            "source_kind": source_kind,
        },
    )


def delete_process_alias(
    neo4j_client: Neo4jClient,
    alias_name: str,
    *,
    target_element_id: str,
    source_kind: str,
) -> None:
    _delete_alias_relation(
        neo4j_client,
        """
        MATCH (alias:Alias {normalized_name: $normalized_name})-[r:MAY_REFER_TO]->(target:Process)
        WHERE elementId(target) = $target_element_id
          AND r.source_kind = $source_kind
        DELETE r
        """,
        {
            "normalized_name": normalize_alias_name(alias_name),
            "target_element_id": target_element_id,
            "source_kind": source_kind,
        },
    )


def _delete_alias_relation(neo4j_client: Neo4jClient, query: str, parameters: dict[str, str]) -> None:
    normalized_name = str(parameters.get("normalized_name", "")).strip()
    if not normalized_name:
        return
    neo4j_client.execute_write(query, parameters)
    neo4j_client.execute_write(
        """
        MATCH (alias:Alias {normalized_name: $normalized_name})
        WHERE NOT (alias)-[:MAY_REFER_TO]->()
        DELETE alias
        """,
        {"normalized_name": normalized_name},
    )

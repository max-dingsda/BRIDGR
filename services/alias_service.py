from __future__ import annotations

from datetime import date

from knowledge_base import KnowledgeBase
from neo4j_utils import Neo4jClient

ALIAS_SOURCE_KIND_KNOWLEDGE_BASE = "knowledge_base"


def normalize_alias_name(value: str) -> str:
    return " ".join(value.strip().casefold().split())


def lookup_alias_matches(neo4j_client: Neo4jClient, alias_name: str) -> list[dict[str, str]]:
    normalized_name = normalize_alias_name(alias_name)
    if not normalized_name:
        return []
    rows = neo4j_client.execute_read_unvalidated(
        """
        MATCH (alias:Alias {normalized_name: $normalized_name})-[:KANN_MEINEN]->(target)
        WITH alias, target,
             CASE
                 WHEN target:Prozess THEN 'Prozess'
                 WHEN target:Anwendung THEN 'Anwendung'
                 WHEN target:Schnittstelle THEN 'Schnittstelle'
                 WHEN target:Server THEN 'Server'
                 WHEN target:OrgEinheit THEN 'OrgEinheit'
                 ELSE ''
             END AS entity_type
        WHERE entity_type <> ''
        RETURN entity_type,
               coalesce(target.name, '') AS entity_name,
               coalesce(target.cmdb_id, target.prozess_id, target.id, '') AS entity_id,
               alias.name AS alias_name
        ORDER BY entity_type, entity_name, entity_id
        """,
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


def sync_knowledge_base_aliases(neo4j_client: Neo4jClient, knowledge_base: KnowledgeBase) -> int:
    neo4j_client.ensure_constraints()
    neo4j_client.execute_write(
        """
        MATCH (:Alias)-[r:KANN_MEINEN]->()
        WHERE r.source_kind = $source_kind
        DELETE r
        """,
        {"source_kind": ALIAS_SOURCE_KIND_KNOWLEDGE_BASE},
    )
    written_aliases = 0
    written_keys: set[tuple[str, str, str]] = set()

    for entry in knowledge_base.confirmed:
        alias_name = str(entry.get("anwendung_name", "")).strip()
        resolved_name = str(entry.get("resolved_to", "")).strip()
        cmdb_id = str(entry.get("cmdb_id", "")).strip()
        alias_key = (
            "Anwendung",
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

    for entry in knowledge_base.org_unit_candidates:
        if entry.get("status") != "mapped":
            continue
        alias_name = str(entry.get("candidate_name", "")).strip()
        target_name = str(entry.get("mapped_org_unit", "")).strip()
        alias_key = (
            "OrgEinheit",
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
        WHERE NOT (alias)-[:KANN_MEINEN]->()
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
        MERGE (application:Anwendung {cmdb_id: $cmdb_id})
        SET application.id = $cmdb_id,
            application.name = coalesce(application.name, $resolved_name)
        WITH application
        MATCH (alias:Alias {normalized_name: $normalized_name})
        MERGE (alias)-[r:KANN_MEINEN]->(application)
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
    _merge_alias_node(neo4j_client, alias_name)
    neo4j_client.execute_write(
        """
        MERGE (org_unit:OrgEinheit {name: $target_name})
        WITH org_unit
        MATCH (alias:Alias {normalized_name: $normalized_name})
        MERGE (alias)-[r:KANN_MEINEN]->(org_unit)
        SET r.source_kind = $source_kind
        """,
        {
            "target_name": target_name.strip(),
            "normalized_name": normalize_alias_name(alias_name),
            "source_kind": ALIAS_SOURCE_KIND_KNOWLEDGE_BASE,
        },
    )

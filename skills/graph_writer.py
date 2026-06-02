from __future__ import annotations

from dataclasses import dataclass

from cmdb import (
    CMDB_ENTITY_TYPE_APPLICATION,
    CMDB_ENTITY_TYPE_INTERFACE,
    CMDB_ENTITY_TYPE_PROCESS,
    CMDB_ENTITY_TYPE_SERVER,
    CmdbEntity,
    CmdbRelation,
    NormalizedCmdb,
)
from constants import CONFIDENCE_STRONG, MATCH_SOURCE_KNOWLEDGE_BASE, MATCH_SOURCE_KNOWLEDGE_BASE_MANUAL
from neo4j_utils import Neo4jClient
from skills.extract.extract_base import ExtractedProcess
from skills.match import MatchResult

PROCESS_WRITE_ACTION_INSERTED = "inserted"
PROCESS_WRITE_ACTION_UPDATED = "updated"


@dataclass(slots=True)
class GraphWritePayload:
    process: ExtractedProcess
    matches: list[MatchResult]


class GraphWriter:
    def build_payload(self, process: ExtractedProcess, matches: list[MatchResult]) -> GraphWritePayload:
        return GraphWritePayload(process=process, matches=matches)

    def write_payload(self, client: Neo4jClient, payload: GraphWritePayload) -> str:
        client.ensure_constraints()
        process = payload.process
        process_write_action = self._upsert_process_node(client, process.process_id, process.process_name)
        client.execute_write(
            """
            MATCH (p:Prozess {prozess_id: $process_id})-[r:NUTZT]->(:Anwendung)
            DELETE r
            """,
            {
                "process_id": process.process_id,
            },
        )
        client.execute_write(
            """
            MATCH (:Anwendung)-[r:DIENT]->(p:Prozess {prozess_id: $process_id})
            DELETE r
            """,
            {
                "process_id": process.process_id,
            },
        )
        client.execute_write(
            """
            MATCH (:Rolle)-[r:BETEILIGT_AN]->(p:Prozess {prozess_id: $process_id})
            DELETE r
            """,
            {
                "process_id": process.process_id,
            },
        )

        for role_name in process.roles:
            client.execute_write(
                """
                MERGE (r:Rolle {name: $role_name})
                MERGE (p:Prozess {prozess_id: $process_id})
                MERGE (r)-[:BETEILIGT_AN]->(p)
                """,
                {
                    "role_name": role_name,
                    "process_id": process.process_id,
                },
            )

        for previous_process_name in process.follows_after:
            client.execute_write(
                """
                MERGE (current:Prozess {prozess_id: $process_id})
                MERGE (previous:Prozess {name: $previous_process_name})
                ON CREATE SET previous.placeholder = true
                SET previous.placeholder = coalesce(previous.placeholder, true)
                MERGE (current)-[:FOLGT_AUF]->(previous)
                """,
                {
                    "process_id": process.process_id,
                    "previous_process_name": previous_process_name,
                },
            )

        for match in payload.matches:
            if not match.cmdb_id:
                continue
            if match.confidence != CONFIDENCE_STRONG and match.source not in {
                MATCH_SOURCE_KNOWLEDGE_BASE,
                MATCH_SOURCE_KNOWLEDGE_BASE_MANUAL,
            }:
                continue
            client.execute_write(
                """
                MERGE (p:Prozess {prozess_id: $process_id})
                MERGE (a:Anwendung {cmdb_id: $cmdb_id})
                SET a.id = $cmdb_id,
                    a.name = $application_name
                MERGE (a)-[r:DIENT]->(p)
                SET r.konfidenz = $confidence
                """,
                {
                    "process_id": process.process_id,
                    "cmdb_id": match.cmdb_id,
                    "application_name": match.matched_name or match.application_name,
                    "confidence": match.confidence,
                },
            )
        return process_write_action

    def sync_cmdb(
        self,
        client: Neo4jClient,
        normalized_cmdb: NormalizedCmdb,
        owner_assignments: dict[str, str] | None = None,
    ) -> None:
        client.ensure_constraints()
        owner_assignments = owner_assignments or {}

        for entity in normalized_cmdb.entities:
            self._upsert_cmdb_entity(client, entity)

        for entity in normalized_cmdb.entities:
            client.execute_write(
                """
                MATCH (source)-[r]->(target)
                WHERE source.id = $entity_id AND type(r) IN ['USES_INTERFACE', 'RUNS_ON']
                DELETE r
                """,
                {"entity_id": entity.entity_id},
            )
            client.execute_write(
                """
                MATCH (:OrgEinheit)-[r:VERANTWORTET]->(target)
                WHERE target.id = $entity_id
                DELETE r
                """,
                {"entity_id": entity.entity_id},
            )

        for relation in normalized_cmdb.relations:
            self._merge_cmdb_relation(client, relation)

        for entity_id, org_unit_name in owner_assignments.items():
            client.execute_write(
                """
                MERGE (o:OrgEinheit {name: $org_unit_name})
                MATCH (target)
                WHERE target.id = $entity_id
                MERGE (o)-[:VERANTWORTET]->(target)
                """,
                {
                    "org_unit_name": org_unit_name,
                    "entity_id": entity_id,
                },
            )

    def write_process_owner(self, client: Neo4jClient, org_unit_name: str, process_id: str) -> None:
        client.execute_write(
            """
            MATCH (:OrgEinheit)-[r:VERANTWORTET]->(p:Prozess {prozess_id: $process_id})
            DELETE r
            """,
            {"process_id": process_id},
        )
        client.execute_write(
            """
            MERGE (o:OrgEinheit {name: $org_unit_name})
            MATCH (p:Prozess {prozess_id: $process_id})
            MERGE (o)-[:VERANTWORTET]->(p)
            """,
            {"org_unit_name": org_unit_name, "process_id": process_id},
        )

    def remove_process_owner(self, client: Neo4jClient, process_id: str) -> None:
        client.execute_write(
            """
            MATCH (:OrgEinheit)-[r:VERANTWORTET]->(p:Prozess {prozess_id: $process_id})
            DELETE r
            """,
            {"process_id": process_id},
        )

    def write_role_assignment(self, client: Neo4jClient, org_unit_name: str, role_name: str) -> None:
        client.execute_write(
            """
            MERGE (o:OrgEinheit {name: $org_unit_name})
            MERGE (r:Rolle {name: $role_name})
            MERGE (o)-[:KANN_EINNEHMEN]->(r)
            """,
            {
                "org_unit_name": org_unit_name,
                "role_name": role_name,
            },
        )

    def cleanup_process_placeholders(self, client: Neo4jClient) -> None:
        client.execute_write(
            """
            MATCH (p:Prozess {placeholder: true})
            DETACH DELETE p
            """
        )

    def _upsert_process_node(self, client: Neo4jClient, process_id: str, process_name: str) -> str:
        placeholder_rows = client.execute_write(
            """
            MATCH (p:Prozess {name: $process_name, placeholder: true})
            RETURN elementId(p) AS element_id
            """,
            {
                "process_name": process_name,
            },
        )
        process_rows = client.execute_write(
            """
            MATCH (p:Prozess {prozess_id: $process_id})
            RETURN elementId(p) AS element_id
            """,
            {
                "process_id": process_id,
            },
        )

        if process_rows:
            client.execute_write(
                """
                MATCH (p:Prozess {prozess_id: $process_id})
                SET p.name = $process_name,
                    p.placeholder = false
                """,
                {
                    "process_id": process_id,
                    "process_name": process_name,
                },
            )
            self._resolve_duplicate_placeholders(client, process_id, process_name)
            return PROCESS_WRITE_ACTION_UPDATED

        if len(placeholder_rows) == 1:
            client.execute_write(
                """
                MATCH (p)
                WHERE elementId(p) = $element_id
                SET p.prozess_id = $process_id,
                    p.name = $process_name,
                    p.placeholder = false
                """,
                {
                    "element_id": placeholder_rows[0]["element_id"],
                    "process_id": process_id,
                    "process_name": process_name,
                },
            )
            return PROCESS_WRITE_ACTION_UPDATED

        client.execute_write(
            """
            MERGE (p:Prozess {prozess_id: $process_id})
            SET p.name = $process_name,
                p.placeholder = false
            """,
            {
                "process_id": process_id,
                "process_name": process_name,
            },
        )
        return PROCESS_WRITE_ACTION_INSERTED

    def _upsert_cmdb_entity(self, client: Neo4jClient, entity: CmdbEntity) -> None:
        if entity.entity_type == CMDB_ENTITY_TYPE_APPLICATION:
            client.execute_write(
                """
                MERGE (a:Anwendung {cmdb_id: $entity_id})
                SET a.id = $entity_id,
                    a.name = $name
                """,
                {
                    "entity_id": entity.entity_id,
                    "name": entity.name,
                },
            )
            return
        if entity.entity_type == CMDB_ENTITY_TYPE_INTERFACE:
            client.execute_write(
                """
                MERGE (i:Schnittstelle {id: $entity_id})
                SET i.name = $name
                """,
                {
                    "entity_id": entity.entity_id,
                    "name": entity.name,
                },
            )
            return
        if entity.entity_type == CMDB_ENTITY_TYPE_SERVER:
            client.execute_write(
                """
                MERGE (s:Server {id: $entity_id})
                SET s.name = $name,
                    s.server_type = $server_type
                """,
                {
                    "entity_id": entity.entity_id,
                    "name": entity.name,
                    "server_type": entity.server_type,
                },
            )
            return
        if entity.entity_type == CMDB_ENTITY_TYPE_PROCESS:
            client.execute_write(
                """
                MERGE (p:Prozess {prozess_id: $entity_id})
                SET p.name = $name,
                    p.placeholder = false
                """,
                {
                    "entity_id": entity.entity_id,
                    "name": entity.name,
                },
            )

    def _merge_cmdb_relation(self, client: Neo4jClient, relation: CmdbRelation) -> None:
        if relation.relation_type == "USES_INTERFACE":
            client.execute_write(
                """
                MATCH (source), (target)
                WHERE source.id = $source_id AND target.id = $target_id
                MERGE (source)-[:USES_INTERFACE]->(target)
                """,
                {
                    "source_id": relation.source_id,
                    "target_id": relation.target_id,
                },
            )
            return
        if relation.relation_type == "RUNS_ON":
            client.execute_write(
                """
                MATCH (source), (target)
                WHERE source.id = $source_id AND target.id = $target_id
                MERGE (source)-[:RUNS_ON]->(target)
                """,
                {
                    "source_id": relation.source_id,
                    "target_id": relation.target_id,
                },
            )
            return

    def merge_archimate_node(
        self,
        client: Neo4jClient,
        label: str,
        name: str,
        archimate_id: str,
        archimate_source: str,
        archimate_type: str,
    ) -> None:
        client.execute_write(
            f"""
            MERGE (n:{label} {{name: $name}})
            SET n.archimate_id = $archimate_id,
                n.archimate_source = $archimate_source,
                n.archimate_type = $archimate_type
            """,
            {
                "name": name,
                "archimate_id": archimate_id,
                "archimate_source": archimate_source,
                "archimate_type": archimate_type,
            },
        )

    def merge_archimate_relation(
        self,
        client: Neo4jClient,
        source_name: str,
        source_label: str,
        target_name: str,
        target_label: str,
        bridgr_relation: str,
        archimate_rel_type: str,
    ) -> None:
        client.execute_write(
            f"""
            MATCH (s:{source_label} {{name: $source_name}})
            MATCH (t:{target_label} {{name: $target_name}})
            MERGE (s)-[r:{bridgr_relation}]->(t)
            SET r.archimate_rel_type = $archimate_rel_type
            """,
            {
                "source_name": source_name,
                "target_name": target_name,
                "archimate_rel_type": archimate_rel_type,
            },
        )

    def _resolve_duplicate_placeholders(self, client: Neo4jClient, process_id: str, process_name: str) -> None:
        client.execute_write(
            """
            MATCH (real:Prozess {prozess_id: $process_id})
            MATCH (placeholder:Prozess {name: $process_name, placeholder: true})
            WHERE elementId(real) <> elementId(placeholder)
            OPTIONAL MATCH (source:Prozess)-[:FOLGT_AUF]->(placeholder)
            WITH real, placeholder, collect(DISTINCT source) AS sources
            FOREACH (src IN sources |
                MERGE (src)-[:FOLGT_AUF]->(real)
            )
            """,
            {
                "process_id": process_id,
                "process_name": process_name,
            },
        )
        client.execute_write(
            """
            MATCH (real:Prozess {prozess_id: $process_id})
            MATCH (placeholder:Prozess {name: $process_name, placeholder: true})
            WHERE elementId(real) <> elementId(placeholder)
            OPTIONAL MATCH (placeholder)-[:FOLGT_AUF]->(target:Prozess)
            WITH real, placeholder, collect(DISTINCT target) AS targets
            FOREACH (dst IN targets |
                MERGE (real)-[:FOLGT_AUF]->(dst)
            )
            DETACH DELETE placeholder
            """,
            {
                "process_id": process_id,
                "process_name": process_name,
            },
        )

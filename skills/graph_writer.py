from __future__ import annotations

from dataclasses import dataclass

from constants import CONFIDENCE_STRONG, MATCH_SOURCE_KNOWLEDGE_BASE, MATCH_SOURCE_KNOWLEDGE_BASE_MANUAL
from neo4j_utils import Neo4jClient
from skills.extract.extract_base import ExtractedProcess
from skills.match import MatchResult


@dataclass(slots=True)
class GraphWritePayload:
    process: ExtractedProcess
    matches: list[MatchResult]


class GraphWriter:
    def build_payload(self, process: ExtractedProcess, matches: list[MatchResult]) -> GraphWritePayload:
        return GraphWritePayload(process=process, matches=matches)

    def write_payload(self, client: Neo4jClient, payload: GraphWritePayload) -> None:
        client.ensure_constraints()
        process = payload.process
        client.execute_write(
            """
            MERGE (p:Prozess {prozess_id: $process_id})
            SET p.name = $process_name
            """,
            {
                "process_id": process.process_id,
                "process_name": process.process_name,
            },
        )
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
            MATCH (:OrgEinheit)-[r:VERANTWORTET]->(p:Prozess {prozess_id: $process_id})
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

        for org_unit_name in process.org_units:
            client.execute_write(
                """
                MERGE (o:OrgEinheit {name: $org_unit})
                MERGE (p:Prozess {prozess_id: $process_id})
                MERGE (o)-[:VERANTWORTET]->(p)
                """,
                {
                    "org_unit": org_unit_name,
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
                SET a.name = $application_name
                MERGE (p)-[r:NUTZT]->(a)
                SET r.konfidenz = $confidence
                """,
                {
                    "process_id": process.process_id,
                    "cmdb_id": match.cmdb_id,
                    "application_name": match.matched_name or match.application_name,
                    "confidence": match.confidence,
                },
            )

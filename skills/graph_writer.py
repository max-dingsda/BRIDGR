from __future__ import annotations

from dataclasses import dataclass

from processing.cmdb import (
    CMDB_ENTITY_TYPE_APPLICATION,
    CMDB_ENTITY_TYPE_INTERFACE,
    CMDB_ENTITY_TYPE_PROCESS,
    CMDB_ENTITY_TYPE_SERVER,
    CmdbEntity,
    CmdbRelation,
    NormalizedCmdb,
)
from core.constants import (
    ALIAS_SOURCE_KIND_CONFIRMED_CANDIDATE,
    ALIAS_SOURCE_KIND_CONFIRMED_MATCH,
    CONFIDENCE_STRONG,
    DIENT_SOURCE_CONFIRMED,
    DIENT_SOURCE_MANUAL,
    DIENT_SOURCE_STRONG,
    MATCH_SOURCE_KNOWLEDGE_BASE,
    MATCH_SOURCE_KNOWLEDGE_BASE_MANUAL,
)
from core.neo4j_utils import Neo4jClient
from skills.extract.extract_base import ExtractedProcess
from skills.match import MatchResult

PROCESS_WRITE_ACTION_INSERTED = "inserted"
PROCESS_WRITE_ACTION_UPDATED = "updated"


def _normalize_for_alias(name: str) -> str:
    return " ".join(name.strip().casefold().split())


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
            MATCH (:Anwendung)-[r:KÖNNTE_DIENEN]->(p:Prozess {prozess_id: $process_id})
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
            is_kb_source = match.source in {MATCH_SOURCE_KNOWLEDGE_BASE, MATCH_SOURCE_KNOWLEDGE_BASE_MANUAL}
            if match.confidence == CONFIDENCE_STRONG or is_kb_source:
                dient_source = (
                    DIENT_SOURCE_MANUAL if match.source == MATCH_SOURCE_KNOWLEDGE_BASE_MANUAL
                    else DIENT_SOURCE_CONFIRMED if is_kb_source
                    else DIENT_SOURCE_STRONG
                )
                client.execute_write(
                    """
                    MERGE (p:Prozess {prozess_id: $process_id})
                    MERGE (a:Anwendung {cmdb_id: $cmdb_id})
                    SET a.id = $cmdb_id,
                        a.name = $application_name
                    MERGE (a)-[r:DIENT]->(p)
                    SET r.konfidenz = $confidence,
                        r.raw_name = $raw_name,
                        r.source = $source
                    """,
                    {
                        "process_id": process.process_id,
                        "cmdb_id": match.cmdb_id,
                        "application_name": match.matched_name or match.application_name,
                        "confidence": match.confidence,
                        "raw_name": match.application_name,
                        "source": dient_source,
                    },
                )
            else:
                client.execute_write(
                    """
                    MERGE (p:Prozess {prozess_id: $process_id})
                    MATCH (a:Anwendung {cmdb_id: $cmdb_id})
                    MERGE (a)-[r:KÖNNTE_DIENEN]->(p)
                    SET r.score = $score
                    """,
                    {
                        "process_id": process.process_id,
                        "cmdb_id": match.cmdb_id,
                        "score": match.score,
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
            canonical = self._resolve_org_unit_canonical_name(client, org_unit_name)
            client.execute_write(
                """
                MATCH (o:OrgEinheit {name: $org_unit_name})-[r:KÖNNTE_VERANTWORTEN]->(target)
                WHERE target.id = $entity_id
                DELETE r
                """,
                {"org_unit_name": canonical, "entity_id": entity_id},
            )
            client.execute_write(
                """
                MERGE (o:OrgEinheit {name: $org_unit_name})
                MATCH (target)
                WHERE target.id = $entity_id
                MERGE (o)-[:VERANTWORTET]->(target)
                """,
                {
                    "org_unit_name": canonical,
                    "entity_id": entity_id,
                },
            )

    def write_process_owner(self, client: Neo4jClient, org_unit_name: str, process_id: str) -> None:
        canonical = self._resolve_org_unit_canonical_name(client, org_unit_name)
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
            {"org_unit_name": canonical, "process_id": process_id},
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
        canonical = self._resolve_org_unit_canonical_name(client, org_unit_name)
        client.execute_write(
            """
            MERGE (o:OrgEinheit {name: $org_unit_name})
            MERGE (r:Rolle {name: $role_name})
            MERGE (o)-[:KANN_EINNEHMEN]->(r)
            """,
            {
                "org_unit_name": canonical,
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
        canonical_name = self._resolve_org_unit_canonical_name(client, name) if label == "OrgEinheit" else name
        client.execute_write(
            f"""
            MERGE (n:{label} {{name: $name}})
            SET n.archimate_id = $archimate_id,
                n.archimate_source = $archimate_source,
                n.archimate_type = $archimate_type
            """,
            {
                "name": canonical_name,
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

    def promote_candidate_link(
        self,
        client: Neo4jClient,
        cmdb_id: str,
        process_id: str,
        raw_name: str,
        matched_name: str,
    ) -> None:
        client.execute_write(
            """
            MATCH (a:Anwendung {cmdb_id: $cmdb_id})-[r:KÖNNTE_DIENEN]->(p:Prozess {prozess_id: $process_id})
            DELETE r
            """,
            {"cmdb_id": cmdb_id, "process_id": process_id},
        )
        client.execute_write(
            """
            MERGE (p:Prozess {prozess_id: $process_id})
            MERGE (a:Anwendung {cmdb_id: $cmdb_id})
            SET a.name = $matched_name
            MERGE (a)-[r:DIENT]->(p)
            SET r.konfidenz = 'stark',
                r.raw_name = $raw_name,
                r.source = $source
            """,
            {
                "process_id": process_id,
                "cmdb_id": cmdb_id,
                "matched_name": matched_name,
                "raw_name": raw_name,
                "source": DIENT_SOURCE_CONFIRMED,
            },
        )
        normalized_raw = _normalize_for_alias(raw_name)
        normalized_matched = _normalize_for_alias(matched_name)
        if normalized_raw and normalized_raw != normalized_matched:
            client.execute_write(
                """
                MERGE (alias:Alias {normalized_name: $normalized_name})
                ON CREATE SET alias.name = $alias_name,
                              alias.source_kind = $source_kind
                SET alias.name = coalesce(alias.name, $alias_name)
                WITH alias
                MATCH (a:Anwendung {cmdb_id: $cmdb_id})
                MERGE (alias)-[r:KANN_MEINEN]->(a)
                SET r.source_kind = $source_kind
                """,
                {
                    "normalized_name": normalized_raw,
                    "alias_name": raw_name.strip(),
                    "cmdb_id": cmdb_id,
                    "source_kind": ALIAS_SOURCE_KIND_CONFIRMED_MATCH,
                },
            )

    def reject_candidate_link(
        self,
        client: Neo4jClient,
        cmdb_id: str | None,
        process_id: str,
        prozess_name: str,
        anwendung_name: str,
    ) -> None:
        if cmdb_id:
            client.execute_write(
                """
                MATCH (a:Anwendung {cmdb_id: $cmdb_id})-[r:KÖNNTE_DIENEN]->(p:Prozess {prozess_id: $process_id})
                DELETE r
                """,
                {"cmdb_id": cmdb_id, "process_id": process_id},
            )
        client.execute_write(
            """
            MERGE (ab:Ablehnung {prozess_name: $prozess_name, anwendung_name: $anwendung_name})
            """,
            {"prozess_name": prozess_name, "anwendung_name": anwendung_name},
        )

    def promote_candidate_ownership(
        self,
        client: Neo4jClient,
        org_unit_name: str,
        entity_id: str,
    ) -> None:
        canonical = self._resolve_org_unit_canonical_name(client, org_unit_name)
        client.execute_write(
            """
            MATCH (o:OrgEinheit {name: $org_unit_name})-[r:KÖNNTE_VERANTWORTEN]->(target)
            WHERE target.id = $entity_id OR target.cmdb_id = $entity_id
            DELETE r
            """,
            {"org_unit_name": canonical, "entity_id": entity_id},
        )
        client.execute_write(
            """
            MERGE (o:OrgEinheit {name: $org_unit_name})
            MATCH (target)
            WHERE target.id = $entity_id OR target.cmdb_id = $entity_id
            MERGE (o)-[:VERANTWORTET]->(target)
            """,
            {"org_unit_name": canonical, "entity_id": entity_id},
        )

    def reject_candidate_ownership(
        self,
        client: Neo4jClient,
        org_unit_name: str,
        entity_id: str,
    ) -> None:
        client.execute_write(
            """
            MATCH (o:OrgEinheit {name: $org_unit_name})-[r:KÖNNTE_VERANTWORTEN]->(target)
            WHERE target.id = $entity_id OR target.cmdb_id = $entity_id
            DELETE r
            """,
            {"org_unit_name": org_unit_name, "entity_id": entity_id},
        )

    def write_candidate_ownership(
        self,
        client: Neo4jClient,
        org_unit_name: str,
        entity_id: str,
        score: float,
    ) -> None:
        canonical = self._resolve_org_unit_canonical_name(client, org_unit_name)
        client.execute_write(
            """
            MERGE (o:OrgEinheit {name: $org_unit_name})
            MATCH (target)
            WHERE target.id = $entity_id OR target.cmdb_id = $entity_id
            MERGE (o)-[r:KÖNNTE_VERANTWORTEN]->(target)
            SET r.score = $score
            """,
            {"org_unit_name": canonical, "entity_id": entity_id, "score": score},
        )

    def get_confirmed_links_from_neo4j(self, client: Neo4jClient) -> list[dict]:
        rows = client.execute_read(
            """
            MATCH (a:Anwendung)-[r:DIENT]->(p:Prozess)
            WHERE r.raw_name IS NOT NULL
              AND r.source IN ['manuell_bestaetigt', 'manueller_link']
            RETURN p.name AS prozess,
                   r.raw_name AS anwendung_name,
                   a.cmdb_id AS cmdb_id,
                   a.name AS resolved_to,
                   r.source AS quelle
            """
        )
        return [dict(row) for row in rows]

    def get_rejected_decisions_from_neo4j(self, client: Neo4jClient) -> list[dict]:
        rows = client.execute_read_unvalidated(
            """
            MATCH (ab:Ablehnung)
            RETURN ab.prozess_name AS prozess,
                   ab.anwendung_name AS anwendung_name
            """
        )
        return [{"prozess": row["prozess"], "anwendung_name": row["anwendung_name"], "cmdb_id": None} for row in rows]

    def load_org_units_from_neo4j(self, client: Neo4jClient) -> dict[str, str]:
        """Return {normalized_name: canonical_name} for all OrgEinheit nodes."""
        rows = client.execute_read(
            "MATCH (o:OrgEinheit) WHERE o.name IS NOT NULL RETURN o.name AS name",
            {},
        )
        result: dict[str, str] = {}
        for row in rows:
            name = (row.get("name") or "").strip()
            if name:
                result[_normalize_for_alias(name)] = name
        return result

    def load_org_unit_aliases_from_neo4j(self, client: Neo4jClient) -> dict[str, str]:
        """Return {normalized_alias: canonical_org_unit_name} from Alias→OrgEinheit edges."""
        rows = client.execute_read(
            """
            MATCH (alias:Alias)-[:KANN_MEINEN]->(o:OrgEinheit)
            WHERE alias.normalized_name IS NOT NULL AND o.name IS NOT NULL
            RETURN alias.normalized_name AS alias_normalized, o.name AS org_unit_name
            """,
            {},
        )
        result: dict[str, str] = {}
        for row in rows:
            key = (row.get("alias_normalized") or "").strip()
            val = (row.get("org_unit_name") or "").strip()
            if key and val:
                result[key] = val
        return result

    def write_role_only_decision(self, client: Neo4jClient, role_name: str) -> None:
        """Mark a Rolle node as role-only (not an OrgEinheit) directly in Neo4j."""
        client.execute_write(
            "MATCH (r:Rolle {name: $role_name}) SET r.role_only = true",
            {"role_name": role_name},
        )

    def write_org_unit_alias(self, client: Neo4jClient, candidate_name: str, org_unit_name: str) -> None:
        """Project a confirmed org-unit candidate mapping as an Alias node in Neo4j.

        Creates (:Alias)-[:KANN_MEINEN]->(:OrgEinheit) so the pipeline can resolve
        the raw candidate string to the canonical OrgEinheit without reading kb.json.
        No-op when candidate_name and org_unit_name normalise to the same value.
        """
        normalized_candidate = _normalize_for_alias(candidate_name)
        normalized_target = _normalize_for_alias(org_unit_name)
        if not normalized_candidate or normalized_candidate == normalized_target:
            return
        client.execute_write(
            """
            MERGE (alias:Alias {normalized_name: $normalized_name})
            ON CREATE SET alias.name = $alias_name,
                          alias.source_kind = $source_kind
            SET alias.name = coalesce(alias.name, $alias_name)
            WITH alias
            MERGE (o:OrgEinheit {name: $org_unit_name})
            MERGE (alias)-[r:KANN_MEINEN]->(o)
            SET r.source_kind = $source_kind
            """,
            {
                "normalized_name": normalized_candidate,
                "alias_name": candidate_name.strip(),
                "org_unit_name": org_unit_name.strip(),
                "source_kind": ALIAS_SOURCE_KIND_CONFIRMED_CANDIDATE,
            },
        )

    def _resolve_org_unit_canonical_name(self, client: Neo4jClient, name: str) -> str:
        """Return canonical OrgEinheit name via case-insensitive lookup; fall back to stripped input.

        First-seen wins: if an OrgEinheit with the same name (different case) already exists,
        its stored name is used for the MERGE to avoid creating a duplicate node.
        """
        stripped = name.strip()
        rows = client.execute_read(
            "MATCH (o:OrgEinheit) WHERE toLower(o.name) = toLower($name) RETURN o.name AS name LIMIT 1",
            {"name": stripped},
        )
        return rows[0]["name"] if rows else stripped

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

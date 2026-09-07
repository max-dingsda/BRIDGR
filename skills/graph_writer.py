from __future__ import annotations

from dataclasses import dataclass
from datetime import date

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
    SERVES_SOURCE_CONFIRMED,
    SERVES_SOURCE_MANUAL,
    SERVES_SOURCE_STRONG,
    MATCH_SOURCE_KNOWLEDGE_BASE,
    MATCH_SOURCE_KNOWLEDGE_BASE_MANUAL,
)
from core.neo4j_utils import Neo4jClient
from skills.extract.extract_base import ExtractedProcess
from skills.match import MatchResult

PROCESS_WRITE_ACTION_INSERTED = "inserted"
PROCESS_WRITE_ACTION_UPDATED = "updated"


def _validate_decision_row(row: dict, *, confirmed: bool) -> None:
    required = ("process_id", "anwendung_name", "cmdb_id", "quelle") if confirmed else ("process_id", "anwendung_name")
    if any(not isinstance(row.get(key), str) or not row[key].strip() for key in required):
        raise ValueError("Persisted decision has missing or invalid required fields; manual clarification required.")


def normalize_org_unit_name(name: str) -> str:
    return " ".join(name.strip().casefold().split())


@dataclass(slots=True)
class GraphWritePayload:
    process: ExtractedProcess
    matches: list[MatchResult]


class GraphWriter:
    def build_payload(self, process: ExtractedProcess, matches: list[MatchResult]) -> GraphWritePayload:
        return GraphWritePayload(process=process, matches=matches)

    def write_payload(self, client: Neo4jClient, payload: GraphWritePayload) -> str:
        with client.transaction():
            client.ensure_constraints()
            process = payload.process
            process_write_action = self._upsert_process_node(client, process.process_id, process.process_name)
            client.execute_write(
                """
                MATCH (p:Process {process_id: $process_id})-[r:NUTZT]->(:Application)
                DELETE r
                """,
                {
                    "process_id": process.process_id,
                },
            )
            client.execute_write(
                """
                MATCH (:Application)-[r:SERVES]->(p:Process {process_id: $process_id})
                WHERE NOT coalesce(r.source, '') IN ['manuell_bestaetigt', 'manueller_link']
                DELETE r
                """,
                {
                    "process_id": process.process_id,
                },
            )
            client.execute_write(
                """
                MATCH (:Application)-[r:MAY_SERVE]->(p:Process {process_id: $process_id})
                DELETE r
                """,
                {
                    "process_id": process.process_id,
                },
            )
            client.execute_write(
                """
                MATCH (:Role)-[r:PARTICIPATES_IN]->(p:Process {process_id: $process_id})
                DELETE r
                """,
                {
                    "process_id": process.process_id,
                },
            )

            for role_name in process.roles:
                client.execute_write(
                    """
                    MERGE (r:Role {name: $role_name})
                    MERGE (p:Process {process_id: $process_id})
                    MERGE (r)-[:PARTICIPATES_IN]->(p)
                    """,
                    {
                        "role_name": role_name,
                        "process_id": process.process_id,
                    },
                )

            for previous_process_name in process.follows_after:
                client.execute_write(
                    """
                    MERGE (current:Process {process_id: $process_id})
                    MERGE (previous:Process {name: $previous_process_name})
                    ON CREATE SET previous.placeholder = true
                    SET previous.placeholder = coalesce(previous.placeholder, true)
                    MERGE (current)-[:FOLLOWS]->(previous)
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
                        SERVES_SOURCE_MANUAL if match.source == MATCH_SOURCE_KNOWLEDGE_BASE_MANUAL
                        else SERVES_SOURCE_CONFIRMED if is_kb_source
                        else SERVES_SOURCE_STRONG
                    )
                    client.execute_write(
                        """
                        MERGE (p:Process {process_id: $process_id})
                        MERGE (a:Application {cmdb_id: $cmdb_id})
                        SET a.id = $cmdb_id,
                            a.name = $application_name
                        MERGE (a)-[r:SERVES]->(p)
                        WITH r
                        WHERE NOT coalesce(r.source, '') IN ['manuell_bestaetigt', 'manueller_link']
                        SET r.confidence = $confidence,
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
                        MERGE (p:Process {process_id: $process_id})
                        MATCH (a:Application {cmdb_id: $cmdb_id})
                        MERGE (a)-[r:MAY_SERVE]->(p)
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
        with client.transaction():
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
                    MATCH (:OrgUnit)-[r:RESPONSIBLE_FOR]->(target)
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
                    MATCH (o:OrgUnit {name: $org_unit_name})-[r:MAY_BE_RESPONSIBLE_FOR]->(target)
                    WHERE target.id = $entity_id
                    DELETE r
                    """,
                    {"org_unit_name": canonical, "entity_id": entity_id},
                )
                client.execute_write(
                    """
                    MERGE (o:OrgUnit {name: $org_unit_name})
                    MATCH (target)
                    WHERE target.id = $entity_id
                    MERGE (o)-[:RESPONSIBLE_FOR]->(target)
                    """,
                    {
                        "org_unit_name": canonical,
                        "entity_id": entity_id,
                    },
                )

    def write_process_owner(self, client: Neo4jClient, org_unit_name: str, process_id: str) -> None:
        with client.transaction():
            canonical = self._resolve_org_unit_canonical_name(client, org_unit_name)
            client.execute_write(
                """
                MATCH (:OrgUnit)-[r:RESPONSIBLE_FOR]->(p:Process {process_id: $process_id})
                DELETE r
                """,
                {"process_id": process_id},
            )
            client.execute_write(
                """
                MERGE (o:OrgUnit {name: $org_unit_name})
                MATCH (p:Process {process_id: $process_id})
                MERGE (o)-[:RESPONSIBLE_FOR]->(p)
                """,
                {"org_unit_name": canonical, "process_id": process_id},
            )

    def remove_process_owner(self, client: Neo4jClient, process_id: str) -> None:
        with client.transaction():
            client.execute_write(
                """
                MATCH (:OrgUnit)-[r:RESPONSIBLE_FOR]->(p:Process {process_id: $process_id})
                DELETE r
                """,
                {"process_id": process_id},
            )

    def write_role_assignment(self, client: Neo4jClient, org_unit_name: str, role_name: str) -> None:
        with client.transaction():
            canonical = self._resolve_org_unit_canonical_name(client, org_unit_name)
            client.execute_write(
                """
                MERGE (o:OrgUnit {name: $org_unit_name})
                MERGE (r:Role {name: $role_name})
                MERGE (o)-[:CAN_ASSUME]->(r)
                """,
                {
                    "org_unit_name": canonical,
                    "role_name": role_name,
                },
            )

    def cleanup_process_placeholders(self, client: Neo4jClient) -> None:
        client.execute_write(
            """
            MATCH (p:Process {placeholder: true})
            DETACH DELETE p
            """
        )

    def _upsert_process_node(self, client: Neo4jClient, process_id: str, process_name: str) -> str:
        placeholder_rows = client.execute_write(
            """
            MATCH (p:Process {name: $process_name, placeholder: true})
            RETURN elementId(p) AS element_id
            """,
            {
                "process_name": process_name,
            },
        )
        process_rows = client.execute_write(
            """
            MATCH (p:Process {process_id: $process_id})
            RETURN elementId(p) AS element_id
            """,
            {
                "process_id": process_id,
            },
        )

        if process_rows:
            # Bind unambiguous historical rejections before the display name changes.
            client.execute_write(
                """
                MATCH (p:Process {process_id: $process_id})
                MATCH (same:Process {name: p.name})
                WITH p, count(same) AS count
                WHERE count = 1
                MATCH (ab:Rejection {prozess_name: p.name})
                WHERE ab.process_id IS NULL
                SET ab.process_id = p.process_id
                """,
                {"process_id": process_id},
            )
            client.execute_write(
                """
                MATCH (p:Process {process_id: $process_id})
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
                SET p.process_id = $process_id,
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

        # Check for a node created by another source (e.g. ArchiMate) with the same
        # name but no process_id yet. Enrich it instead of creating a duplicate.
        name_rows = client.execute_write(
            """
            MATCH (p:Process)
            WHERE toLower(p.name) = toLower($process_name)
              AND p.process_id IS NULL
              AND coalesce(p.placeholder, false) = false
            RETURN elementId(p) AS element_id
            LIMIT 1
            """,
            {"process_name": process_name},
        )
        if name_rows:
            client.execute_write(
                """
                MATCH (p)
                WHERE elementId(p) = $element_id
                SET p.process_id = $process_id,
                    p.name = $process_name,
                    p.placeholder = false
                """,
                {
                    "element_id": name_rows[0]["element_id"],
                    "process_id": process_id,
                    "process_name": process_name,
                },
            )
            return PROCESS_WRITE_ACTION_UPDATED

        client.execute_write(
            """
            MERGE (p:Process {process_id: $process_id})
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
            # Check for a node created by another source (e.g. ArchiMate) with the
            # same name but no cmdb_id yet. Enrich it instead of creating a duplicate.
            existing = client.execute_write(
                """
                MATCH (a:Application)
                WHERE toLower(a.name) = toLower($name) AND a.cmdb_id IS NULL
                RETURN elementId(a) AS element_id
                LIMIT 1
                """,
                {"name": entity.name},
            )
            if existing:
                client.execute_write(
                    """
                    MATCH (a) WHERE elementId(a) = $element_id
                    SET a.cmdb_id = $entity_id, a.id = $entity_id, a.name = $name
                    """,
                    {"element_id": existing[0]["element_id"], "entity_id": entity.entity_id, "name": entity.name},
                )
            else:
                client.execute_write(
                    """
                    MERGE (a:Application {cmdb_id: $entity_id})
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
                MERGE (i:Interface {id: $entity_id})
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
                MERGE (p:Process {process_id: $entity_id})
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
        canonical_name = self._resolve_org_unit_canonical_name(client, name) if label == "OrgUnit" else name
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
        with client.transaction():
            client.execute_write(
                """
                MATCH (a:Application {cmdb_id: $cmdb_id})-[r:MAY_SERVE]->(p:Process {process_id: $process_id})
                DELETE r
                """,
                {"cmdb_id": cmdb_id, "process_id": process_id},
            )
            client.execute_write(
                """
                MERGE (p:Process {process_id: $process_id})
                MERGE (a:Application {cmdb_id: $cmdb_id})
                SET a.name = $matched_name
                MERGE (a)-[r:SERVES]->(p)
                SET r.confidence = 'stark',
                    r.raw_name = $raw_name,
                    r.source = $source
                """,
                {
                    "process_id": process_id,
                    "cmdb_id": cmdb_id,
                    "matched_name": matched_name,
                    "raw_name": raw_name,
                    "source": SERVES_SOURCE_CONFIRMED,
                },
            )
            normalized_raw = normalize_org_unit_name(raw_name)
            normalized_matched = normalize_org_unit_name(matched_name)
            if normalized_raw and normalized_raw != normalized_matched:
                client.execute_write(
                    """
                    MERGE (alias:Alias {normalized_name: $normalized_name})
                    ON CREATE SET alias.name = $alias_name,
                                  alias.source_kind = $source_kind
                    SET alias.name = coalesce(alias.name, $alias_name)
                    WITH alias
                    MATCH (a:Application {cmdb_id: $cmdb_id})
                    MERGE (alias)-[r:MAY_REFER_TO]->(a)
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
        with client.transaction():
            if cmdb_id:
                client.execute_write(
                    """
                    MATCH (a:Application {cmdb_id: $cmdb_id})-[r:MAY_SERVE]->(p:Process {process_id: $process_id})
                    DELETE r
                    """,
                    {"cmdb_id": cmdb_id, "process_id": process_id},
                )
            client.execute_write(
                """
                MERGE (ab:Rejection {process_id: $process_id, anwendung_name: $anwendung_name})
                SET ab.prozess_name = $prozess_name
                """,
                {"process_id": process_id, "prozess_name": prozess_name, "anwendung_name": anwendung_name},
            )

    def get_confirmed_links_from_neo4j(self, client: Neo4jClient) -> list[dict]:
        rows = client.execute_read_unvalidated(
            """
            MATCH (a:Application)-[r:SERVES]->(p:Process)
            WHERE r.raw_name IS NOT NULL
              AND r.source IN ['manuell_bestaetigt', 'manueller_link']
            RETURN p.name AS process,
                   p.process_id AS process_id,
                   r.raw_name AS anwendung_name,
                   a.cmdb_id AS cmdb_id,
                   a.name AS resolved_to,
                   r.source AS quelle
            """
        )
        for row in rows:
            _validate_decision_row(row, confirmed=True)
        return [dict(row) for row in rows]

    def get_rejected_decisions_from_neo4j(self, client: Neo4jClient) -> list[dict]:
        rows = client.execute_read_unvalidated(
            """
            MATCH (ab:Rejection)
            OPTIONAL MATCH (p:Process {name: ab.prozess_name})
            WITH ab, collect(DISTINCT p.process_id) AS candidate_ids
            RETURN ab.prozess_name AS process,
                   ab.process_id AS process_id,
                   candidate_ids,
                   ab.anwendung_name AS anwendung_name
            """
        )
        decisions = []
        for row in rows:
            row = dict(row)
            if not row.get("process_id"):
                candidates = [value for value in row.get("candidate_ids", []) if value]
                if len(candidates) != 1:
                    raise ValueError("Legacy rejection has missing or ambiguous process identity; manual clarification required.")
                row["process_id"] = candidates[0]
            _validate_decision_row(row, confirmed=False)
            decisions.append({key: row[key] for key in ("process", "process_id", "anwendung_name")}
                             | {"cmdb_id": None})
        return decisions

    def load_org_units_from_neo4j(self, client: Neo4jClient) -> dict[str, str]:
        """Return {normalized_name: canonical_name} for all OrgUnit nodes."""
        rows = client.execute_read(
            "MATCH (o:OrgUnit) WHERE o.name IS NOT NULL RETURN o.name AS name",
            {},
        )
        result: dict[str, str] = {}
        for row in rows:
            name = (row.get("name") or "").strip()
            if name:
                result[normalize_org_unit_name(name)] = name
        return result

    def load_org_unit_aliases_from_neo4j(self, client: Neo4jClient) -> dict[str, tuple[str, ...]]:
        """Return every distinct target of each Alias→OrgUnit mapping."""
        rows = client.execute_read(
            """
            MATCH (alias:Alias)-[:MAY_REFER_TO]->(o:OrgUnit)
            WHERE alias.normalized_name IS NOT NULL AND o.name IS NOT NULL
            RETURN alias.normalized_name AS alias_normalized, o.name AS org_unit_name
            """,
            {},
        )
        result: dict[str, set[str]] = {}
        for row in rows:
            key = (row.get("alias_normalized") or "").strip()
            val = (row.get("org_unit_name") or "").strip()
            if key and val:
                result.setdefault(key, set()).add(val)
        return {key: tuple(sorted(values)) for key, values in result.items()}

    def write_role_only_decision(self, client: Neo4jClient, role_name: str) -> None:
        """Mark a Role node as role-only (not an OrgUnit) directly in Neo4j."""
        client.execute_write(
            "MATCH (r:Role {name: $role_name}) SET r.role_only = true",
            {"role_name": role_name},
        )

    def write_org_unit_alias(self, client: Neo4jClient, candidate_name: str, org_unit_name: str) -> None:
        """Project a confirmed org-unit candidate mapping as an Alias node in Neo4j.

        Creates (:Alias)-[:MAY_REFER_TO]->(:OrgUnit) so the pipeline can resolve
        the raw candidate string to the canonical OrgUnit without reading kb.json.
        No-op when candidate_name and org_unit_name normalise to the same value.
        """
        normalized_candidate = normalize_org_unit_name(candidate_name)
        normalized_target = normalize_org_unit_name(org_unit_name)
        if not normalized_candidate or normalized_candidate == normalized_target:
            return
        client.execute_write(
            """
            MERGE (alias:Alias {normalized_name: $normalized_name})
            ON CREATE SET alias.name = $alias_name,
                          alias.source_kind = $source_kind
            SET alias.name = coalesce(alias.name, $alias_name)
            WITH alias
            MERGE (o:OrgUnit {name: $org_unit_name})
            MERGE (alias)-[r:MAY_REFER_TO]->(o)
            SET r.source_kind = $source_kind
            """,
            {
                "normalized_name": normalized_candidate,
                "alias_name": candidate_name.strip(),
                "org_unit_name": org_unit_name.strip(),
                "source_kind": ALIAS_SOURCE_KIND_CONFIRMED_CANDIDATE,
            },
        )

    def upsert_org_unit_candidate(
        self,
        client: Neo4jClient,
        candidate_name: str,
        source_path: str = "",
        process_name: str = "",
        role_name: str = "",
    ) -> None:
        """Record an unresolved org-unit/role mention as an (:OrgCandidate) node.

        MERGE by normalized_name; provenance (source_path/process_name/role_name) is
        appended to list properties without duplicates. last_seen only advances while
        the candidate is still open, so a decided candidate keeps its decision date.
        """
        cleaned_name = " ".join(candidate_name.strip().split())
        if not cleaned_name:
            return
        normalized_name = normalize_org_unit_name(cleaned_name)
        today = date.today().isoformat()
        client.execute_write(
            """
            MERGE (k:OrgCandidate {normalized_name: $normalized_name})
            ON CREATE SET k.candidate_name = $candidate_name,
                          k.status = 'open',
                          k.mapped_org_unit = '',
                          k.source_paths = [],
                          k.process_names = [],
                          k.role_names = [],
                          k.first_seen = $today,
                          k.last_seen = $today
            SET k.source_paths = CASE
                    WHEN $source_path <> '' AND NOT $source_path IN k.source_paths
                    THEN k.source_paths + $source_path ELSE k.source_paths END,
                k.process_names = CASE
                    WHEN $process_name <> '' AND NOT $process_name IN k.process_names
                    THEN k.process_names + $process_name ELSE k.process_names END,
                k.role_names = CASE
                    WHEN $role_name <> '' AND NOT $role_name IN k.role_names
                    THEN k.role_names + $role_name ELSE k.role_names END,
                k.last_seen = CASE WHEN k.status = 'open' THEN $today ELSE k.last_seen END
            """,
            {
                "normalized_name": normalized_name,
                "candidate_name": cleaned_name,
                "source_path": source_path,
                "process_name": process_name,
                "role_name": role_name,
                "today": today,
            },
        )

    def load_org_unit_candidates(self, client: Neo4jClient, status: str | None = None) -> list[dict]:
        # OrgCandidate is an internal operational node (like Rejection) and is deliberately
        # excluded from graph_schema.py's LLM-facing allowlist, so execute_read's schema
        # validation would reject this query. Use the unvalidated read path instead.
        rows = client.execute_read_unvalidated(
            """
            MATCH (k:OrgCandidate)
            WHERE $status IS NULL OR k.status = $status
            RETURN k.candidate_name AS candidate_name,
                   k.normalized_name AS normalized_name,
                   k.status AS status,
                   k.mapped_org_unit AS mapped_org_unit,
                   k.source_paths AS source_paths,
                   k.process_names AS process_names,
                   k.role_names AS role_names,
                   k.first_seen AS first_seen,
                   k.last_seen AS last_seen
            """,
            {"status": status},
        )
        return [dict(row) for row in rows]

    def map_org_unit_candidate(self, client: Neo4jClient, candidate_name: str, target_org_unit: str) -> None:
        normalized_name = normalize_org_unit_name(candidate_name)
        if not normalized_name:
            return
        client.execute_write(
            """
            MATCH (k:OrgCandidate {normalized_name: $normalized_name})
            SET k.status = 'mapped',
                k.mapped_org_unit = $target_org_unit,
                k.last_seen = $today
            """,
            {
                "normalized_name": normalized_name,
                "target_org_unit": target_org_unit.strip(),
                "today": date.today().isoformat(),
            },
        )

    def reject_org_unit_candidate(self, client: Neo4jClient, candidate_name: str) -> None:
        normalized_name = normalize_org_unit_name(candidate_name)
        if not normalized_name:
            return
        client.execute_write(
            """
            MATCH (k:OrgCandidate {normalized_name: $normalized_name})
            SET k.status = 'rejected',
                k.mapped_org_unit = '',
                k.last_seen = $today
            """,
            {"normalized_name": normalized_name, "today": date.today().isoformat()},
        )

    def _resolve_org_unit_canonical_name(self, client: Neo4jClient, name: str) -> str:
        """Return canonical OrgUnit name via case-insensitive lookup; fall back to stripped input.

        First-seen wins: if an OrgUnit with the same name (different case) already exists,
        its stored name is used for the MERGE to avoid creating a duplicate node.
        """
        stripped = name.strip()
        rows = client.execute_read(
            "MATCH (o:OrgUnit) WHERE toLower(o.name) = toLower($name) RETURN o.name AS name LIMIT 1",
            {"name": stripped},
        )
        return rows[0]["name"] if rows else stripped

    def _resolve_duplicate_placeholders(self, client: Neo4jClient, process_id: str, process_name: str) -> None:
        client.execute_write(
            """
            MATCH (real:Process {process_id: $process_id})
            MATCH (placeholder:Process {name: $process_name, placeholder: true})
            WHERE elementId(real) <> elementId(placeholder)
            OPTIONAL MATCH (source:Process)-[:FOLLOWS]->(placeholder)
            WITH real, placeholder, collect(DISTINCT source) AS sources
            FOREACH (src IN sources |
                MERGE (src)-[:FOLLOWS]->(real)
            )
            """,
            {
                "process_id": process_id,
                "process_name": process_name,
            },
        )
        client.execute_write(
            """
            MATCH (real:Process {process_id: $process_id})
            MATCH (placeholder:Process {name: $process_name, placeholder: true})
            WHERE elementId(real) <> elementId(placeholder)
            OPTIONAL MATCH (placeholder)-[:FOLLOWS]->(target:Process)
            WITH real, placeholder, collect(DISTINCT target) AS targets
            FOREACH (dst IN targets |
                MERGE (real)-[:FOLLOWS]->(dst)
            )
            DETACH DELETE placeholder
            """,
            {
                "process_id": process_id,
                "process_name": process_name,
            },
        )

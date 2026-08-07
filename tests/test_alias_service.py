from services.alias_service import (
    delete_application_alias,
    delete_org_unit_alias,
    delete_process_alias,
    lookup_alias_matches,
    sync_curated_aliases,
    write_merged_org_unit_alias,
    write_merged_process_alias,
)


class RecordingNeo4jClient:
    def __init__(self, responses=None) -> None:
        self.responses = list(responses or [])
        self.queries: list[tuple[str, dict | None]] = []

    def ensure_constraints(self) -> None:
        self.queries.append(("ENSURE_CONSTRAINTS", None))

    def execute_write(self, query: str, parameters=None):
        self.queries.append((query, parameters))
        if self.responses:
            return self.responses.pop(0)
        return []

    def execute_read(self, query: str, parameters=None):
        self.queries.append((query, parameters))
        if self.responses:
            return self.responses.pop(0)
        return []

    def execute_read_unvalidated(self, query: str, parameters=None):
        self.queries.append((query, parameters))
        if self.responses:
            return self.responses.pop(0)
        return []


def test_sync_curated_aliases_projects_application_and_org_aliases() -> None:
    client = RecordingNeo4jClient()
    confirmed_links = [
        {
            "process": "Order",
            "anwendung_name": "SAP XY",
            "cmdb_id": "app-1",
            "resolved_to": "SAP BW",
            "quelle": "manuell_bestaetigt",
        }
    ]
    org_unit_candidates = [
        {
            "candidate_name": "Sales",
            "normalized_name": "sales",
            "source_paths": ["Input/process.txt"],
            "process_names": ["Order"],
            "role_names": [],
            "status": "mapped",
            "mapped_org_unit": "Sales Department",
            "first_seen": "2026-05-31",
            "last_seen": "2026-05-31",
        }
    ]

    written = sync_curated_aliases(client, confirmed_links, org_unit_candidates)

    assert written == 2
    queries = [query for query, _ in client.queries]
    assert any("MATCH (:Alias)-[r:MAY_REFER_TO]->()" in query for query in queries)
    assert any("MERGE (application:Application {cmdb_id: $cmdb_id})" in query for query in queries)
    assert any("MERGE (org_unit:OrgUnit {name: $target_name})" in query for query in queries)
    assert any("MATCH (alias:Alias)" in query and "DELETE alias" in query for query in queries)


def test_sync_curated_aliases_skips_identity_aliases() -> None:
    client = RecordingNeo4jClient()
    confirmed_links = [
        {
            "process": "Order",
            "anwendung_name": "SAP BW",
            "cmdb_id": "app-1",
            "resolved_to": "SAP BW",
            "quelle": "manuell_bestaetigt",
        }
    ]
    org_unit_candidates = [
        {
            "candidate_name": "Sales Department",
            "normalized_name": "sales department",
            "source_paths": ["Input/process.txt"],
            "process_names": ["Order"],
            "role_names": [],
            "status": "mapped",
            "mapped_org_unit": "Sales Department",
            "first_seen": "2026-05-31",
            "last_seen": "2026-05-31",
        }
    ]

    written = sync_curated_aliases(client, confirmed_links, org_unit_candidates)

    assert written == 0


def test_lookup_alias_matches_returns_supported_target_rows() -> None:
    client = RecordingNeo4jClient(
        responses=[
            [
                {
                    "entity_type": "OrgUnit",
                    "entity_name": "Sales Department",
                    "entity_id": "",
                    "alias_name": "Sales",
                }
            ]
        ]
    )

    rows = lookup_alias_matches(client, "  Sales  ")

    assert rows == [
        {
            "entity_type": "OrgUnit",
            "entity_name": "Sales Department",
            "entity_id": "",
            "alias_name": "Sales",
        }
    ]
    assert client.queries[0][1] == {"normalized_name": "sales"}
    assert "MATCH (alias:Alias" in client.queries[0][0]


def test_lookup_alias_matches_uses_unvalidated_read_path() -> None:
    class ReadPathClient(RecordingNeo4jClient):
        def execute_read(self, query: str, parameters=None):
            raise AssertionError("validated read path must not be used for alias lookup")

    client = ReadPathClient(
        responses=[
            [
                {
                    "entity_type": "OrgUnit",
                    "entity_name": "IT Infrastructure",
                    "entity_id": "",
                    "alias_name": "Team Platform",
                }
            ]
        ]
    )

    rows = lookup_alias_matches(client, "Team Platform")

    assert rows[0]["entity_name"] == "IT Infrastructure"


def test_delete_application_alias_removes_relation_and_orphan_alias_cleanup() -> None:
    client = RecordingNeo4jClient()

    delete_application_alias(client, "SAP CRM", "app-1", source_kind="confirmed_match")

    queries = [query for query, _ in client.queries]
    assert any("MATCH (alias:Alias {normalized_name: $normalized_name})-[r:MAY_REFER_TO]->(application:Application {cmdb_id: $cmdb_id})" in query for query in queries)
    assert any("WHERE NOT (alias)-[:MAY_REFER_TO]->()" in query for query in queries)


def test_write_merged_org_unit_alias_writes_alias_for_source_name() -> None:
    client = RecordingNeo4jClient()

    write_merged_org_unit_alias(client, "Team IT Plattforms", "Plattform IT")

    queries = [query for query, _ in client.queries]
    assert any("MERGE (alias:Alias {normalized_name: $normalized_name})" in query for query in queries)
    assert any("MERGE (alias)-[r:MAY_REFER_TO]->(org_unit)" in query for query in queries)
    params = [params for _, params in client.queries if params and params.get("target_name") == "Plattform IT"][0]
    assert params["source_kind"] == "merged_entity"


def test_write_merged_process_alias_writes_alias_for_source_name() -> None:
    client = RecordingNeo4jClient()

    write_merged_process_alias(client, "Reisekostenabrechnung", target_element_id="4711")

    queries = [query for query, _ in client.queries]
    assert any("MERGE (alias:Alias {normalized_name: $normalized_name})" in query for query in queries)
    assert any("MATCH (process:Process)" in query and "elementId(process) = $target_element_id" in query for query in queries)


def test_delete_org_unit_alias_removes_relation_and_orphan_alias_cleanup() -> None:
    client = RecordingNeo4jClient()

    delete_org_unit_alias(client, "Controlling", "Buchhaltung", source_kind="merged_entity")

    queries = [query for query, _ in client.queries]
    assert any("(target:OrgUnit {name: $target_name})" in query for query in queries)
    assert any("WHERE NOT (alias)-[:MAY_REFER_TO]->()" in query for query in queries)


def test_delete_process_alias_removes_relation_and_orphan_alias_cleanup() -> None:
    client = RecordingNeo4jClient()

    delete_process_alias(client, "Reisekostenabrechnung", target_element_id="4711", source_kind="merged_entity")

    queries = [query for query, _ in client.queries]
    assert any("elementId(target) = $target_element_id" in query for query in queries)
    assert any("WHERE NOT (alias)-[:MAY_REFER_TO]->()" in query for query in queries)

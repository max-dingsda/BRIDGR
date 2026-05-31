from knowledge_base import KnowledgeBase
from services.alias_service import lookup_alias_matches, sync_knowledge_base_aliases


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


def test_sync_knowledge_base_aliases_projects_application_and_org_aliases() -> None:
    client = RecordingNeo4jClient()
    knowledge_base = KnowledgeBase(
        confirmed=[
            {
                "prozess": "Order",
                "anwendung_name": "SAP XY",
                "cmdb_id": "app-1",
                "resolved_to": "SAP BW",
                "bestaetigt_am": "2026-05-31",
                "quelle": "manuell_bestaetigt",
            }
        ],
        rejected=[],
        disambiguation=[],
        process_identity=[],
        org_units=[{"name": "Sales Department", "created_at": "2026-05-31", "source": "manual"}],
        org_unit_candidates=[
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
        ],
    )

    written = sync_knowledge_base_aliases(client, knowledge_base)

    assert written == 2
    queries = [query for query, _ in client.queries]
    assert any("MATCH (:Alias)-[r:KANN_MEINEN]->()" in query for query in queries)
    assert any("MERGE (application:Anwendung {cmdb_id: $cmdb_id})" in query for query in queries)
    assert any("MERGE (org_unit:OrgEinheit {name: $target_name})" in query for query in queries)
    assert any("MATCH (alias:Alias)" in query and "DELETE alias" in query for query in queries)


def test_sync_knowledge_base_aliases_skips_identity_aliases() -> None:
    client = RecordingNeo4jClient()
    knowledge_base = KnowledgeBase(
        confirmed=[
            {
                "prozess": "Order",
                "anwendung_name": "SAP BW",
                "cmdb_id": "app-1",
                "resolved_to": "SAP BW",
                "bestaetigt_am": "2026-05-31",
                "quelle": "manuell_bestaetigt",
            }
        ],
        rejected=[],
        disambiguation=[],
        process_identity=[],
        org_units=[{"name": "Sales Department", "created_at": "2026-05-31", "source": "manual"}],
        org_unit_candidates=[
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
        ],
    )

    written = sync_knowledge_base_aliases(client, knowledge_base)

    assert written == 0


def test_lookup_alias_matches_returns_supported_target_rows() -> None:
    client = RecordingNeo4jClient(
        responses=[
            [
                {
                    "entity_type": "OrgEinheit",
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
            "entity_type": "OrgEinheit",
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
                    "entity_type": "OrgEinheit",
                    "entity_name": "IT Infrastructure",
                    "entity_id": "",
                    "alias_name": "Team Platform",
                }
            ]
        ]
    )

    rows = lookup_alias_matches(client, "Team Platform")

    assert rows[0]["entity_name"] == "IT Infrastructure"

from __future__ import annotations

from unittest.mock import MagicMock, patch

from services.merge_service import _reference_projection, load_process_merge_candidates, merge_org_units, merge_processes


class FakeNeo4jClient:
    def __init__(self) -> None:
        self.written: list[tuple[str, dict | None]] = []

    def execute_write(self, query: str, parameters=None):
        self.written.append((query, parameters))
        return []

    def execute_read_unvalidated(self, query: str, parameters=None):
        self.written.append((query, parameters))
        if "RETURN properties(source) AS props" in query:
            return [{"props": {"name": parameters["source_name"]}}]
        if "RETURN elementId(p) AS element_id" in query and "process_name" in query:
            return [{"element_id": "proc-a", "process_id": "P-1", "process_name": "Reisekosten prüfen"}]
        if "RETURN coalesce(source.name" in query:
            return [{
                "source_name": "Reisekostenabrechnung",
                "target_name": "Reisekosten abrechnen",
                "source_props": {"process_id": "PROC-046", "name": "Reisekostenabrechnung"},
            }]
        return []


def _make_config():
    return MagicMock()


@patch("services.merge_service.create_manual_decision")
@patch("services.merge_service.write_merged_org_unit_alias")
@patch("services.merge_service.get_session_neo4j_client")
@patch("services.merge_service.create_snapshot")
def test_merge_org_units_transfers_relationships_and_records_decision(
    mock_create_snapshot, mock_get_client, mock_write_alias, mock_create_manual_decision
) -> None:
    fake_client = FakeNeo4jClient()
    mock_get_client.return_value = fake_client
    config = _make_config()

    level, message = merge_org_units(config, "Team IT Plattforms", "Plattform IT")

    assert level == "success"
    assert "überführt" in message
    queries = [query for query, _ in fake_client.written]
    assert any("MATCH (source)-[:RESPONSIBLE_FOR]->(p:Process)" in query and "MERGE (target)-[:RESPONSIBLE_FOR]->(p)" in query for query in queries)
    assert any("MATCH (source)-[:CAN_ASSUME]->(r:Role)" in query and "MERGE (target)-[:CAN_ASSUME]->(r)" in query for query in queries)
    assert any("MATCH (alias:Alias)-[:MAY_REFER_TO]->(source)" in query and "MERGE (alias)-[:MAY_REFER_TO]->(target)" in query for query in queries)
    assert any("DETACH DELETE source" in query for query in queries)
    mock_write_alias.assert_called_once_with(fake_client, "Team IT Plattforms", "Plattform IT")
    payload = mock_create_manual_decision.call_args[0][2]
    assert payload["entity_type"] == "OrgUnit"
    assert "merge_preview" in payload
    mock_create_snapshot.assert_called_once_with(config, fake_client, trigger="merge", operation="merge_org_unit")


@patch("services.merge_service.get_session_neo4j_client")
def test_merge_org_units_rejects_identical_names_case_insensitive(mock_get_client) -> None:
    mock_get_client.return_value = FakeNeo4jClient()

    level, message = merge_org_units(_make_config(), "Plattform IT", "plattform it")

    assert level == "error"
    assert "identisch" in message


@patch("services.merge_service.create_manual_decision")
@patch("services.merge_service.write_merged_process_alias")
@patch("services.merge_service.get_session_neo4j_client")
@patch("services.merge_service.create_snapshot")
def test_merge_processes_transfers_relationships_and_records_decision(
    mock_create_snapshot, mock_get_client, mock_write_alias, mock_create_manual_decision
) -> None:
    fake_client = FakeNeo4jClient()
    mock_get_client.return_value = fake_client
    config = _make_config()

    level, message = merge_processes(config, "source-1", "target-1")

    assert level == "success"
    assert "überführt" in message
    queries = [query for query, _ in fake_client.written]
    assert any("MATCH (a:Application)-[r:SERVES]->(source)" in query and "MERGE (a)-[merged:SERVES]->(target)" in query for query in queries)
    assert any("MATCH (role:Role)-[:PARTICIPATES_IN]->(source)" in query and "MERGE (role)-[:PARTICIPATES_IN]->(target)" in query for query in queries)
    assert any("MATCH (successor:Process)-[:FOLLOWS]->(source)" in query and "MERGE (successor)-[:FOLLOWS]->(target)" in query for query in queries)
    for rel in ("REALIZES", "SUPPORTS", "REQUIRES", "PROCESSES", "AFFECTS", "INFLUENCES"):
        assert any(f"(n)-[:{rel}]->(source)" in query and f"(n)-[:{rel}]->(target)" in query for query in queries), f"incoming {rel} not transferred"
    for rel in ("SUPPORTS", "REQUIRES", "PROCESSES"):
        assert any(f"(source)-[:{rel}]->(n)" in query and f"(target)-[:{rel}]->(n)" in query for query in queries), f"outgoing {rel} not transferred"
    mock_write_alias.assert_called_once_with(fake_client, "Reisekostenabrechnung", target_element_id="target-1")
    payload = mock_create_manual_decision.call_args[0][2]
    assert payload["entity_type"] == "Process"
    assert payload["source_ref"] == "source-1"
    assert "merge_preview" in payload
    mock_create_snapshot.assert_called_once_with(config, fake_client, trigger="merge", operation="merge_process")


@patch("services.merge_service.get_session_neo4j_client")
def test_merge_processes_rejects_identical_refs(mock_get_client) -> None:
    mock_get_client.return_value = FakeNeo4jClient()

    level, message = merge_processes(_make_config(), "same", "same")

    assert level == "error"
    assert "identisch" in message


@patch("services.merge_service.get_session_neo4j_client")
def test_load_process_merge_candidates_returns_element_ids(mock_get_client) -> None:
    fake_client = FakeNeo4jClient()
    mock_get_client.return_value = fake_client

    rows = load_process_merge_candidates(_make_config())

    assert rows == [{"element_id": "proc-a", "process_id": "P-1", "process_name": "Reisekosten prüfen"}]


def test_reference_projection_prefers_stable_process_identifier() -> None:
    projection = _reference_projection("target")

    assert "WHEN target:Process THEN coalesce(target.process_id, target.name, elementId(target), '')" in projection
    assert "WHEN target:Application THEN coalesce(target.cmdb_id, target.name, '')" in projection

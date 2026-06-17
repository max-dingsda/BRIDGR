from __future__ import annotations

from unittest.mock import MagicMock, patch

from services.merge_service import merge_org_units


class FakeNeo4jClient:
    def __init__(self) -> None:
        self.written: list[tuple[str, dict | None]] = []

    def execute_write(self, query: str, parameters=None):
        self.written.append((query, parameters))
        return []


def _make_config():
    return MagicMock()


@patch("services.merge_service.create_manual_decision")
@patch("services.merge_service.write_merged_org_unit_alias")
@patch("services.merge_service.get_session_neo4j_client")
def test_merge_org_units_transfers_relationships_and_records_decision(
    mock_get_client, mock_write_alias, mock_create_manual_decision
) -> None:
    fake_client = FakeNeo4jClient()
    mock_get_client.return_value = fake_client

    level, message = merge_org_units(_make_config(), "Team IT Plattforms", "Plattform IT")

    assert level == "success"
    assert "überführt" in message
    queries = [query for query, _ in fake_client.written]
    assert any("MATCH (source)-[:VERANTWORTET]->(p:Prozess)" in query and "MERGE (target)-[:VERANTWORTET]->(p)" in query for query in queries)
    assert any("MATCH (source)-[:KANN_EINNEHMEN]->(r:Rolle)" in query and "MERGE (target)-[:KANN_EINNEHMEN]->(r)" in query for query in queries)
    assert any("MATCH (alias:Alias)-[:KANN_MEINEN]->(source)" in query and "MERGE (alias)-[:KANN_MEINEN]->(target)" in query for query in queries)
    assert any("DETACH DELETE source" in query for query in queries)
    mock_write_alias.assert_called_once_with(fake_client, "Team IT Plattforms", "Plattform IT")
    mock_create_manual_decision.assert_called_once()
    assert mock_create_manual_decision.call_args[0][1] == "entity_merge"


@patch("services.merge_service.get_session_neo4j_client")
def test_merge_org_units_rejects_identical_names_case_insensitive(mock_get_client) -> None:
    mock_get_client.return_value = FakeNeo4jClient()

    level, message = merge_org_units(_make_config(), "Plattform IT", "plattform it")

    assert level == "error"
    assert "identisch" in message


@patch("services.merge_service.create_manual_decision")
@patch("services.merge_service.write_merged_org_unit_alias")
@patch("services.merge_service.get_session_neo4j_client")
def test_merge_org_units_uses_merge_for_deduplication(
    mock_get_client, mock_write_alias, mock_create_manual_decision
) -> None:
    fake_client = FakeNeo4jClient()
    mock_get_client.return_value = fake_client

    merge_org_units(_make_config(), "Sales Dept", "Sales Department")

    queries = [query for query, _ in fake_client.written]
    assert any("MERGE (target)-[:VERANTWORTET]->(p)" in query for query in queries)
    assert any("MERGE (target)-[:VERANTWORTET]->(a)" in query for query in queries)
    assert any("MERGE (target)-[:KANN_EINNEHMEN]->(r)" in query for query in queries)
    assert any("MERGE (target)-[:IST_VERBUNDEN_MIT]->(n)" in query for query in queries)

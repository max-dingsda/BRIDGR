from unittest.mock import MagicMock, patch

import pytest

from services.organization_service import (
    assign_role_to_org_unit,
    clear_process_owner,
    load_all_processes_with_owner,
    load_unassigned_roles,
    set_process_owner,
)


class FakeNeo4jClient:
    def __init__(self, rows: list[dict] | None = None) -> None:
        self.written: list[tuple[str, dict | None]] = []
        self._rows = rows or []

    def execute_write(self, query: str, parameters=None):
        self.written.append((query, parameters))
        return self._rows


def _make_config():
    config = MagicMock()
    return config


@patch("services.organization_service.get_session_neo4j_client")
def test_load_unassigned_roles_returns_roles_from_neo4j(mock_get_client) -> None:
    fake_client = FakeNeo4jClient(rows=[
        {"rolle": "Einkäufer", "prozesse": ["Bestellabwicklung"]},
        {"rolle": "Vertrieb", "prozesse": ["Angebotserstellung", "Auftragsabwicklung"]},
    ])
    mock_get_client.return_value = fake_client

    result = load_unassigned_roles(_make_config())

    assert len(result) == 2
    assert result[0]["rolle"] == "Einkäufer"
    assert result[0]["prozesse"] == ["Bestellabwicklung"]
    assert result[1]["rolle"] == "Vertrieb"


@patch("services.organization_service.get_session_neo4j_client")
def test_load_unassigned_roles_returns_empty_list_when_none_pending(mock_get_client) -> None:
    fake_client = FakeNeo4jClient(rows=[])
    mock_get_client.return_value = fake_client

    result = load_unassigned_roles(_make_config())

    assert result == []


@patch("services.organization_service.get_session_neo4j_client")
def test_assign_role_to_org_unit_writes_kann_einnehmen(mock_get_client) -> None:
    fake_client = FakeNeo4jClient()
    mock_get_client.return_value = fake_client

    level, message = assign_role_to_org_unit(_make_config(), "Einkäufer", "Einkauf")

    assert level == "success"
    assert "Einkäufer" in message
    assert "Einkauf" in message
    kann_einnehmen_queries = [q for q, _ in fake_client.written if "KANN_EINNEHMEN" in q]
    assert len(kann_einnehmen_queries) == 1


@patch("services.organization_service.get_session_neo4j_client")
def test_assign_role_to_org_unit_rejects_empty_org_unit_name(mock_get_client) -> None:
    fake_client = FakeNeo4jClient()
    mock_get_client.return_value = fake_client

    level, _ = assign_role_to_org_unit(_make_config(), "Einkäufer", "   ")

    assert level == "error"
    assert not fake_client.written


@patch("services.organization_service.get_session_neo4j_client")
def test_load_all_processes_with_owner_returns_list(mock_get_client) -> None:
    fake_client = FakeNeo4jClient(rows=[
        {"prozess_id": "proc-1", "prozess": "Bestellabwicklung", "eigentuemer": "Einkauf"},
        {"prozess_id": "proc-2", "prozess": "Reklamation", "eigentuemer": None},
    ])
    mock_get_client.return_value = fake_client

    result = load_all_processes_with_owner(_make_config())

    assert len(result) == 2
    assert result[0]["prozess_id"] == "proc-1"
    assert result[0]["eigentuemer"] == "Einkauf"
    assert result[1]["eigentuemer"] is None


@patch("services.organization_service.get_session_neo4j_client")
def test_set_process_owner_writes_verantwortet(mock_get_client) -> None:
    fake_client = FakeNeo4jClient()
    mock_get_client.return_value = fake_client

    level, _ = set_process_owner(_make_config(), "proc-1", "Einkauf")

    assert level == "success"
    delete_queries = [q for q, _ in fake_client.written if "DELETE r" in q and "VERANTWORTET" in q]
    merge_queries = [q for q, _ in fake_client.written if "MERGE (o)-[:VERANTWORTET]->(p)" in q]
    assert len(delete_queries) == 1
    assert len(merge_queries) == 1


@patch("services.organization_service.get_session_neo4j_client")
def test_set_process_owner_rejects_empty_org_unit(mock_get_client) -> None:
    fake_client = FakeNeo4jClient()
    mock_get_client.return_value = fake_client

    level, _ = set_process_owner(_make_config(), "proc-1", "  ")

    assert level == "error"
    assert not fake_client.written


@patch("services.organization_service.get_session_neo4j_client")
def test_clear_process_owner_deletes_verantwortet(mock_get_client) -> None:
    fake_client = FakeNeo4jClient()
    mock_get_client.return_value = fake_client

    clear_process_owner(_make_config(), "proc-1")

    delete_queries = [q for q, _ in fake_client.written if "DELETE r" in q and "VERANTWORTET" in q]
    assert len(delete_queries) == 1
    params = [p for _, p in fake_client.written if p and p.get("process_id")]
    assert params[0]["process_id"] == "proc-1"


@patch("services.organization_service.get_session_neo4j_client")
def test_assign_role_to_org_unit_trims_org_unit_name(mock_get_client) -> None:
    fake_client = FakeNeo4jClient()
    mock_get_client.return_value = fake_client

    assign_role_to_org_unit(_make_config(), "Einkäufer", "  Einkauf  ")

    params_list = [p for _, p in fake_client.written if p and p.get("org_unit_name")]
    assert params_list[0]["org_unit_name"] == "Einkauf"

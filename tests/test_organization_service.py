from unittest.mock import MagicMock, patch

import pytest

from services.organization_service import (
    accept_process_owner_candidate,
    assign_role_to_org_unit,
    clear_process_owner,
    load_all_processes_with_owner,
    load_process_owner_candidates,
    load_unassigned_roles,
    mark_role_as_role_only,
    reject_process_owner_candidate,
    set_process_owner,
)


class FakeNeo4jClient:
    def execute_read_unvalidated(self, query, parameters=None):
        return self.execute_write(query, parameters)

    def __init__(self, rows: list[dict] | None = None) -> None:
        self.written: list[tuple[str, dict | None]] = []
        self._rows = rows or []

    def execute_write(self, query: str, parameters=None):
        self.written.append((query, parameters))
        return self._rows

    def execute_read(self, query: str, parameters=None):
        return []

    def transaction(self):
        from contextlib import nullcontext
        return nullcontext(self)

    serialized_writes = transaction

    def stage_artifact(self, path, payload):
        from processing.run_artifacts import atomic_write_json
        atomic_write_json(path, payload)

    def read_staged_artifact(self, path):
        return None


def _make_config():
    config = MagicMock()
    return config


@patch("services.organization_service.get_session_neo4j_client")
def test_load_unassigned_roles_returns_roles_from_neo4j(mock_get_client) -> None:
    fake_client = FakeNeo4jClient(rows=[
        {"role": "Einkäufer", "processes": ["Bestellabwicklung"]},
        {"role": "Vertrieb", "processes": ["Angebotserstellung", "Auftragsabwicklung"]},
    ])
    mock_get_client.return_value = fake_client

    result = load_unassigned_roles(_make_config())

    assert len(result) == 2
    assert result[0]["role"] == "Einkäufer"
    assert result[0]["processes"] == ["Bestellabwicklung"]
    assert result[1]["role"] == "Vertrieb"


@patch("services.organization_service.get_session_neo4j_client")
def test_load_unassigned_roles_returns_empty_list_when_none_pending(mock_get_client) -> None:
    fake_client = FakeNeo4jClient(rows=[])
    mock_get_client.return_value = fake_client

    result = load_unassigned_roles(_make_config())

    assert result == []


@patch("services.organization_service.get_session_neo4j_client")
def test_load_unassigned_roles_skips_roles_marked_as_role_only(mock_get_client) -> None:
    # Filtering by role_only happens in Cypher — fake client returns pre-filtered rows
    fake_client = FakeNeo4jClient(rows=[
        {"role": "Einkäufer", "processes": ["Bestellabwicklung"]},
    ])
    mock_get_client.return_value = fake_client

    result = load_unassigned_roles(_make_config())

    assert [entry["role"] for entry in result] == ["Einkäufer"]


@patch("services.organization_service.get_session_neo4j_client")
def test_load_unassigned_roles_skips_roles_matching_existing_org_units(mock_get_client) -> None:
    # Filtering by OrgUnit name match happens in Cypher — fake client returns pre-filtered rows
    fake_client = FakeNeo4jClient(rows=[
        {"role": "Einkäufer", "processes": ["Bestellabwicklung"]},
    ])
    mock_get_client.return_value = fake_client

    result = load_unassigned_roles(_make_config())

    assert [entry["role"] for entry in result] == ["Einkäufer"]


@patch("services.organization_service.get_session_neo4j_client")
@patch("services.organization_service.ensure_org_unit_registered")
@patch("services.organization_service.create_manual_decision")
def test_assign_role_to_org_unit_writes_kann_einnehmen(mock_create_manual_decision, _mock_register, mock_get_client) -> None:
    fake_client = FakeNeo4jClient()
    mock_get_client.return_value = fake_client

    level, message = assign_role_to_org_unit(_make_config(), "Einkäufer", "Einkauf")

    assert level == "success"
    assert "Einkäufer" in message
    assert "Einkauf" in message
    kann_einnehmen_queries = [q for q, _ in fake_client.written if "CAN_ASSUME" in q]
    assert len(kann_einnehmen_queries) == 1
    mock_create_manual_decision.assert_called_once()
    assert mock_create_manual_decision.call_args[0][1] == "manual_role_assignment"


@patch("services.organization_service.get_session_neo4j_client")
@patch("services.organization_service.ensure_org_unit_registered")
def test_assign_role_to_org_unit_rejects_empty_org_unit_name(_mock_register, mock_get_client) -> None:
    fake_client = FakeNeo4jClient()
    mock_get_client.return_value = fake_client

    level, _ = assign_role_to_org_unit(_make_config(), "Einkäufer", "   ")

    assert level == "error"
    assert not fake_client.written


@patch("services.organization_service.get_session_neo4j_client")
def test_load_all_processes_with_owner_returns_list(mock_get_client) -> None:
    fake_client = FakeNeo4jClient(rows=[
        {"process_id": "proc-1", "process": "Bestellabwicklung", "owner": "Einkauf"},
        {"process_id": "proc-2", "process": "Reklamation", "owner": None},
    ])
    mock_get_client.return_value = fake_client

    result = load_all_processes_with_owner(_make_config())

    assert len(result) == 2
    assert result[0]["process_id"] == "proc-1"
    assert result[0]["owner"] == "Einkauf"
    assert result[1]["owner"] is None


@patch("services.organization_service.get_session_neo4j_client")
@patch("services.organization_service.ensure_org_unit_registered")
@patch("services.organization_service.create_manual_decision")
def test_set_process_owner_writes_verantwortet(mock_create_manual_decision, _mock_register, mock_get_client) -> None:
    fake_client = FakeNeo4jClient()
    mock_get_client.return_value = fake_client

    level, _ = set_process_owner(_make_config(), "proc-1", "Einkauf", process_name="Reisekosten prüfen")

    assert level == "success"
    delete_queries = [q for q, _ in fake_client.written if "DELETE r" in q and "RESPONSIBLE_FOR" in q]
    merge_queries = [q for q, _ in fake_client.written if "MERGE (o)-[:RESPONSIBLE_FOR]->(p)" in q]
    assert len(delete_queries) == 1
    assert len(merge_queries) == 1
    mock_create_manual_decision.assert_called_once()
    assert mock_create_manual_decision.call_args[0][1] == "manual_process_owner_assignment"
    assert mock_create_manual_decision.call_args[0][2]["process_name"] == "Reisekosten prüfen"


@patch("services.organization_service.get_session_neo4j_client")
@patch("services.organization_service.ensure_org_unit_registered")
def test_set_process_owner_rejects_empty_org_unit(_mock_register, mock_get_client) -> None:
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

    delete_queries = [q for q, _ in fake_client.written if "DELETE r" in q and "RESPONSIBLE_FOR" in q]
    assert len(delete_queries) == 1
    params = [p for _, p in fake_client.written if p and p.get("process_id")]
    assert params[0]["process_id"] == "proc-1"


def _make_run_with_candidate(process_id: str, candidate: str, status: str = "") -> dict:
    doc: dict = {
        "extracted_process": {
            "process_id": process_id,
            "process_name": "Testprozess",
            "process_owner_candidate": candidate,
            "source_path": "Input/test.txt",
        }
    }
    if status:
        doc["process_owner_candidate_status"] = status
    return {"documents": [doc]}


@patch("services.organization_service.write_latest_run")
@patch("services.organization_service.load_latest_run")
@patch("services.organization_service.resolve_runtime_output_path")
@patch("services.organization_service.get_session_neo4j_client")
def test_load_process_owner_candidates_returns_pending(mock_neo4j, mock_output, mock_load, mock_write) -> None:
    mock_output.return_value = (MagicMock(), False)
    mock_load.return_value = _make_run_with_candidate("proc-1", "Einkauf")
    mock_neo4j.return_value = FakeNeo4jClient(rows=[{"process_id": "proc-1", "owner_count": 0}])

    result = load_process_owner_candidates(_make_config())

    assert len(result) == 1
    assert result[0]["process_id"] == "proc-1"
    assert result[0]["candidate_org_unit"] == "Einkauf"


@patch("services.organization_service.write_latest_run")
@patch("services.organization_service.load_latest_run")
@patch("services.organization_service.resolve_runtime_output_path")
@patch("services.organization_service.get_session_neo4j_client")
def test_load_process_owner_candidates_ignores_stale_artifacts_when_graph_is_empty(
    mock_neo4j, mock_output, mock_load, mock_write,
) -> None:
    mock_output.return_value = (MagicMock(), False)
    mock_load.return_value = _make_run_with_candidate("proc-1", "Einkauf")
    mock_neo4j.return_value = FakeNeo4jClient(rows=[])

    assert load_process_owner_candidates(_make_config()) == []


@patch("services.organization_service.write_latest_run")
@patch("services.organization_service.load_latest_run")
@patch("services.organization_service.resolve_runtime_output_path")
@patch("services.organization_service.get_session_neo4j_client")
def test_load_process_owner_candidates_skips_already_owned(mock_neo4j, mock_output, mock_load, mock_write) -> None:
    mock_output.return_value = (MagicMock(), False)
    mock_load.return_value = _make_run_with_candidate("proc-1", "Einkauf")
    mock_neo4j.return_value = FakeNeo4jClient(rows=[{"process_id": "proc-1", "owner_count": 1}])

    result = load_process_owner_candidates(_make_config())

    assert result == []


@patch("services.organization_service.write_latest_run")
@patch("services.organization_service.load_latest_run")
@patch("services.organization_service.resolve_runtime_output_path")
@patch("services.organization_service.get_session_neo4j_client")
def test_load_process_owner_candidates_skips_rejected(mock_neo4j, mock_output, mock_load, mock_write) -> None:
    mock_output.return_value = (MagicMock(), False)
    mock_load.return_value = _make_run_with_candidate("proc-1", "Einkauf", status="rejected")
    mock_neo4j.return_value = FakeNeo4jClient(rows=[{"process_id": "proc-1", "owner_count": 0}])

    result = load_process_owner_candidates(_make_config())

    assert result == []


@patch("services.organization_service.write_latest_run")
@patch("services.organization_service.load_latest_run")
@patch("services.organization_service.resolve_runtime_output_path")
@patch("services.organization_service.get_session_neo4j_client")
def test_reject_process_owner_candidate_sets_status(mock_neo4j, mock_output, mock_load, mock_write) -> None:
    run = _make_run_with_candidate("proc-1", "Einkauf")
    mock_output.return_value = (MagicMock(), False)
    mock_load.return_value = run
    mock_neo4j.return_value = FakeNeo4jClient()

    level, _ = reject_process_owner_candidate(_make_config(), "proc-1")

    assert level == "success"
    written_run = mock_write.call_args[0][0]
    doc = written_run["documents"][0]
    assert doc["process_owner_candidate_status"] == "rejected"


@patch("services.organization_service.write_latest_run")
@patch("services.organization_service.load_latest_run")
@patch("services.organization_service.resolve_runtime_output_path")
@patch("services.organization_service.get_session_neo4j_client")
@patch("services.organization_service.ensure_org_unit_registered")
def test_accept_process_owner_candidate_writes_verantwortet_and_status(
    _mock_register, mock_neo4j, mock_output, mock_load, mock_write
) -> None:
    run = _make_run_with_candidate("proc-1", "Einkauf")
    mock_output.return_value = (MagicMock(), False)
    mock_load.return_value = run
    mock_neo4j.return_value = FakeNeo4jClient()

    level, _ = accept_process_owner_candidate(_make_config(), "proc-1", "Einkauf", process_name="Testprozess")

    assert level == "success"
    verantwortet_queries = [q for q, _ in mock_neo4j.return_value.written if "RESPONSIBLE_FOR" in q and "MERGE" in q]
    assert len(verantwortet_queries) == 1
    written_run = mock_write.call_args[0][0]
    doc = written_run["documents"][0]
    assert doc["process_owner_candidate_status"] == "accepted"


@patch("services.organization_service.get_session_neo4j_client")
@patch("services.organization_service.ensure_org_unit_registered")
def test_assign_role_to_org_unit_trims_org_unit_name(_mock_register, mock_get_client) -> None:
    fake_client = FakeNeo4jClient()
    mock_get_client.return_value = fake_client

    assign_role_to_org_unit(_make_config(), "Einkäufer", "  Einkauf  ")

    params_list = [p for _, p in fake_client.written if p and p.get("org_unit_name")]
    assert params_list[0]["org_unit_name"] == "Einkauf"


@patch("services.organization_service.get_session_neo4j_client")
def test_mark_role_as_role_only_persists_decision(mock_get_client) -> None:
    fake_client = FakeNeo4jClient()
    mock_get_client.return_value = fake_client

    level, message = mark_role_as_role_only(_make_config(), "Freigeber")

    assert level == "success"
    assert "Freigeber" in message
    role_only_queries = [
        (query, params)
        for query, params in fake_client.written
        if "role_only" in query and params and params.get("role_name") == "Freigeber"
    ]
    assert len(role_only_queries) == 1

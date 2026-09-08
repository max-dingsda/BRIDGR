from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from core.neo4j_utils import Neo4jQueryError
from services.correction_service import revert_manual_decision


class FakeNeo4jClient:
    def __init__(self) -> None:
        self.written: list[tuple[str, dict | None]] = []
        self.reads = 0

    def execute_write(self, query: str, parameters=None):
        self.written.append((query, parameters))
        return []

    def execute_read_unvalidated(self, query: str, parameters=None):
        self.written.append((query, parameters))
        self.reads += 1
        return [{"element_id": "restored-source"}]

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
    config.cmdb_uuid_column = "app_id"
    config.cmdb_name_column = "application_name"
    return config


@patch("services.correction_service.create_manual_decision")
@patch("services.correction_service.mark_manual_decision_reverted")
@patch("services.correction_service.get_manual_decision")
@patch("services.correction_service.get_session_neo4j_client")
def test_revert_manual_link_deletes_matching_dient_and_marks_decision(
    mock_get_client, mock_get_decision, mock_mark_reverted, mock_create_manual_decision
) -> None:
    fake_client = FakeNeo4jClient()
    mock_get_client.return_value = fake_client
    mock_get_decision.return_value = type(
        "Decision",
        (),
        {
            "decision_id": "dec-1",
            "decision_type": "manual_link",
            "status": "active",
            "payload_json": json.dumps({
                "process_id": "proc-1",
                "cmdb_id": "cmdb-1",
                "application_name": "Mail",
                "source_path": "",
            }),
        },
    )()

    level, message = revert_manual_decision(_make_config(), "dec-1")

    assert level == "success"
    assert "zurückgenommen" in message
    delete_queries = [q for q, _ in fake_client.written if "MATCH (a:Application {cmdb_id: $cmdb_id})-[r:SERVES]->(p:Process" in q]
    assert len(delete_queries) == 1
    mock_mark_reverted.assert_called_once_with(fake_client, "dec-1")
    mock_create_manual_decision.assert_called_once()


@patch("services.correction_service.create_manual_decision")
@patch("services.correction_service.mark_manual_decision_reverted")
@patch("services.correction_service.delete_application_alias")
@patch("services.correction_service.get_manual_decision")
@patch("services.correction_service.get_session_neo4j_client")
def test_revert_confirmed_candidate_link_deletes_matching_confirmed_dient(
    mock_get_client, mock_get_decision, mock_delete_alias, mock_mark_reverted, mock_create_manual_decision
) -> None:
    fake_client = FakeNeo4jClient()
    mock_get_client.return_value = fake_client
    mock_get_decision.return_value = type(
        "Decision",
        (),
        {
            "decision_id": "dec-2",
            "decision_type": "confirmed_candidate_link",
            "status": "active",
            "payload_json": json.dumps({
                "process_id": "proc-1",
                "cmdb_id": "cmdb-1",
                "application_name": "Mail",
                "matched_name": "Mail System",
                "source_path": "",
            }),
        },
    )()

    level, _ = revert_manual_decision(_make_config(), "dec-2")

    assert level == "success"
    params = [p for _, p in fake_client.written if p and p.get("cmdb_id") == "cmdb-1"]
    assert params[0]["raw_name"] == "Mail"
    mock_delete_alias.assert_called_once_with(
        fake_client,
        "Mail",
        "cmdb-1",
        source_kind="confirmed_match",
    )
    mock_mark_reverted.assert_called_once()
    mock_create_manual_decision.assert_called_once()


@patch("services.correction_service.create_manual_decision")
@patch("services.correction_service.mark_manual_decision_reverted")
@patch("services.correction_service.get_manual_decision")
@patch("services.correction_service.get_session_neo4j_client")
def test_revert_process_owner_assignment_deletes_verantwortet(
    mock_get_client, mock_get_decision, mock_mark_reverted, mock_create_manual_decision
) -> None:
    fake_client = FakeNeo4jClient()
    mock_get_client.return_value = fake_client
    mock_get_decision.return_value = type(
        "Decision",
        (),
        {
            "decision_id": "dec-3",
            "decision_type": "manual_process_owner_assignment",
            "status": "active",
            "payload_json": json.dumps({
                "process_id": "proc-1",
                "org_unit_name": "Einkauf",
            }),
        },
    )()

    level, _ = revert_manual_decision(_make_config(), "dec-3")

    assert level == "success"
    delete_queries = [q for q, _ in fake_client.written if "RESPONSIBLE_FOR" in q and "DELETE r" in q]
    assert len(delete_queries) == 1
    mock_mark_reverted.assert_called_once()
    mock_create_manual_decision.assert_called_once()


@patch("services.correction_service.create_manual_decision")
@patch("services.correction_service.mark_manual_decision_reverted")
@patch("services.correction_service.get_manual_decision")
@patch("services.correction_service.get_session_neo4j_client")
def test_revert_role_assignment_deletes_kann_einnehmen(
    mock_get_client, mock_get_decision, mock_mark_reverted, mock_create_manual_decision
) -> None:
    fake_client = FakeNeo4jClient()
    mock_get_client.return_value = fake_client
    mock_get_decision.return_value = type(
        "Decision",
        (),
        {
            "decision_id": "dec-4",
            "decision_type": "manual_role_assignment",
            "status": "active",
            "payload_json": json.dumps({
                "role_name": "Einkäufer",
                "org_unit_name": "Einkauf",
            }),
        },
    )()

    level, _ = revert_manual_decision(_make_config(), "dec-4")

    assert level == "success"
    delete_queries = [q for q, _ in fake_client.written if "CAN_ASSUME" in q and "DELETE r" in q]
    assert len(delete_queries) == 1
    mock_mark_reverted.assert_called_once()
    mock_create_manual_decision.assert_called_once()


@patch("services.correction_service.get_manual_decision")
@patch("services.correction_service.get_session_neo4j_client")
def test_revert_manual_decision_returns_error_when_missing(mock_get_client, mock_get_decision) -> None:
    mock_get_client.return_value = FakeNeo4jClient()
    mock_get_decision.return_value = None

    level, message = revert_manual_decision(_make_config(), "missing")

    assert level == "error"
    assert "nicht gefunden" in message










@patch("services.correction_service.mark_manual_decision_reverted")
@patch("services.correction_service.get_manual_decision")
@patch("services.correction_service.get_session_neo4j_client")
def test_revert_manual_decision_returns_error_on_neo4j_failure(
    mock_get_client, mock_get_decision, mock_mark_reverted
) -> None:
    fake_client = FakeNeo4jClient()
    mock_get_client.return_value = fake_client
    mock_get_decision.return_value = type(
        "Decision",
        (),
        {
            "decision_id": "dec-7",
            "decision_type": "manual_role_assignment",
            "status": "active",
            "payload_json": json.dumps({
                "role_name": "Einkäufer",
                "org_unit_name": "Einkauf",
            }),
        },
    )()

    def fail_write(query: str, parameters=None):
        raise Neo4jQueryError("boom")

    fake_client.execute_write = fail_write

    level, message = revert_manual_decision(_make_config(), "dec-7")

    assert level == "error"
    assert "boom" in message
    mock_mark_reverted.assert_not_called()


@patch("services.correction_service.create_manual_decision")
@patch("services.correction_service.mark_manual_decision_reverted")
@patch("services.correction_service.get_manual_decision")
@patch("services.correction_service.get_session_neo4j_client")
def test_revert_manual_decision_returns_error_when_audit_write_fails(
    mock_get_client, mock_get_decision, mock_mark_reverted, mock_create_manual_decision
) -> None:
    fake_client = FakeNeo4jClient()
    mock_get_client.return_value = fake_client
    mock_get_decision.return_value = type(
        "Decision",
        (),
        {
            "decision_id": "dec-8",
            "decision_type": "manual_role_assignment",
            "status": "active",
            "payload_json": json.dumps({
                "role_name": "Einkäufer",
                "org_unit_name": "Einkauf",
            }),
        },
    )()
    mock_create_manual_decision.side_effect = Neo4jQueryError("audit failed")

    level, message = revert_manual_decision(_make_config(), "dec-8")

    assert level == "error"
    assert "audit failed" in message
    mock_mark_reverted.assert_called_once()


@patch("services.correction_service.create_manual_decision")
@patch("services.correction_service.mark_manual_decision_reverted")
@patch("services.correction_service.get_manual_decision")
@patch("services.correction_service.get_session_neo4j_client")
def test_revert_manual_decision_records_revert_audit_as_reverted_status(
    mock_get_client, mock_get_decision, mock_mark_reverted, mock_create_manual_decision
) -> None:
    fake_client = FakeNeo4jClient()
    mock_get_client.return_value = fake_client
    mock_get_decision.return_value = type(
        "Decision",
        (),
        {
            "decision_id": "dec-9",
            "decision_type": "manual_role_assignment",
            "status": "active",
            "payload_json": json.dumps({
                "role_name": "Einkäufer",
                "org_unit_name": "Einkauf",
            }),
        },
    )()

    level, _ = revert_manual_decision(_make_config(), "dec-9")

    assert level == "success"
    assert mock_create_manual_decision.call_args.kwargs["status"] == "reverted"

from __future__ import annotations

import json

from services.decision_service import (
    create_manual_decision,
    get_manual_decision,
    list_recent_manual_decisions,
    mark_manual_decision_reverted,
)


class RecordingNeo4jClient:
    def __init__(self) -> None:
        self.writes: list[tuple[str, dict | None]] = []
        self.reads: list[tuple[str, dict | None]] = []
        self.read_unvalidated_responses: list[list[dict]] = []

    def execute_write(self, query: str, parameters=None):
        self.writes.append((query, parameters))
        return []

    def execute_read_unvalidated(self, query: str, parameters=None):
        self.reads.append((query, parameters))
        if self.read_unvalidated_responses:
            return self.read_unvalidated_responses.pop(0)
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


def test_create_manual_decision_writes_manual_decision_node() -> None:
    client = RecordingNeo4jClient()

    decision = create_manual_decision(
        client,
        "manual_link",
        {"process_id": "proc-1", "cmdb_id": "app-1"},
        notes="created during review",
    )

    assert decision.decision_type == "manual_link"
    assert decision.status == "active"
    assert json.loads(decision.payload_json) == {"cmdb_id": "app-1", "process_id": "proc-1"}
    assert len(client.writes) == 1
    query, params = client.writes[0]
    assert "CREATE (d:ManualDecision" in query
    assert params["decision_id"] == decision.decision_id
    assert params["decision_type"] == "manual_link"
    assert params["status"] == "active"
    assert params["notes"] == "created during review"


def test_create_manual_decision_accepts_non_active_status() -> None:
    client = RecordingNeo4jClient()

    decision = create_manual_decision(
        client,
        "decision_revert",
        {"reverted_decision_id": "dec-1"},
        status="reverted",
    )

    assert decision.status == "reverted"
    assert client.writes[0][1]["status"] == "reverted"


def test_get_manual_decision_returns_none_when_missing() -> None:
    client = RecordingNeo4jClient()

    result = get_manual_decision(client, "missing-id")

    assert result is None


def test_get_manual_decision_returns_existing_decision() -> None:
    client = RecordingNeo4jClient()
    client.read_unvalidated_responses = [[
        {
            "decision_id": "dec-1",
            "decision_type": "manual_link",
            "status": "active",
            "created_at": "2026-06-17T10:00:00Z",
            "payload_json": '{"process_id":"proc-1"}',
            "supersedes_decision_id": None,
            "reverted_at": None,
            "notes": "note",
        }
    ]]

    result = get_manual_decision(client, "dec-1")

    assert result is not None
    assert result.decision_id == "dec-1"
    assert result.decision_type == "manual_link"
    assert result.notes == "note"
    query, _ = client.reads[0]
    assert "WITH properties(d) AS props" in query


def test_list_recent_manual_decisions_returns_rows_in_order() -> None:
    client = RecordingNeo4jClient()
    client.read_unvalidated_responses = [[
        {
            "decision_id": "dec-2",
            "decision_type": "entity_merge",
            "status": "active",
            "created_at": "2026-06-17T11:00:00Z",
            "payload_json": '{"target":"Sales"}',
            "supersedes_decision_id": None,
            "reverted_at": None,
            "notes": None,
        },
        {
            "decision_id": "dec-1",
            "decision_type": "manual_link",
            "status": "reverted",
            "created_at": "2026-06-17T10:00:00Z",
            "payload_json": '{"process_id":"proc-1"}',
            "supersedes_decision_id": None,
            "reverted_at": "2026-06-17T12:00:00Z",
            "notes": None,
        },
    ]]

    result = list_recent_manual_decisions(client, limit=5)

    assert [item.decision_id for item in result] == ["dec-2", "dec-1"]
    assert client.reads[0][1] == {"limit": 5}
    query, _ = client.reads[0]
    assert "WITH properties(d) AS props" in query


def test_mark_manual_decision_reverted_updates_status_and_timestamp() -> None:
    client = RecordingNeo4jClient()

    reverted_at = mark_manual_decision_reverted(client, "dec-1")

    assert reverted_at.endswith("Z")
    assert len(client.writes) == 1
    query, params = client.writes[0]
    assert "MATCH (d:ManualDecision {decision_id: $decision_id})" in query
    assert "SET d.status = $status" in query
    assert params["decision_id"] == "dec-1"
    assert params["status"] == "reverted"
    assert params["reverted_at"] == reverted_at

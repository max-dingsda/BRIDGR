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
    delete_queries = [q for q, _ in fake_client.written if "MATCH (a:Anwendung {cmdb_id: $cmdb_id})-[r:DIENT]->(p:Prozess" in q]
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
    delete_queries = [q for q, _ in fake_client.written if "VERANTWORTET" in q and "DELETE r" in q]
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
    delete_queries = [q for q, _ in fake_client.written if "KANN_EINNEHMEN" in q and "DELETE r" in q]
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


@patch("services.correction_service.create_manual_decision")
@patch("services.correction_service.mark_manual_decision_reverted")
@patch("services.correction_service.delete_org_unit_alias")
@patch("services.correction_service.get_manual_decision")
@patch("services.correction_service.get_session_neo4j_client")
def test_revert_org_unit_merge_restores_node_and_relationships(
    mock_get_client, mock_get_decision, mock_delete_alias, mock_mark_reverted, mock_create_manual_decision
) -> None:
    fake_client = FakeNeo4jClient()
    mock_get_client.return_value = fake_client
    mock_get_decision.return_value = type(
        "Decision",
        (),
        {
            "decision_id": "dec-5",
            "decision_type": "entity_merge",
            "status": "active",
            "payload_json": json.dumps({
                "entity_type": "OrgEinheit",
                "source_name": "Controlling",
                "target_name": "Buchhaltung",
                "merge_preview": {
                    "source_properties": {"name": "Controlling"},
                    "source_outgoing": [{"rel_type": "VERANTWORTET", "other_label": "Prozess", "other_ref": "Auftrag erfassen"}],
                    "source_incoming": [{"rel_type": "KANN_MEINEN", "other_label": "Alias", "other_ref": "CTRL"}],
                    "target_outgoing_keys": [],
                    "target_incoming_keys": [],
                },
            }),
        },
    )()

    level, message = revert_manual_decision(_make_config(), "dec-5")

    assert level == "success"
    assert "Controlling" in message
    queries = [q for q, _ in fake_client.written]
    assert any("MERGE (source:OrgEinheit {name: $source_name})" in query for query in queries)
    assert any("MERGE (source)-[:VERANTWORTET]->(other)" in query for query in queries)
    assert any("coalesce(other.prozess_id, '') = $other_ref" in query or "coalesce(other.name, '') = $other_ref" in query for query in queries)
    assert any("MATCH (other)-[r:KANN_MEINEN]->(source)" in query for query in queries)
    mock_delete_alias.assert_called_once_with(fake_client, "Controlling", "Buchhaltung", source_kind="merged_entity")
    mock_mark_reverted.assert_called_once()
    mock_create_manual_decision.assert_called_once()


@patch("services.correction_service.create_manual_decision")
@patch("services.correction_service.mark_manual_decision_reverted")
@patch("services.correction_service.delete_process_alias")
@patch("services.correction_service.get_manual_decision")
@patch("services.correction_service.get_session_neo4j_client")
def test_revert_process_merge_restores_node_and_relationships(
    mock_get_client, mock_get_decision, mock_delete_alias, mock_mark_reverted, mock_create_manual_decision
) -> None:
    fake_client = FakeNeo4jClient()
    mock_get_client.return_value = fake_client
    mock_get_decision.return_value = type(
        "Decision",
        (),
        {
            "decision_id": "dec-6",
            "decision_type": "entity_merge",
            "status": "active",
            "payload_json": json.dumps({
                "entity_type": "Prozess",
                "source_name": "Reisekostenabrechnung",
                "target_ref": "target-1",
                "merge_preview": {
                    "source_properties": {"prozess_id": "PROC-046", "name": "Reisekostenabrechnung"},
                    "target_properties": {"prozess_id": "PROC-045", "name": "Reisekosten abrechnen"},
                    "source_outgoing": [{"rel_type": "FOLGT_AUF", "other_label": "Prozess", "other_ref": "prev-1"}],
                    "source_incoming": [{"rel_type": "DIENT", "other_label": "Anwendung", "other_ref": "app-1"}],
                    "target_outgoing_keys": [],
                    "target_incoming_keys": [],
                },
            }),
        },
    )()

    level, message = revert_manual_decision(_make_config(), "dec-6")

    assert level == "success"
    assert "Reisekostenabrechnung" in message
    queries = [q for q, _ in fake_client.written]
    assert any("SET target.prozess_id = $target_process_id" in query for query in queries)
    assert not any("CREATE (source:Prozess)" in query for query in queries)
    assert any("SET source += $source_properties" in query for query in queries)
    assert any("MERGE (source)-[:FOLGT_AUF]->(other)" in query for query in queries)
    assert any("MERGE (other)-[:DIENT]->(source)" in query for query in queries)
    mock_delete_alias.assert_called_once_with(
        fake_client,
        "Reisekostenabrechnung",
        target_element_id="target-1",
        source_kind="merged_entity",
    )
    mock_mark_reverted.assert_called_once()
    mock_create_manual_decision.assert_called_once()


def test_revert_process_match_supports_element_id_process_id_and_name() -> None:
    from services.correction_service import _node_match

    query = _node_match("other", "Prozess")

    assert "elementId(other) = $other_ref" in query
    assert "coalesce(other.prozess_id, '') = $other_ref" in query
    assert "coalesce(other.name, '') = $other_ref" in query


def test_revert_name_based_domain_labels_are_supported() -> None:
    from services.correction_service import _node_match

    query = _node_match("other", "Anforderung")

    assert query == "MATCH (other:Anforderung {name: $other_ref})"


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
def test_revert_manual_decision_returns_warning_when_audit_write_fails(
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

    assert level == "warning"
    assert "fachlich ausgeführt" in message
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

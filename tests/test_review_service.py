from __future__ import annotations

from unittest.mock import MagicMock, patch

from services.review_service import confirm_review_link, save_manual_link


class FakeNeo4jClient:
    def __init__(self) -> None:
        self.written: list[tuple[str, dict | None]] = []

    def execute_write(self, query: str, parameters=None):
        self.written.append((query, parameters))
        return []


def _make_config():
    return MagicMock()


@patch("services.review_service.persist_single_document_refresh")
@patch("services.review_service.create_manual_decision")
@patch("services.review_service.get_session_neo4j_client")
def test_confirm_review_link_records_manual_decision(
    mock_get_client, mock_create_manual_decision, mock_refresh
) -> None:
    fake_client = FakeNeo4jClient()
    mock_get_client.return_value = fake_client

    message = confirm_review_link(
        _make_config(),
        process_name="Incident Management",
        application_name="Mail",
        cmdb_id="cmdb-1",
        matched_name="Mail System",
        process_id="proc-1",
        source_path="Input/process.txt",
        cmdb_rows=[],
    )

    assert "bestaetigt" in message
    mock_create_manual_decision.assert_called_once()
    args = mock_create_manual_decision.call_args[0]
    assert args[1] == "confirmed_candidate_link"
    payload = args[2]
    assert payload["process_id"] == "proc-1"
    assert payload["application_name"] == "Mail"
    assert payload["cmdb_id"] == "cmdb-1"
    mock_refresh.assert_called_once()


@patch("services.review_service.persist_single_document_refresh")
@patch("services.review_service.create_manual_decision")
@patch("services.review_service.get_session_neo4j_client")
def test_save_manual_link_records_manual_decision(
    mock_get_client, mock_create_manual_decision, mock_refresh
) -> None:
    fake_client = FakeNeo4jClient()
    mock_get_client.return_value = fake_client

    message = save_manual_link(
        _make_config(),
        process_name="Incident Management",
        application_name="Mail",
        cmdb_id="cmdb-1",
        matched_name="Mail System",
        process_id="proc-1",
        source_path="Input/process.txt",
        cmdb_rows=[],
    )

    assert "gespeichert" in message
    mock_create_manual_decision.assert_called_once()
    args = mock_create_manual_decision.call_args[0]
    assert args[1] == "manual_link"
    payload = args[2]
    assert payload["process_id"] == "proc-1"
    assert payload["application_name"] == "Mail"
    assert payload["cmdb_id"] == "cmdb-1"
    mock_refresh.assert_called_once()

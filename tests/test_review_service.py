from __future__ import annotations

from unittest.mock import MagicMock, patch

from services.review_service import confirm_review_link, confirm_review_links_batch, save_manual_link


class FakeNeo4jClient:
    def __init__(self) -> None:
        self.written: list[tuple[str, dict | None]] = []

    def execute_write(self, query: str, parameters=None):
        self.written.append((query, parameters))
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


@patch("services.review_service.persist_single_document_refresh")
@patch("services.review_service.create_manual_decision")
@patch("services.review_service.get_session_neo4j_client")
def test_confirm_review_links_batch_confirms_each_row_and_refreshes_per_source(
    mock_get_client, mock_create_decision, mock_refresh
) -> None:
    fake_client = FakeNeo4jClient()
    mock_get_client.return_value = fake_client

    rows = [
        {
            "process": "Budgetplanung",
            "process_id": "proc-1",
            "anwendung_im_prozess": "SAP CO",
            "anwendung_in_cmdb": "SAP S/4HANA CO",
            "cmdb_id": "cmdb-42",
            "source_path": "Input/a.txt",
        },
        {
            "process": "Forecast aktualisieren",
            "process_id": "proc-2",
            "anwendung_im_prozess": "SAP CO",
            "anwendung_in_cmdb": "SAP S/4HANA CO",
            "cmdb_id": "cmdb-42",
            "source_path": "Input/b.txt",
        },
    ]

    message = confirm_review_links_batch(_make_config(), rows, cmdb_rows=[])

    assert "2" in message
    assert "SAP CO" in message
    assert mock_create_decision.call_count == 2
    decision_types = [call[0][1] for call in mock_create_decision.call_args_list]
    assert all(dt == "confirmed_candidate_link" for dt in decision_types)
    assert mock_refresh.call_count == 2


@patch("services.review_service.persist_single_document_refresh")
@patch("services.review_service.create_manual_decision")
@patch("services.review_service.get_session_neo4j_client")
def test_confirm_review_links_batch_refreshes_once_per_unique_source_path(
    mock_get_client, mock_create_decision, mock_refresh
) -> None:
    fake_client = FakeNeo4jClient()
    mock_get_client.return_value = fake_client

    rows = [
        {
            "process": "Process A",
            "process_id": "proc-1",
            "anwendung_im_prozess": "Outlook",
            "anwendung_in_cmdb": "Microsoft 365 Outlook",
            "cmdb_id": "cmdb-99",
            "source_path": "Input/shared.txt",
        },
        {
            "process": "Process B",
            "process_id": "proc-2",
            "anwendung_im_prozess": "Outlook",
            "anwendung_in_cmdb": "Microsoft 365 Outlook",
            "cmdb_id": "cmdb-99",
            "source_path": "Input/shared.txt",
        },
    ]

    confirm_review_links_batch(_make_config(), rows, cmdb_rows=[])

    assert mock_refresh.call_count == 1

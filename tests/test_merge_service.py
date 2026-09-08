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




@patch("services.merge_service.get_session_neo4j_client")
def test_merge_org_units_rejects_identical_names_case_insensitive(mock_get_client) -> None:
    mock_get_client.return_value = FakeNeo4jClient()

    level, message = merge_org_units(_make_config(), "Plattform IT", "plattform it")

    assert level == "error"
    assert "identisch" in message




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

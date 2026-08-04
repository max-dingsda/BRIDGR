from pathlib import Path

from core.app_config import AppConfig
from processing.run_artifacts import load_latest_run, write_latest_run
from services import cmdb_service, review_service, runtime_service


def test_persist_cmdb_sync_refreshes_latest_run_with_current_cmdb_rows(tmp_path: Path, monkeypatch) -> None:
    input_dir = tmp_path / "Input"
    input_dir.mkdir()
    (input_dir / "cmdb.csv").write_text(
        "app_id,application_name,entity_type\n"
        "cmdb-1,SAP ERP,application\n",
        encoding="utf-8",
    )

    debug_events: list[tuple[str, dict]] = []

    monkeypatch.setattr(runtime_service, "get_session_neo4j_client", lambda _config: object())
    monkeypatch.setattr(runtime_service, "write_debug_log", lambda _config, event, details: debug_events.append((event, details)))
    snapshot_calls: list[tuple[str, str]] = []
    monkeypatch.setattr(
        cmdb_service,
        "create_snapshot",
        lambda _config, _client, *, trigger, operation: snapshot_calls.append((trigger, operation)),
    )
    monkeypatch.setattr(
        cmdb_service,
        "sync_cmdb_to_neo4j",
        lambda _config, _client: cmdb_service.CmdbSyncResult(
            entity_count=1,
            relation_count=0,
            owner_assignment_count=0,
            owner_candidate_count=0,
            refreshed_document_count=0,
        ),
    )

    refreshed_rows: list[dict[str, str]] = []

    def fake_refresh(_config: AppConfig, cmdb_rows: list[dict[str, str]]) -> int:
        refreshed_rows.extend(cmdb_rows)
        return 4

    monkeypatch.setattr(review_service, "persist_latest_run_refresh", fake_refresh)

    result = cmdb_service.persist_cmdb_sync(
        AppConfig(
            input_path=str(input_dir),
            cmdb_type_files={"application": "cmdb.csv"},
            cmdb_uuid_column="app_id",
            cmdb_name_column="application_name",
        )
    )

    assert result.refreshed_document_count == 4
    assert snapshot_calls == [("cmdb_sync", "explicit_cmdb_sync")]
    assert refreshed_rows == [{"app_id": "cmdb-1", "application_name": "SAP ERP", "entity_type": "application"}]
    assert len(debug_events) == 1
    event_name, event_details = debug_events[0]
    assert event_name == "cmdb_sync"
    assert event_details["entity_count"] == 1
    assert event_details["relation_count"] == 0
    assert event_details["refreshed_document_count"] == 4
    assert event_details["cmdb_type_files"] == {"application": "cmdb.csv"}


def test_sync_cmdb_to_neo4j_uses_type_files_when_configured(tmp_path: Path, monkeypatch) -> None:
    input_dir = tmp_path / "Input"
    input_dir.mkdir()
    (input_dir / "apps.csv").write_text(
        "id;name;owner_name;runs_on\nAPP-1;SAP ERP;Buchhaltung;SRV-1\n",
        encoding="utf-8",
    )
    (input_dir / "servers.csv").write_text(
        "id;name;server_type;owner_name\nSRV-1;ns-001;virtual;IT-Betrieb\n",
        encoding="utf-8",
    )

    synced_entities: list = []
    synced_relations: list = []
    upserted_candidates: list = []

    class FakeGraphWriter:
        def load_org_units_from_neo4j(self, _client):
            return {}

        def load_org_unit_aliases_from_neo4j(self, _client):
            return {}

        def sync_cmdb(self, _client, normalized_cmdb, owner_assignments):
            synced_entities.extend(normalized_cmdb.entities)
            synced_relations.extend(normalized_cmdb.relations)

        def upsert_org_unit_candidate(self, _client, candidate_name, source_path, process_name, role_name):
            upserted_candidates.append(candidate_name)

        def load_org_unit_candidates(self, _client, status=None):
            return [{"candidate_name": name} for name in upserted_candidates]

    monkeypatch.setattr(cmdb_service, "GraphWriter", FakeGraphWriter)

    config = AppConfig(
        input_path=str(input_dir),
        cmdb_type_files={"application": "apps.csv", "server": "servers.csv"},
        cmdb_uuid_column="id",
        cmdb_name_column="name",
        cmdb_runs_on_column="runs_on",
    )

    result = cmdb_service.sync_cmdb_to_neo4j(config, object())

    assert result.entity_count == 2
    assert result.relation_count == 1
    app = next(e for e in synced_entities if e.entity_id == "APP-1")
    assert app.entity_type == "application"
    srv = next(e for e in synced_entities if e.entity_id == "SRV-1")
    assert srv.entity_type == "server"
    assert synced_relations[0].relation_type == "RUNS_ON"
    assert synced_relations[0].target_id == "SRV-1"


def test_persist_latest_run_refresh_resolves_previously_unmatched_application(tmp_path: Path, monkeypatch) -> None:
    output_dir = tmp_path / "Output"
    output_dir.mkdir()
    write_latest_run(
        {
            "documents": [
                {
                    "source_path": "Input/03_Auftragsbearbeitung.txt",
                    "status": "processed",
                    "extracted_process": {
                        "process_name": "Auftragsbearbeitung",
                        "process_id": "proc-1",
                        "org_unit": "",
                        "roles": [],
                        "org_units": [],
                        "org_unit_candidates": [],
                        "follows_after": [],
                        "raw_applications": [{"name": "SAP ERP", "confidence": "stark"}],
                        "applications": [{"name": "SAP ERP", "confidence": "stark"}],
                        "source_path": "Input/03_Auftragsbearbeitung.txt",
                        "process_owner_candidate": "",
                    },
                    "matches": [
                        {
                            "application_name": "SAP ERP",
                            "cmdb_id": None,
                            "matched_name": None,
                            "confidence": "schwach",
                            "source": "unmatched",
                            "score": 0.0,
                        }
                    ],
                    "review_items": [
                        {
                            "process_name": "Auftragsbearbeitung",
                            "application_name": "SAP ERP",
                            "reason": "unmatched",
                        }
                    ],
                    "graph_payload": {},
                }
            ]
        },
        output_dir,
    )

    writes: list[dict] = []

    class FakeGraphWriter:
        def build_payload(self, process, matches):
            return type("Payload", (), {"process": process, "matches": matches})()

        def write_payload(self, _neo4j_client, payload) -> None:
            writes.append(
                {
                    "process_name": payload.process.process_name,
                    "match_names": [match.matched_name for match in payload.matches],
                }
            )

        def get_confirmed_links_from_neo4j(self, _client) -> list:
            return []

        def get_rejected_decisions_from_neo4j(self, _client) -> list:
            return []

        def load_org_units_from_neo4j(self, _client) -> dict:
            return {}

        def load_org_unit_aliases_from_neo4j(self, _client) -> dict:
            return {}

    monkeypatch.setattr(review_service, "resolve_runtime_output_path", lambda _path: (output_dir, False))
    monkeypatch.setattr(review_service, "get_session_neo4j_client", lambda _config: object())
    monkeypatch.setattr(review_service, "GraphWriter", FakeGraphWriter)

    refreshed_count = review_service.persist_latest_run_refresh(
        AppConfig(
            output_path=str(output_dir),
            cmdb_uuid_column="app_id",
            cmdb_name_column="application_name",
            fuzzy_threshold=0.85,
        ),
        [{"app_id": "cmdb-4711", "application_name": "SAP ERP", "entity_type": "application"}],
    )

    refreshed_run = load_latest_run(output_dir)
    refreshed_document = refreshed_run["documents"][0]

    assert refreshed_count == 1
    assert refreshed_document["matches"][0]["cmdb_id"] == "cmdb-4711"
    assert refreshed_document["matches"][0]["matched_name"] == "SAP ERP"
    assert refreshed_document["matches"][0]["confidence"] == "stark"
    assert refreshed_document["review_items"] == []
    assert writes == [{"process_name": "Auftragsbearbeitung", "match_names": ["SAP ERP"]}]

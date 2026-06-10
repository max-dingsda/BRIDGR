from pathlib import Path

from core.app_config import AppConfig
from processing.knowledge_base import KnowledgeBase
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
    knowledge_base = KnowledgeBase(
        confirmed=[],
        rejected=[],
        disambiguation=[],
        process_identity=[],
        org_units=[],
        org_unit_candidates=[],
    )

    monkeypatch.setattr(runtime_service, "get_session_neo4j_client", lambda _config: object())
    monkeypatch.setattr(runtime_service, "write_debug_log", lambda _config, event, details: debug_events.append((event, details)))
    monkeypatch.setattr(cmdb_service, "load_knowledge_base", lambda: knowledge_base)
    monkeypatch.setattr(cmdb_service, "save_knowledge_base", lambda _kb: None)
    monkeypatch.setattr(
        cmdb_service,
        "sync_cmdb_to_neo4j",
        lambda _config, _client, _kb: (
            cmdb_service.CmdbSyncResult(
                entity_count=1,
                relation_count=0,
                owner_assignment_count=0,
                owner_candidate_count=0,
                refreshed_document_count=0,
            ),
            knowledge_base,
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
            cmdb_filename="cmdb.csv",
        )
    )

    assert result.refreshed_document_count == 4
    assert refreshed_rows == [{"app_id": "cmdb-1", "application_name": "SAP ERP", "entity_type": "application"}]
    assert debug_events == [
        (
            "cmdb_sync",
            {
                "entity_count": 1,
                "relation_count": 0,
                "owner_assignment_count": 0,
                "owner_candidate_count": 0,
                "refreshed_document_count": 4,
                "cmdb_filename": "cmdb.csv",
                "cmdb_relations_filename": "",
            },
        )
    ]


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

    knowledge_base = KnowledgeBase(
        confirmed=[],
        rejected=[],
        disambiguation=[],
        process_identity=[],
        org_units=[],
        org_unit_candidates=[],
    )

    writes: list[dict] = []
    alias_sync_calls: list[bool] = []

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

    monkeypatch.setattr(review_service, "resolve_runtime_output_path", lambda _path: (output_dir, False))
    monkeypatch.setattr(review_service, "load_knowledge_base", lambda: knowledge_base)
    monkeypatch.setattr(review_service, "get_session_neo4j_client", lambda _config: object())
    monkeypatch.setattr(review_service, "sync_knowledge_base_aliases", lambda _client, _kb: alias_sync_calls.append(True))
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
    assert alias_sync_calls == [True]

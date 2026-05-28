import streamlit as st

from app import (
    ACTIVE_IMPORT_RUN_ID_STATE_KEY,
    ACTIVE_REVIEW_RUN_ID_STATE_KEY,
    CHAT_MESSAGES_STATE_KEY,
    CHAT_PENDING_APPLICATION_OPTIONS_STATE_KEY,
    CHAT_PENDING_ORIGINAL_QUESTION_STATE_KEY,
    clear_pipeline_run_tracker,
    IMPORT_RUN_FEEDBACK_STATE_KEY,
    LLM_STATUS_CONFIG_STATE_KEY,
    LLM_STATUS_STATE_KEY,
    NEO4J_CLIENT_CONFIG_STATE_KEY,
    NEO4J_CONNECTION_STATUS_CONFIG_STATE_KEY,
    NEO4J_CONNECTION_STATUS_STATE_KEY,
    NEO4J_CLIENT_STATE_KEY,
    REVIEW_RUN_FEEDBACK_STATE_KEY,
    clear_run_feedback,
    create_pipeline_run_tracker,
    ensure_query_chat_defaults,
    ensure_import_session_defaults,
    fail_pipeline_run_tracker,
    finish_pipeline_run_tracker,
    get_pipeline_run_tracker,
    get_llm_status,
    get_neo4j_connection_status,
    apply_pending_review_scope_defaults,
    request_review_last_import_scope,
    persist_org_candidate_mapping_refresh,
    persist_organization_sync,
    persist_org_unit_node,
    get_session_neo4j_client,
    reset_query_chat_state,
    reset_session_neo4j_client,
    rerun_single_document_from_artifact,
    run_query_chat_turn,
    set_run_feedback,
    update_pipeline_run_tracker,
    update_config_session_defaults,
    sync_config_session_defaults,
    write_debug_log,
)
from app_config import AppConfig
from knowledge_base import KnowledgeBase
from neo4j_utils import Neo4jConnectionError
from skills.extract.extract_base import ApplicationReference
from services import organization_service, query_service, runtime_service


def test_ensure_import_session_defaults_uses_config_mode() -> None:
    st.session_state.clear()

    ensure_import_session_defaults(AppConfig(last_run_mode="full"))

    assert st.session_state["import_run_mode"] == "full"


def test_pending_review_scope_defaults_can_be_requested_and_applied() -> None:
    st.session_state.clear()

    request_review_last_import_scope()
    apply_pending_review_scope_defaults()

    assert st.session_state["review_scope_mode"] == "Nur letzter Import"
    assert st.session_state["review_process_selection"] == []


def test_run_feedback_state_can_be_set_and_cleared() -> None:
    st.session_state.clear()

    set_run_feedback(REVIEW_RUN_FEEDBACK_STATE_KEY, "success", "ok")
    set_run_feedback(IMPORT_RUN_FEEDBACK_STATE_KEY, "error", "boom")

    assert st.session_state[REVIEW_RUN_FEEDBACK_STATE_KEY] == {"level": "success", "message": "ok"}
    assert st.session_state[IMPORT_RUN_FEEDBACK_STATE_KEY] == {"level": "error", "message": "boom"}

    clear_run_feedback(REVIEW_RUN_FEEDBACK_STATE_KEY)
    clear_run_feedback(IMPORT_RUN_FEEDBACK_STATE_KEY)

    assert REVIEW_RUN_FEEDBACK_STATE_KEY not in st.session_state
    assert IMPORT_RUN_FEEDBACK_STATE_KEY not in st.session_state


def test_pipeline_run_tracker_lifecycle() -> None:
    run_id = create_pipeline_run_tracker("done in {duration}")

    assert get_pipeline_run_tracker(run_id) == {
        "status": "running",
        "completed": 0,
        "total": 0,
        "source_path": "",
        "document_status": "",
        "duration_seconds": None,
        "error_message": "",
        "success_message_template": "done in {duration}",
    }

    update_pipeline_run_tracker(
        run_id,
        {
            "completed": 2,
            "total": 5,
            "source_path": "Input/process.txt",
            "status": "processed",
        },
    )
    assert get_pipeline_run_tracker(run_id)["completed"] == 2
    assert get_pipeline_run_tracker(run_id)["total"] == 5
    assert get_pipeline_run_tracker(run_id)["source_path"] == "Input/process.txt"
    assert get_pipeline_run_tracker(run_id)["document_status"] == "processed"

    finish_pipeline_run_tracker(run_id, 12.5)
    assert get_pipeline_run_tracker(run_id)["status"] == "success"
    assert get_pipeline_run_tracker(run_id)["duration_seconds"] == 12.5

    clear_pipeline_run_tracker(run_id)
    assert get_pipeline_run_tracker(run_id) is None


def test_pipeline_run_tracker_can_store_error_state() -> None:
    run_id = create_pipeline_run_tracker("done in {duration}")

    fail_pipeline_run_tracker(run_id, "boom")

    assert get_pipeline_run_tracker(run_id)["status"] == "error"
    assert get_pipeline_run_tracker(run_id)["error_message"] == "boom"

    clear_pipeline_run_tracker(run_id)


def test_sync_config_session_defaults_replaces_legacy_input_path() -> None:
    st.session_state.clear()
    st.session_state["config_input_path"] = "data/input"

    sync_config_session_defaults(AppConfig(input_path="Input"))

    assert st.session_state["config_input_path"] == "Input"


def test_sync_config_session_defaults_replaces_windows_legacy_input_path() -> None:
    st.session_state.clear()
    st.session_state["config_input_path"] = ".\\data\\input"

    sync_config_session_defaults(AppConfig(input_path="Input"))

    assert st.session_state["config_input_path"] == "Input"


def test_update_config_session_defaults_includes_neo4j_values() -> None:
    st.session_state.clear()

    config = AppConfig(
        neo4j_url="neo4j://127.0.0.1:7687",
        neo4j_user="neo4j",
        neo4j_password="secret",
        neo4j_database="bridgr-architecture",
    )

    update_config_session_defaults(config)

    assert st.session_state["config_neo4j_url"] == "neo4j://127.0.0.1:7687"
    assert st.session_state["config_neo4j_user"] == "neo4j"
    assert st.session_state["config_neo4j_password"] == "secret"
    assert st.session_state["config_neo4j_database"] == "bridgr-architecture"


def test_sync_config_session_defaults_refreshes_neo4j_values() -> None:
    st.session_state.clear()
    st.session_state["config_neo4j_url"] = "neo4j+s://cloud.databases.neo4j.io"
    st.session_state["config_neo4j_user"] = "cloud-user"
    st.session_state["config_neo4j_password"] = "cloud-secret"
    st.session_state["config_neo4j_database"] = "cloud-db"

    sync_config_session_defaults(
        AppConfig(
            neo4j_url="neo4j://127.0.0.1:7687",
            neo4j_user="neo4j",
            neo4j_password="local-secret",
            neo4j_database="bridgr-architecture",
        )
    )

    assert st.session_state["config_neo4j_url"] == "neo4j://127.0.0.1:7687"
    assert st.session_state["config_neo4j_user"] == "neo4j"
    assert st.session_state["config_neo4j_password"] == "local-secret"
    assert st.session_state["config_neo4j_database"] == "bridgr-architecture"


def test_get_session_neo4j_client_reuses_cached_client(monkeypatch) -> None:
    st.session_state.clear()
    created_clients = []

    class FakeClient:
        def __init__(self, config) -> None:
            self.config = config
            created_clients.append(self)

        def close(self) -> None:
            return None

    monkeypatch.setattr(runtime_service, "Neo4jClient", FakeClient)

    config = AppConfig(neo4j_password="secret")
    first_client = get_session_neo4j_client(config)
    second_client = get_session_neo4j_client(config)

    assert first_client is second_client
    assert len(created_clients) == 1


def test_get_session_neo4j_client_replaces_client_when_config_changes(monkeypatch) -> None:
    st.session_state.clear()
    closed_clients = []

    class FakeClient:
        def __init__(self, config) -> None:
            self.config = config

        def close(self) -> None:
            closed_clients.append(self.config.database)

    monkeypatch.setattr(runtime_service, "Neo4jClient", FakeClient)

    first_client = get_session_neo4j_client(AppConfig(neo4j_password="secret", neo4j_database="db-1"))
    second_client = get_session_neo4j_client(AppConfig(neo4j_password="secret", neo4j_database="db-2"))

    assert first_client is not second_client
    assert closed_clients == ["db-1"]


def test_reset_session_neo4j_client_warns_when_close_fails(monkeypatch) -> None:
    st.session_state.clear()
    warnings = []

    class FailingClient:
        def close(self) -> None:
            raise RuntimeError("close failed")

    monkeypatch.setattr(runtime_service.st, "warning", warnings.append)
    st.session_state[NEO4J_CLIENT_STATE_KEY] = FailingClient()
    st.session_state[NEO4J_CLIENT_CONFIG_STATE_KEY] = ("url", "user", "pw", "db")

    reset_session_neo4j_client(show_warning=True)

    assert warnings == ["Neo4j-Client konnte nicht sauber geschlossen werden: close failed"]
    assert NEO4J_CLIENT_STATE_KEY not in st.session_state


def test_ensure_query_chat_defaults_initializes_chat_state() -> None:
    st.session_state.clear()

    ensure_query_chat_defaults()

    assert st.session_state[CHAT_MESSAGES_STATE_KEY] == []
    assert st.session_state[CHAT_PENDING_APPLICATION_OPTIONS_STATE_KEY] == []
    assert st.session_state[CHAT_PENDING_ORIGINAL_QUESTION_STATE_KEY] == ""


def test_reset_query_chat_state_clears_messages_and_pending_clarification() -> None:
    st.session_state.clear()
    st.session_state[CHAT_MESSAGES_STATE_KEY] = [{"role": "user", "content": "test"}]
    st.session_state[CHAT_PENDING_APPLICATION_OPTIONS_STATE_KEY] = ["Mail", "Outlook"]
    st.session_state[CHAT_PENDING_ORIGINAL_QUESTION_STATE_KEY] = "Welche Mail-Anwendung?"

    reset_query_chat_state()

    assert st.session_state[CHAT_MESSAGES_STATE_KEY] == []
    assert st.session_state[CHAT_PENDING_APPLICATION_OPTIONS_STATE_KEY] == []
    assert st.session_state[CHAT_PENDING_ORIGINAL_QUESTION_STATE_KEY] == ""


def test_get_neo4j_connection_status_returns_cached_result(monkeypatch) -> None:
    st.session_state.clear()
    calls = []

    def fake_get_session_client(config):
        calls.append(config)

        class FakeClient:
            def execute_read(self, query: str) -> list[dict]:
                return [{"ok": 1}]

        return FakeClient()

    monkeypatch.setattr(runtime_service, "get_session_neo4j_client", fake_get_session_client)

    config = AppConfig(neo4j_url="neo4j://localhost:7687", neo4j_password="secret", neo4j_database="test-db")
    first_status = get_neo4j_connection_status(config)
    second_status = get_neo4j_connection_status(config)

    assert first_status == second_status
    assert calls == [config]
    assert st.session_state[NEO4J_CONNECTION_STATUS_CONFIG_STATE_KEY] == (
        config.neo4j_url,
        config.neo4j_user,
        config.neo4j_password,
        config.neo4j_database,
    )


def test_get_neo4j_connection_status_reports_missing_password() -> None:
    st.session_state.clear()

    status = get_neo4j_connection_status(AppConfig())

    assert status == (False, "Neo4j-Verbindung nicht pruefbar: Passwort fehlt.")
    assert st.session_state[NEO4J_CONNECTION_STATUS_STATE_KEY] == status


def test_get_neo4j_connection_status_reports_connection_error(monkeypatch) -> None:
    st.session_state.clear()

    def fake_get_session_client(_config):
        raise RuntimeError("boom")

    monkeypatch.setattr(runtime_service, "get_session_neo4j_client", fake_get_session_client)
    monkeypatch.setattr(runtime_service, "Neo4jConnectionError", RuntimeError)

    status = get_neo4j_connection_status(AppConfig(neo4j_password="secret"))

    assert status == (False, "Neo4j nicht erreichbar: boom")


def test_get_llm_status_returns_cached_result(monkeypatch) -> None:
    st.session_state.clear()
    calls = []

    class FakeClient:
        def __init__(self, config) -> None:
            calls.append(config)

        def list_models(self) -> list[str]:
            return ["qwen2.5-coder:7b"]

    monkeypatch.setattr(runtime_service, "OpenAICompatibleClient", FakeClient)

    config = AppConfig(llm_base_url="http://127.0.0.1:11434/v1", llm_model="qwen2.5-coder:7b")
    first_status = get_llm_status(config)
    second_status = get_llm_status(config)

    assert first_status == second_status
    assert len(calls) == 1
    assert st.session_state[LLM_STATUS_CONFIG_STATE_KEY] == (
        config.llm_base_url,
        config.llm_model,
        config.llm_api_key_env,
        config.llm_timeout_seconds,
    )


def test_get_llm_status_reports_missing_model() -> None:
    st.session_state.clear()

    status = get_llm_status(AppConfig(llm_base_url="http://127.0.0.1:11434/v1", llm_model=""))

    assert status == ("warning", "LLM-Endpoint erreichbar noch nicht geprueft: Modellname fehlt.")
    assert st.session_state[LLM_STATUS_STATE_KEY] == status


def test_get_llm_status_reports_missing_model_on_endpoint(monkeypatch) -> None:
    st.session_state.clear()

    class FakeClient:
        def __init__(self, _config) -> None:
            return None

        def list_models(self) -> list[str]:
            return ["mistral:7b", "llama3:8b"]

    monkeypatch.setattr(runtime_service, "OpenAICompatibleClient", FakeClient)

    status = get_llm_status(AppConfig(llm_base_url="http://127.0.0.1:11434/v1", llm_model="qwen2.5-coder:7b"))

    assert status == (
        "warning",
        "LLM-Endpoint erreichbar, aber Modell `qwen2.5-coder:7b` ist nicht verfuegbar. Verfuegbar: mistral:7b, llama3:8b.",
    )


def test_get_llm_status_reports_endpoint_error(monkeypatch) -> None:
    st.session_state.clear()

    class FailingClient:
        def __init__(self, _config) -> None:
            return None

        def list_models(self) -> list[str]:
            raise RuntimeError("offline")

    monkeypatch.setattr(runtime_service, "OpenAICompatibleClient", FailingClient)
    monkeypatch.setattr(runtime_service, "LlmClientError", RuntimeError)

    status = get_llm_status(AppConfig(llm_base_url="http://127.0.0.1:11434/v1", llm_model="qwen2.5-coder:7b"))

    assert status == ("error", "LLM nicht erreichbar: offline")


def test_write_debug_log_creates_jsonl_entry(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(runtime_service, "resolve_runtime_output_path", lambda _path: (tmp_path, False))

    write_debug_log(AppConfig(debug_mode=True), "query_error", {"question": "Welche Prozesse gibt es?"})

    log_content = (tmp_path / "debug.log").read_text(encoding="utf-8")
    assert '"event": "query_error"' in log_content
    assert '"question": "Welche Prozesse gibt es?"' in log_content


def test_persist_org_unit_node_merges_org_unit_node(monkeypatch) -> None:
    captured = {}

    class FakeNeo4jClient:
        def execute_write(self, query: str, parameters: dict | None = None) -> list[dict]:
            captured["query"] = query
            captured["parameters"] = parameters
            return [{"name": parameters["org_unit_name"]}]

    monkeypatch.setattr(organization_service, "get_session_neo4j_client", lambda _config: FakeNeo4jClient())

    persist_org_unit_node(AppConfig(neo4j_password="secret"), "  People   &  Culture  ")

    assert "MERGE (o:OrgEinheit {name: $org_unit_name})" in captured["query"]
    assert "RETURN o.name AS name" in captured["query"]
    assert captured["parameters"] == {"org_unit_name": "People & Culture"}


def test_persist_org_candidate_mapping_refresh_syncs_org_unit_node_without_latest_run(monkeypatch) -> None:
    synced_org_units = []

    monkeypatch.setattr(
        organization_service,
        "load_knowledge_base",
        lambda: KnowledgeBase(
            confirmed=[],
            rejected=[],
            disambiguation=[],
            process_identity=[],
            org_units=[],
            org_unit_candidates=[
                {
                    "candidate_name": "People & Culture",
                    "normalized_name": "people & culture",
                    "source_paths": ["Input/process.txt"],
                    "process_names": ["Abwesenheit bearbeiten"],
                    "role_names": [],
                    "status": "mapped",
                    "mapped_org_unit": "People & Culture",
                    "first_seen": "2026-05-27",
                    "last_seen": "2026-05-27",
                }
            ],
        ),
    )
    monkeypatch.setattr(organization_service, "persist_org_unit_node", lambda _config, name: synced_org_units.append(name))
    monkeypatch.setattr(organization_service, "resolve_runtime_output_path", lambda _path: (None, False))
    monkeypatch.setattr(organization_service, "load_latest_run", lambda _path: None)

    refreshed_count = persist_org_candidate_mapping_refresh(AppConfig(neo4j_password="secret"), "People & Culture")

    assert refreshed_count == 0
    assert synced_org_units == ["People & Culture"]


def test_rerun_single_document_from_artifact_applies_org_unit_candidate_mapping() -> None:
    knowledge_base = KnowledgeBase(
        confirmed=[],
        rejected=[],
        disambiguation=[],
        process_identity=[],
        org_units=[{"name": "QM", "created_at": "2026-05-27", "source": "manual"}],
        org_unit_candidates=[
            {
                "candidate_name": "Qualitaetsmanagement",
                "normalized_name": "qualitaetsmanagement",
                "source_paths": ["Input/process.txt"],
                "process_names": ["Pruefen"],
                "role_names": [],
                "status": "mapped",
                "mapped_org_unit": "QM",
                "first_seen": "2026-05-27",
                "last_seen": "2026-05-27",
            }
        ],
    )
    document = {
        "source_path": "Input/process.txt",
        "extracted_process": {
            "process_name": "Pruefen",
            "process_id": "proc-1",
            "org_unit": "",
            "roles": [],
            "org_units": [],
            "org_unit_candidates": ["Qualitaetsmanagement"],
            "follows_after": [],
            "raw_applications": [],
            "applications": [],
            "source_path": "Input/process.txt",
        },
        "matches": [],
        "review_items": [],
        "graph_payload": {},
        "status": "no_matches",
    }

    refreshed = rerun_single_document_from_artifact(document, AppConfig(), [], knowledge_base)

    assert refreshed["extracted_process"]["org_units"] == ["QM"]
    assert refreshed["extracted_process"]["org_unit"] == "QM"
    assert refreshed["graph_payload"]["process"]["org_units"] == ["QM"]


def test_persist_organization_sync_syncs_all_org_units_and_refreshes_latest_run(monkeypatch) -> None:
    monkeypatch.setattr(
        organization_service,
        "load_knowledge_base",
        lambda: KnowledgeBase(
            confirmed=[],
            rejected=[],
            disambiguation=[],
            process_identity=[],
            org_units=[
                {"name": "QM", "created_at": "2026-05-27", "source": "manual"},
                {"name": "Sales", "created_at": "2026-05-27", "source": "manual"},
            ],
            org_unit_candidates=[],
        ),
    )
    synced_names = []
    monkeypatch.setattr(organization_service, "persist_org_unit_node", lambda _config, name: synced_names.append(name))
    monkeypatch.setattr(organization_service, "load_cmdb_rows", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(organization_service, "persist_latest_run_refresh", lambda _config, _cmdb_rows: 3)

    synced_org_units, refreshed_documents = persist_organization_sync(AppConfig(neo4j_password="secret"))

    assert synced_names == ["QM", "Sales"]
    assert synced_org_units == 2
    assert refreshed_documents == 3


def test_run_query_chat_turn_logs_cypher_on_query_error(tmp_path, monkeypatch) -> None:
    st.session_state.clear()
    ensure_query_chat_defaults()
    monkeypatch.setattr(runtime_service, "resolve_runtime_output_path", lambda _path: (tmp_path, False))

    class FakeLlmClient:
        def __init__(self, _config) -> None:
            return None

    class FailingNeo4jClient:
        def execute_read(self, query: str):
            raise RuntimeError("bad cypher")

    monkeypatch.setattr(query_service, "OpenAICompatibleClient", FakeLlmClient)
    monkeypatch.setattr(query_service, "get_session_neo4j_client", lambda _config: FailingNeo4jClient())
    monkeypatch.setattr(query_service, "generate_cypher_from_question", lambda **_kwargs: "MATCH (n) RETURN n.name AS name UNION ALL MATCH (p) RETURN p.id AS id")
    monkeypatch.setattr(query_service, "Neo4jQueryError", RuntimeError)

    run_query_chat_turn("Wie viele Prozesse gibt es?", AppConfig(debug_mode=True, neo4j_password="secret", llm_model="qwen"))

    log_content = (tmp_path / "debug.log").read_text(encoding="utf-8")
    assert '"event": "query_error"' in log_content
    assert 'RETURN n.name AS name UNION ALL' in log_content
    assert st.session_state[CHAT_MESSAGES_STATE_KEY][-1]["cypher_query"].startswith("MATCH (n)")

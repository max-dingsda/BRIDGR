import streamlit as st

from app import (
    CHAT_MESSAGES_STATE_KEY,
    CHAT_PENDING_APPLICATION_OPTIONS_STATE_KEY,
    CHAT_PENDING_ORIGINAL_QUESTION_STATE_KEY,
    LLM_STATUS_CONFIG_STATE_KEY,
    LLM_STATUS_STATE_KEY,
    NEO4J_CLIENT_CONFIG_STATE_KEY,
    NEO4J_CONNECTION_STATUS_CONFIG_STATE_KEY,
    NEO4J_CONNECTION_STATUS_STATE_KEY,
    NEO4J_CLIENT_STATE_KEY,
    ensure_query_chat_defaults,
    ensure_import_session_defaults,
    get_llm_status,
    get_neo4j_connection_status,
    get_session_neo4j_client,
    reset_session_neo4j_client,
    run_query_chat_turn,
    update_config_session_defaults,
    sync_config_session_defaults,
    write_debug_log,
)
from app_config import AppConfig


def test_ensure_import_session_defaults_uses_config_mode() -> None:
    st.session_state.clear()

    ensure_import_session_defaults(AppConfig(last_run_mode="full"))

    assert st.session_state["import_run_mode"] == "full"


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

    monkeypatch.setattr("app.Neo4jClient", FakeClient)

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

    monkeypatch.setattr("app.Neo4jClient", FakeClient)

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

    monkeypatch.setattr("app.st.warning", warnings.append)
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


def test_get_neo4j_connection_status_returns_cached_result(monkeypatch) -> None:
    st.session_state.clear()
    calls = []

    def fake_get_session_client(config):
        calls.append(config)

        class FakeClient:
            def execute_read(self, query: str) -> list[dict]:
                return [{"ok": 1}]

        return FakeClient()

    monkeypatch.setattr("app.get_session_neo4j_client", fake_get_session_client)

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

    monkeypatch.setattr("app.get_session_neo4j_client", fake_get_session_client)
    monkeypatch.setattr("app.Neo4jConnectionError", RuntimeError)

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

    monkeypatch.setattr("app.OpenAICompatibleClient", FakeClient)

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

    monkeypatch.setattr("app.OpenAICompatibleClient", FakeClient)

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

    monkeypatch.setattr("app.OpenAICompatibleClient", FailingClient)
    monkeypatch.setattr("app.LlmClientError", RuntimeError)

    status = get_llm_status(AppConfig(llm_base_url="http://127.0.0.1:11434/v1", llm_model="qwen2.5-coder:7b"))

    assert status == ("error", "LLM nicht erreichbar: offline")


def test_write_debug_log_creates_jsonl_entry(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr("app.resolve_runtime_output_path", lambda _path: (tmp_path, False))

    write_debug_log(AppConfig(debug_mode=True), "query_error", {"question": "Welche Prozesse gibt es?"})

    log_content = (tmp_path / "debug.log").read_text(encoding="utf-8")
    assert '"event": "query_error"' in log_content
    assert '"question": "Welche Prozesse gibt es?"' in log_content


def test_run_query_chat_turn_logs_cypher_on_query_error(tmp_path, monkeypatch) -> None:
    st.session_state.clear()
    ensure_query_chat_defaults()
    monkeypatch.setattr("app.resolve_runtime_output_path", lambda _path: (tmp_path, False))

    class FakeLlmClient:
        def __init__(self, _config) -> None:
            return None

    class FailingNeo4jClient:
        def execute_read(self, query: str):
            raise RuntimeError("bad cypher")

    monkeypatch.setattr("app.OpenAICompatibleClient", FakeLlmClient)
    monkeypatch.setattr("app.get_session_neo4j_client", lambda _config: FailingNeo4jClient())
    monkeypatch.setattr("app.generate_cypher_from_question", lambda **_kwargs: "MATCH (n) RETURN n.name AS name UNION ALL MATCH (p) RETURN p.id AS id")
    monkeypatch.setattr("app.Neo4jQueryError", RuntimeError)

    run_query_chat_turn("Wie viele Prozesse gibt es?", AppConfig(debug_mode=True, neo4j_password="secret", llm_model="qwen"))

    log_content = (tmp_path / "debug.log").read_text(encoding="utf-8")
    assert '"event": "query_error"' in log_content
    assert 'RETURN n.name AS name UNION ALL' in log_content
    assert st.session_state[CHAT_MESSAGES_STATE_KEY][-1]["cypher_query"].startswith("MATCH (n)")

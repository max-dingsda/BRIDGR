import streamlit as st

from app import (
    CHAT_MESSAGES_STATE_KEY,
    CHAT_PENDING_APPLICATION_OPTIONS_STATE_KEY,
    CHAT_PENDING_ORIGINAL_QUESTION_STATE_KEY,
    NEO4J_CLIENT_CONFIG_STATE_KEY,
    NEO4J_CLIENT_STATE_KEY,
    ensure_query_chat_defaults,
    ensure_import_session_defaults,
    get_session_neo4j_client,
    reset_session_neo4j_client,
    sync_config_session_defaults,
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

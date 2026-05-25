import streamlit as st

from app import ensure_import_session_defaults, sync_config_session_defaults
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

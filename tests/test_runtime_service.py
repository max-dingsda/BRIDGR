import streamlit as st

from core.app_config import AppConfig
from services.runtime_service import update_config_session_defaults


def test_update_config_session_defaults_sets_paths() -> None:
    st.session_state.clear()
    config = AppConfig(
        input_path="Input",
        output_path="Output",
    )

    update_config_session_defaults(config)

    assert st.session_state["config_input_path"] == "Input"
    assert st.session_state["config_output_path"] == "Output"

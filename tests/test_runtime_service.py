import streamlit as st
from pathlib import Path

from app_config import AppConfig
from services.runtime_service import ensure_active_cmdb_selection


def test_ensure_active_cmdb_selection_uses_separate_entity_and_relation_options(tmp_path) -> None:
    st.session_state.clear()
    config = AppConfig(
        cmdb_filename="missing_entities.csv",
        cmdb_relations_filename="missing_relations.csv",
    )

    ensure_active_cmdb_selection(
        config,
        [Path("nested/cmdb_entities.csv")],
        [Path("nested/cmdb_relations.csv")],
    )

    assert st.session_state["active_cmdb_filename"] == "nested/cmdb_entities.csv"
    assert st.session_state["active_cmdb_relations_filename"] == "nested/cmdb_relations.csv"


def test_ensure_active_cmdb_selection_clears_missing_relation_selection(tmp_path) -> None:
    st.session_state.clear()
    config = AppConfig(
        cmdb_filename="cmdb_entities.csv",
        cmdb_relations_filename="cmdb_relations.csv",
    )

    ensure_active_cmdb_selection(
        config,
        [Path("cmdb_entities.csv")],
        [],
    )

    assert st.session_state["active_cmdb_filename"] == "cmdb_entities.csv"
    assert st.session_state["active_cmdb_relations_filename"] == ""

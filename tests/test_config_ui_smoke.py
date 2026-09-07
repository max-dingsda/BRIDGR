from pathlib import Path

import pytest

from core.app_config import AppConfig, save_config


@pytest.mark.parametrize("locale", ["de", "en"])
def test_config_renders_separate_chat_credentials_without_exposing_passwords(tmp_path, monkeypatch, locale):
    from streamlit.testing.v1 import AppTest
    from streamlit.proto.TextInput_pb2 import TextInput
    from ui import config_tab

    path = tmp_path / "config.json"
    save_config(AppConfig(neo4j_user="writer", neo4j_password="writer-secret",
                         neo4j_chat_user="reader", neo4j_chat_password="reader-secret",
                         output_path=str(tmp_path), ui_locale=locale), path)
    monkeypatch.setattr(config_tab, "get_neo4j_connection_status", lambda *args, **kwargs: (False, "Offline test"))
    monkeypatch.setattr(config_tab, "get_llm_status", lambda *args, **kwargs: ("warning", "Offline test"))
    app = AppTest.from_string(
        "import streamlit as st\nfrom pathlib import Path\n"
        "from ui.config_tab import render_config_tab\n"
        f"st.session_state['bridgr_locale'] = {locale!r}\n"
        f"render_config_tab(Path({str(path)!r}))\n"
    ).run(timeout=15)
    assert not app.exception
    inputs = {entry.value: entry for entry in app.text_input}
    assert inputs["reader-secret"].proto.type == TextInput.PASSWORD
    assert inputs["writer-secret"].proto.type == TextInput.PASSWORD
    assert "reader" in inputs
    displayed = " ".join(str(entry.value) for entry in app.json)
    assert "reader-secret" not in displayed and "writer-secret" not in displayed


def test_organization_ui_consumes_canonical_process_id_contract():
    from streamlit.testing.v1 import AppTest
    app = AppTest.from_string('''
from core.app_config import AppConfig
from ui.organization_tab import _render_process_owner_section, _render_process_manager_for_org_unit
rows = [
    {"process_id": "p1", "process": "Order", "owner": None},
    {"process_id": "p2", "process": "Invoice", "owner": "Finance"},
]
_render_process_owner_section(AppConfig(), [{"name": "Finance"}], rows)
_render_process_manager_for_org_unit(AppConfig(), "Finance", "finance", rows)
''').run()
    assert not app.exception
    assert len(app.multiselect) == 2
    assert app.multiselect[1].value == ["p2"]

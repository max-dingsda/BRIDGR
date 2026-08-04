from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
import os

import streamlit as st

from core.app_config import AppConfig, load_config, normalize_run_mode, save_config
from ui.dialog_utils import pick_directory
from core.llm_client import LlmClientConfig, LlmClientError, OpenAICompatibleClient
from services.runtime_service import (
    build_neo4j_client_key,
    ensure_config_session_defaults,
    get_llm_status,
    get_session_neo4j_client,
    get_neo4j_connection_status,
    reset_session_neo4j_client,
    sync_config_session_defaults,
    update_config_session_defaults,
    write_debug_log,
)
from services.snapshot_service import SnapshotError, list_snapshots, restore_snapshot
from ui.layout import render_page_header

_OPENAI_PRESET = {
    "llm_base_url": "https://api.openai.com/v1",
    "llm_model": "gpt-4o",
    "llm_api_key_env": "OPENAI_API_KEY",
}

_OLLAMA_PRESET = {
    "llm_base_url": "http://127.0.0.1:11434/v1",
    "llm_model": "gemma4:12b",
    "llm_api_key_env": "",
}


def _apply_llm_preset(preset: dict[str, str]) -> None:
    st.session_state["config_llm_base_url"] = preset["llm_base_url"]
    st.session_state["config_llm_model"] = preset["llm_model"]
    st.session_state["config_llm_api_key_env"] = preset["llm_api_key_env"]


def render_path_picker_controls() -> None:
    st.markdown("**Pfade auswählen**")
    input_column, output_column = st.columns(2)

    if input_column.button("Eingabe-Ordner wählen", width="stretch"):
        selected_path = pick_directory(st.session_state["config_input_path"])
        if selected_path:
            st.session_state["config_input_path"] = selected_path
            st.rerun()

    if output_column.button("Ausgabe-Ordner wählen", width="stretch"):
        selected_path = pick_directory(st.session_state["config_output_path"])
        if selected_path:
            st.session_state["config_output_path"] = selected_path
            st.rerun()


def render_config_tab(config_path: Path) -> None:
    if st.session_state.pop("snapshot_restore_reset_pending", False):
        st.session_state["snapshot_restore_confirmed"] = False
    restore_feedback = st.session_state.pop("snapshot_restore_feedback", None)

    render_page_header(
        "Konfiguration",
        "Pflegen Sie Laufzeitparameter, Pfade sowie LLM- und Neo4j-Einstellungen für den aktuellen Workspace.",
        "Einstellungen",
    )
    config = load_config(config_path)
    ensure_config_session_defaults(config)
    sync_config_session_defaults(config)

    render_path_picker_controls()

    st.markdown("#### LLM-Presets")
    preset_columns = st.columns(2)
    if preset_columns[0].button("OpenAI", width="stretch"):
        _apply_llm_preset(_OPENAI_PRESET)
        st.rerun()
    if preset_columns[1].button("Ollama", width="stretch"):
        _apply_llm_preset(_OLLAMA_PRESET)
        st.rerun()

    with st.form("config_form"):
        st.markdown("#### LLM")
        llm_base_url = st.text_input("LLM-Endpunkt", value=st.session_state["config_llm_base_url"])
        llm_model = st.text_input("LLM-Modell", value=st.session_state["config_llm_model"])
        llm_api_key_env = st.text_input("API-Schlüssel (Umgebungsvariable)", value=st.session_state["config_llm_api_key_env"])
        llm_context_window = st.number_input("Kontextfenster", min_value=1, value=st.session_state["config_llm_context_window"])
        llm_timeout_seconds = st.number_input("LLM-Timeout (Sekunden)", min_value=1, value=int(config.llm_timeout_seconds))
        _chat_mode_options = ["prompt-only", "tool-use"]
        _chat_mode_index = _chat_mode_options.index(config.chat_mode) if config.chat_mode in _chat_mode_options else 0
        chat_mode = st.selectbox("Chat-Modus", _chat_mode_options, index=_chat_mode_index)
        st.caption(
            "`prompt-only`: Cypher als Textblock (kompatibel mit lokalen Modellen ohne Function-Calling). "
            "`tool-use`: Formales Function-Calling (erfordert Backend-Unterstützung)."
        )

        st.divider()
        st.markdown("#### Neo4j")
        neo4j_url = st.text_input("Neo4j-URL", value=st.session_state["config_neo4j_url"])
        if os.getenv("NEO4J_URI"):
            st.caption("NEO4J_URI wurde aus der Umgebung geladen. Der aktuell wirksame Wert ist im Feld sichtbar und kann hier dauerhaft überschrieben werden.")
        neo4j_user = st.text_input("Neo4j-Benutzer", value=st.session_state["config_neo4j_user"])
        if os.getenv("NEO4J_USERNAME"):
            st.caption("NEO4J_USERNAME wurde aus der Umgebung geladen. Der aktuell wirksame Wert ist im Feld sichtbar und kann hier dauerhaft überschrieben werden.")
        neo4j_password = st.text_input("Neo4j-Passwort", value=st.session_state["config_neo4j_password"], type="password")
        if os.getenv("NEO4J_PASSWORD"):
            st.caption("NEO4J_PASSWORD wurde aus der Umgebung geladen. Der aktuell wirksame Wert bleibt beim Speichern erhalten, bis Sie ihn hier explizit ändern.")
        neo4j_database = st.text_input("Neo4j-Datenbank", value=st.session_state["config_neo4j_database"])
        if os.getenv("NEO4J_DATABASE"):
            st.caption("NEO4J_DATABASE wurde aus der Umgebung geladen. Der aktuell wirksame Wert ist im Feld sichtbar und kann hier dauerhaft überschrieben werden.")

        st.divider()
        st.markdown("#### Datei-Pfade")
        input_path = st.text_input("Eingabepfad", value=st.session_state["config_input_path"])
        output_path = st.text_input("Ausgabepfad", value=st.session_state["config_output_path"])

        st.divider()
        st.markdown("#### CMDB-Spaltenmapping")
        cmdb_uuid_column = st.text_input("ID-Spalte", value=config.cmdb_uuid_column)
        cmdb_name_column = st.text_input("Namensspalte", value=config.cmdb_name_column)
        cmdb_server_type_column = st.text_input("Servertyp-Spalte", value=config.cmdb_server_type_column)
        cmdb_owner_name_column = st.text_input("Eigentümer-Spalte", value=config.cmdb_owner_name_column)
        cmdb_runs_on_column = st.text_input("Spalte 'läuft auf' (Server-IDs)", value=config.cmdb_runs_on_column)
        cmdb_uses_interfaces_column = st.text_input("Spalte 'nutzt Schnittstellen' (Schnittstellen-IDs)", value=config.cmdb_uses_interfaces_column)
        cmdb_multivalue_separator = st.text_input("Mehrwert-Trennzeichen", value=config.cmdb_multivalue_separator)

        st.divider()
        st.markdown("#### Import & Matching")
        fuzzy_threshold = st.number_input("Fuzzy-Schwellenwert", min_value=0.0, max_value=1.0, value=float(config.fuzzy_threshold), step=0.01)
        last_run_mode = st.selectbox("Standard-Importmodus", ["full", "partial"], index=["full", "partial"].index(normalize_run_mode(config.last_run_mode)))
        debug_mode = st.checkbox("Debug-Modus", value=config.debug_mode)
        snapshot_retention_count = st.number_input(
            "Aufbewahrung Snapshots",
            min_value=1,
            max_value=100,
            value=int(config.snapshot_retention_count),
            help="Anzahl gültiger Graph-Snapshots, die nach erfolgreichen Schreiboperationen erhalten bleibt.",
        )

        submitted = st.form_submit_button("Konfiguration speichern")

    if submitted:
        previous_client_key = build_neo4j_client_key(config)
        updated_config = AppConfig(
            llm_base_url=llm_base_url,
            llm_model=llm_model,
            llm_api_key_env=llm_api_key_env,
            llm_context_window=int(llm_context_window),
            llm_timeout_seconds=int(llm_timeout_seconds),
            neo4j_url=neo4j_url.strip(),
            neo4j_user=neo4j_user.strip(),
            neo4j_password=neo4j_password.strip(),
            neo4j_database=neo4j_database.strip(),
            fuzzy_threshold=float(fuzzy_threshold),
            cmdb_uuid_column=cmdb_uuid_column,
            cmdb_name_column=cmdb_name_column,
            cmdb_server_type_column=cmdb_server_type_column,
            cmdb_owner_name_column=cmdb_owner_name_column,
            cmdb_multivalue_separator=cmdb_multivalue_separator or "|",
            cmdb_type_files=config.cmdb_type_files,
            cmdb_runs_on_column=cmdb_runs_on_column or "runs_on",
            cmdb_uses_interfaces_column=cmdb_uses_interfaces_column or "uses_interfaces",
            input_path=input_path,
            output_path=output_path,
            last_run_mode=last_run_mode,
            chat_mode=chat_mode,
            debug_mode=debug_mode,
            snapshot_retention_count=int(snapshot_retention_count),
        )
        save_config(updated_config, config_path)
        if build_neo4j_client_key(updated_config) != previous_client_key:
            reset_session_neo4j_client(show_warning=True)
        update_config_session_defaults(updated_config)
        st.success("Konfiguration gespeichert.")

    refresh_neo4j_status = st.button("Neo4j-Verbindung neu prüfen")
    connection_ok, connection_message = get_neo4j_connection_status(load_config(config_path), force_refresh=refresh_neo4j_status)
    if connection_ok:
        st.success(connection_message)
    else:
        st.error(connection_message)

    if st.button("Modelle aktualisieren"):
        client = OpenAICompatibleClient(
            LlmClientConfig(
                base_url=st.session_state["config_llm_base_url"],
                model=st.session_state["config_llm_model"],
                api_key_env=st.session_state["config_llm_api_key_env"],
                debug_logger=lambda event, details: write_debug_log(load_config(config_path), event, details),
            )
        )
        try:
            models = client.list_models()
        except LlmClientError as exc:
            st.error(str(exc))
        else:
            st.write({"Verfügbare Modelle": models})

    refresh_llm_status = st.button("LLM-Verbindung neu prüfen")
    llm_status_level, llm_status_message = get_llm_status(load_config(config_path), force_refresh=refresh_llm_status)
    if llm_status_level == "success":
        st.success(llm_status_message)
    elif llm_status_level == "warning":
        st.warning(llm_status_message)
    else:
        st.error(llm_status_message)

    st.divider()
    st.markdown("#### Sicherung und Wiederherstellung")
    if restore_feedback:
        st.success(restore_feedback)
    snapshots = list_snapshots(load_config(config_path))
    if snapshots:
        st.dataframe(
            [
                {
                    "Snapshot": snapshot.snapshot_id,
                    "Zeitpunkt": snapshot.created_at,
                    "Auslöser": snapshot.trigger,
                    "Operation": snapshot.operation,
                    "Knoten": snapshot.node_count,
                    "Beziehungen": snapshot.relationship_count,
                    "Status": "gültig" if snapshot.valid else f"ungültig: {snapshot.error}",
                }
                for snapshot in snapshots
            ],
            width="stretch",
            hide_index=True,
        )
        valid_snapshots = [snapshot for snapshot in snapshots if snapshot.valid]
        if valid_snapshots:
            st.warning(
                "Die Wiederherstellung ersetzt den gesamten Inhalt der konfigurierten Neo4j-Datenbank. "
                "Verwenden Sie dafür ausschließlich eine dedizierte BRIDGR-Datenbank."
            )
            selected_snapshot_id = st.selectbox(
                "Snapshot für Wiederherstellung",
                [snapshot.snapshot_id for snapshot in valid_snapshots],
            )
            restore_confirmed = st.checkbox(
                "Ich bestätige die Wiederherstellung des vollständigen BRIDGR-Graphen.",
                key="snapshot_restore_confirmed",
            )
            if st.button("Snapshot wiederherstellen", type="primary", disabled=not restore_confirmed):
                active_config = load_config(config_path)
                try:
                    restored = restore_snapshot(
                        active_config,
                        get_session_neo4j_client(active_config),
                        selected_snapshot_id,
                    )
                except SnapshotError as exc:
                    st.error(f"Wiederherstellung fehlgeschlagen: {exc}")
                else:
                    st.session_state["snapshot_restore_feedback"] = (
                        f"Snapshot {restored.snapshot_id} wurde erfolgreich wiederhergestellt "
                        f"({restored.node_count} Knoten, {restored.relationship_count} Beziehungen). "
                        "Vor der Wiederherstellung wurde ein Sicherheits-Snapshot des bisherigen Zustands angelegt."
                    )
                    st.session_state["snapshot_restore_reset_pending"] = True
                    st.rerun()
    else:
        st.info("Noch keine Snapshots vorhanden. Sie werden vor Import, CMDB-Synchronisation und Merge automatisch erstellt.")

    st.caption("Aktuelle Konfiguration")
    st.json(asdict(load_config(config_path)))

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
import os

import streamlit as st

from core.app_config import AppConfig, load_config, normalize_run_mode, resolve_project_path, resolve_runtime_output_path, save_config
from processing.bpmn_transformer import BpmnTransformError, transform_bpmn_for_import
from processing.cmdb import CmdbLoadError, validate_cmdb_entity_file
from ui.dialog_utils import pick_directory, pick_file
from processing.import_utils import describe_cmdb_file, list_cmdb_candidate_files, list_process_files
from core.llm_client import LlmClientConfig, LlmClientError, OpenAICompatibleClient
from core.neo4j_utils import Neo4jConnectionError, Neo4jQueryError
from services.cmdb_service import persist_cmdb_sync
from services.import_service import build_import_completion_message, finalize_import_artifacts
from services.review_service import clear_knowledge_base_and_refresh
from services.runtime_service import (
    IMPORT_RUN_FEEDBACK_STATE_KEY,
    build_neo4j_client_key,
    ensure_config_session_defaults,
    ensure_import_session_defaults,
    get_llm_status,
    get_neo4j_connection_status,
    request_review_last_import_scope,
    render_run_feedback,
    reset_session_neo4j_client,
    run_pipeline_with_live_feedback,
    set_run_feedback,
    sync_config_session_defaults,
    update_config_session_defaults,
    write_debug_log,
)

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


def render_import_section(config: AppConfig) -> None:
    st.markdown("**Import**")
    st.caption(
        "Der Import verarbeitet neue Prozessdateien aus der Inbox `Input/`. "
        "Nach einem erfolgreichen Lauf werden verarbeitete Prozessdateien archiviert und aus der Inbox entfernt."
    )
    ensure_import_session_defaults(config)
    render_run_feedback(IMPORT_RUN_FEEDBACK_STATE_KEY)

    input_dir = resolve_project_path(config.input_path)
    runtime_output_path, used_output_fallback = resolve_runtime_output_path(config.output_path)
    current_process_files = list_process_files(input_dir)
    process_file_labels = {path.relative_to(input_dir).as_posix(): path for path in current_process_files}
    available_bpmn_files = [path for path in current_process_files if path.suffix.lower() in {".bpmn", ".xml"}]

    mode_column, transform_column, run_column = st.columns([1, 1, 1])
    with mode_column:
        selected_run_mode = st.selectbox("Importmodus", options=["full", "partial"], key="import_run_mode")
        st.caption(
            "`full` verarbeitet alle Prozessdateien im aktuellen Eingabepfad. "
            "`partial` verarbeitet nur die hier explizit ausgewählten Dateien."
        )
        st.info(
            "Legen Sie neue Prozessdateien und die aktive CMDB-Datei direkt im aktuellen Eingabepfad ab. "
            "BRIDGR verwendet den Inbox-Bestand und bietet hier keinen separaten Upload-Pfad mehr an."
        )
        selected_import_filenames = []
        if selected_run_mode == "partial":
            selected_import_filenames = st.multiselect(
                "Dateien für Teilimport",
                options=list(process_file_labels.keys()),
                default=[],
                key="import_process_selection",
            )
        else:
            st.info("Im Modus `full` werden alle aktuell gefundenen Prozessdateien im Eingabepfad verarbeitet.")

    with transform_column:
        st.caption("Optional: Reduziert große BPMN/XML-Dateien vor dem eigentlichen Import auf kompakte Prozessdateien.")
        selected_transform_filenames = st.multiselect(
            "BPMN für Transformation",
            options=[path.relative_to(input_dir).as_posix() for path in available_bpmn_files],
            default=[],
            key="transform_bpmn_selection",
        )
        if st.button("BPMN transformieren", width="stretch"):
            if not available_bpmn_files:
                st.info("Keine BPMN/XML-Dateien im aktuellen Eingabepfad gefunden.")
            elif not selected_transform_filenames:
                st.info("Bitte wählen Sie mindestens eine BPMN/XML-Datei für die Transformation aus.")
            else:
                selected_bpmn_files = [process_file_labels[label] for label in selected_transform_filenames]
                transformed_paths: list[str] = []
                try:
                    for bpmn_file in selected_bpmn_files:
                        transformed_batch = transform_bpmn_for_import(bpmn_file, input_dir)
                        transformed_paths.extend(str(path) for path in transformed_batch)
                except BpmnTransformError as exc:
                    st.error(str(exc))
                else:
                    st.success(
                        f"{len(transformed_paths)} Transform-Datei(en) erzeugt. Die neuen Dateien liegen unter `{input_dir / 'transformed'}`."
                    )
                    st.write(transformed_paths)

    with run_column:
        st.caption("Startet den eigentlichen Import nach Neo4j. Starke bzw. freigegebene Links werden geschrieben.")
        if st.button("Pipeline starten", width="stretch"):
            if not config.llm_model:
                st.warning("Bitte zuerst ein LLM-Modell konfigurieren.")
            else:
                selected_input_paths = [process_file_labels[label] for label in selected_import_filenames]
                pipeline_input_paths = None if selected_run_mode == "full" else selected_input_paths
                if selected_run_mode == "partial" and not pipeline_input_paths:
                    st.info("Bitte wählen Sie mindestens eine Prozessdatei für den Teilimport aus.")
                    return

                runtime_config = AppConfig(
                    **{
                        **asdict(config),
                        "last_run_mode": normalize_run_mode(selected_run_mode),
                    }
                )
                run_result, duration = run_pipeline_with_live_feedback(
                    runtime_config,
                    feedback_state_key=IMPORT_RUN_FEEDBACK_STATE_KEY,
                    success_message_template="Importlauf abgeschlossen in {duration}. Ergebnisse liegen im Ausgabe-Ordner.",
                    input_paths=pipeline_input_paths,
                )
                if run_result is None or duration is None:
                    return

                processed_source_paths = [
                    document.source_path
                    for document in run_result.documents
                    if document.status != "skipped_unchanged"
                ]
                archive_path, archived_display_paths = finalize_import_artifacts(
                    runtime_config,
                    runtime_output_path,
                    input_dir,
                    runtime_config.last_run_mode,
                    processed_source_paths,
                )
                request_review_last_import_scope()
                message = build_import_completion_message(
                    duration,
                    runtime_config.last_run_mode,
                    archive_path,
                    archived_display_paths,
                )
                set_run_feedback(IMPORT_RUN_FEEDBACK_STATE_KEY, "success", message)
                st.rerun()

    st.caption(f"Aktueller Eingabepfad: `{input_dir}`")
    if current_process_files:
        st.dataframe(
            [{"Datei": path.relative_to(input_dir).as_posix()} for path in current_process_files],
            width="stretch",
        )
    else:
        st.info("Noch keine Prozessdateien im Eingabepfad vorhanden.")

    st.caption("CMDB-Typ-Dateien")
    available_csv_files = [describe_cmdb_file(path, input_dir) for path in list_cmdb_candidate_files(input_dir, config.cmdb_uuid_column, config.cmdb_name_column)]
    if available_csv_files:
        current_type_files = config.cmdb_type_files
        file_options = [""] + available_csv_files

        app_col, srv_col, if_col = st.columns(3)
        with app_col:
            app_default = current_type_files.get("application", "")
            app_idx = file_options.index(app_default) if app_default in file_options else 0
            selected_app_file = st.selectbox("Anwendungen", options=file_options, index=app_idx,
                                              format_func=lambda v: v or "(keine)", key="active_cmdb_application_file")
        with srv_col:
            srv_default = current_type_files.get("server", "")
            srv_idx = file_options.index(srv_default) if srv_default in file_options else 0
            selected_srv_file = st.selectbox("Server", options=file_options, index=srv_idx,
                                              format_func=lambda v: v or "(keine)", key="active_cmdb_server_file")
        with if_col:
            if_default = current_type_files.get("interface", "")
            if_idx = file_options.index(if_default) if if_default in file_options else 0
            selected_if_file = st.selectbox("Schnittstellen", options=file_options, index=if_idx,
                                             format_func=lambda v: v or "(keine)", key="active_cmdb_interface_file")

        def _build_type_files_from_selection() -> dict[str, str]:
            return {k: v for k, v in {
                "application": selected_app_file,
                "server": selected_srv_file,
                "interface": selected_if_file,
            }.items() if v}

        action_col_save, action_col_sync = st.columns(2)
        with action_col_save:
            if st.button("Typ-Dateien übernehmen", width="stretch"):
                new_type_files = _build_type_files_from_selection()
                updated_config = AppConfig(**{**asdict(config), "cmdb_type_files": new_type_files})
                save_config(updated_config)
                update_config_session_defaults(updated_config)
                label = ", ".join(f"{k}={v}" for k, v in new_type_files.items()) if new_type_files else "(keine)"
                st.success(f"CMDB-Typ-Dateien gespeichert: {label}.")
                st.rerun()

        with action_col_sync:
            if st.button("CMDB nach Neo4j synchronisieren", width="stretch"):
                new_type_files = _build_type_files_from_selection()
                sync_config = AppConfig(**{**asdict(config), "cmdb_type_files": new_type_files})
                save_config(sync_config)
                update_config_session_defaults(sync_config)
                try:
                    result = persist_cmdb_sync(sync_config)
                except (CmdbLoadError, Neo4jConnectionError, Neo4jQueryError) as exc:
                    st.error(f"CMDB konnte nicht nach Neo4j synchronisiert werden: {exc}")
                else:
                    st.success(
                        f"CMDB synchronisiert: {result.entity_count} Eintrag/Einträge, {result.relation_count} Relation(en), "
                        f"{result.owner_assignment_count} Eigentümer-Zuordnung(en), "
                        f"{result.refreshed_document_count} Dokument(e) im letzten Lauf neu bewertet."
                    )
                st.rerun()

        for type_label, file_name in _build_type_files_from_selection().items():
            issues = validate_cmdb_entity_file(
                input_dir / file_name,
                id_column=config.cmdb_uuid_column,
                name_column=config.cmdb_name_column,
                server_type_column=config.cmdb_server_type_column,
                owner_name_column=config.cmdb_owner_name_column,
            )
            if issues:
                st.error(f"CMDB-Strukturfehler in `{file_name}` ({type_label}):")
                st.dataframe(
                    [{"Meldung": f"Zeile {issue.line_number} {issue.message}"} for issue in issues],
                    width="stretch",
                    hide_index=True,
                )
    else:
        st.info("Noch keine CMDB-Dateien im Eingabepfad vorhanden.")

    st.caption(f"Konfigurierter Ausgabepfad: `{resolve_project_path(config.output_path)}`")
    if used_output_fallback:
        st.warning(f"Der konfigurierte Ausgabepfad ist aktuell nicht beschreibbar. Artefakte werden nach `{runtime_output_path}` geschrieben.")
    else:
        st.write(str(runtime_output_path))


def render_knowledge_base_section(config: AppConfig) -> None:
    st.caption("Hilft beim Zurücksetzen von Testentscheidungen ohne manuelles Bearbeiten von `knowledge_base/kb.json`.")
    action_columns = st.columns(3)

    if action_columns[0].button("Wissensbasis komplett leeren", key="kb-clear-all", width="stretch"):
        level, message = clear_knowledge_base_and_refresh(
            config,
            sections={"confirmed", "rejected", "disambiguation", "process_identity"},
            success_message="Die gesamte Wissensbasis wurde geleert.",
        )
        getattr(st, level)(message)
        st.rerun()

    if action_columns[1].button("Nur Bestätigungen leeren", key="kb-clear-confirmed", width="stretch"):
        level, message = clear_knowledge_base_and_refresh(
            config,
            sections={"confirmed"},
            success_message="Die bestätigten Einträge wurden geleert.",
        )
        getattr(st, level)(message)
        st.rerun()

    if action_columns[2].button("Nur Ablehnungen leeren", key="kb-clear-rejected", width="stretch"):
        level, message = clear_knowledge_base_and_refresh(
            config,
            sections={"rejected"},
            success_message="Die abgelehnten Einträge wurden geleert.",
        )
        getattr(st, level)(message)
        st.rerun()


def render_config_tab(config_path: Path) -> None:
    st.subheader("Konfiguration")
    config = load_config(config_path)
    ensure_config_session_defaults(config)
    sync_config_session_defaults(config)

    with st.expander("Import", expanded=False):
        render_import_section(config)

    with st.expander("Einstellungen", expanded=False):
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

        st.caption("Aktuelle Konfiguration")
        st.json(asdict(load_config(config_path)))

    with st.expander("Wissensbasis", expanded=False):
        render_knowledge_base_section(config)

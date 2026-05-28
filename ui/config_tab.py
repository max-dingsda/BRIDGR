from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
import os

import streamlit as st

from app_config import AppConfig, load_config, normalize_run_mode, resolve_project_path, resolve_runtime_output_path, save_config
from bpmn_transformer import BpmnTransformError, transform_bpmn_for_import
from dialog_utils import pick_directory, pick_file
from import_utils import list_cmdb_files, list_process_files
from llm_client import LlmClientConfig, LlmClientError, OpenAICompatibleClient
from services.import_service import build_import_completion_message, finalize_import_artifacts
from services.runtime_service import (
    IMPORT_RUN_FEEDBACK_STATE_KEY,
    build_neo4j_client_key,
    ensure_active_cmdb_selection,
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
def render_path_picker_controls() -> None:
    st.markdown("**Pfade auswaehlen**")
    input_column, cmdb_column, relations_column, output_column = st.columns(4)

    if input_column.button("Input-Ordner waehlen", width="stretch"):
        selected_path = pick_directory(st.session_state["config_input_path"])
        if selected_path:
            st.session_state["config_input_path"] = selected_path
            st.rerun()

    if cmdb_column.button("CMDB-Datei im Input-Ordner waehlen", width="stretch"):
        selected_path = pick_file(st.session_state["config_input_path"], [("CSV files", "*.csv"), ("All files", "*.*")])
        if selected_path:
            selected_file = Path(selected_path)
            st.session_state["config_input_path"] = str(selected_file.parent)
            st.session_state["config_cmdb_filename"] = selected_file.name
            st.rerun()

    if relations_column.button("CMDB-Relationsdatei waehlen", width="stretch"):
        selected_path = pick_file(st.session_state["config_input_path"], [("CSV files", "*.csv"), ("All files", "*.*")])
        if selected_path:
            selected_file = Path(selected_path)
            st.session_state["config_input_path"] = str(selected_file.parent)
            st.session_state["config_cmdb_relations_filename"] = selected_file.name
            st.rerun()

    if output_column.button("Output-Ordner waehlen", width="stretch"):
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
            "`full` verarbeitet alle Prozessdateien im aktuellen Input-Pfad. "
            "`partial` verarbeitet nur die hier explizit ausgewaehlten Dateien."
        )
        st.info(
            "Legen Sie neue Prozessdateien und die aktive CMDB-Datei direkt im aktuellen Input-Pfad ab. "
            "BRIDGR verwendet den Inbox-Bestand und bietet hier keinen separaten Upload-Pfad mehr an."
        )
        selected_import_filenames = []
        if selected_run_mode == "partial":
            selected_import_filenames = st.multiselect(
                "Dateien fuer Teilimport",
                options=list(process_file_labels.keys()),
                default=[],
                key="import_process_selection",
            )
        else:
            st.info("Im Modus `full` werden alle aktuell gefundenen Prozessdateien im Input-Pfad verarbeitet.")

    with transform_column:
        st.caption("Optional: Reduziert grosse BPMN/XML-Dateien vor dem eigentlichen Import auf kompakte Prozessdateien.")
        selected_transform_filenames = st.multiselect(
            "BPMN fuer Transformation",
            options=[path.relative_to(input_dir).as_posix() for path in available_bpmn_files],
            default=[],
            key="transform_bpmn_selection",
        )
        if st.button("BPMN transformieren", width="stretch"):
            if not available_bpmn_files:
                st.info("Keine BPMN/XML-Dateien im aktuellen Input-Pfad gefunden.")
            elif not selected_transform_filenames:
                st.info("Bitte waehlen Sie mindestens eine BPMN/XML-Datei fuer die Transformation aus.")
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
                    st.info("Bitte waehlen Sie mindestens eine Prozessdatei fuer den Teilimport aus.")
                    return

                runtime_config = AppConfig(
                    **{
                        **asdict(config),
                        "last_run_mode": normalize_run_mode(selected_run_mode),
                        "cmdb_filename": st.session_state.get("active_cmdb_filename", config.cmdb_filename),
                    }
                )
                run_result, duration = run_pipeline_with_live_feedback(
                    runtime_config,
                    feedback_state_key=IMPORT_RUN_FEEDBACK_STATE_KEY,
                    success_message_template="Importlauf abgeschlossen in {duration}. Ergebnisse liegen im Output-Ordner.",
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

    current_cmdb_files = list_cmdb_files(input_dir)
    ensure_active_cmdb_selection(config, current_cmdb_files)

    st.caption(f"Aktueller Input-Pfad: `{input_dir}`")
    if current_process_files:
        st.dataframe(
            [{"Datei": path.relative_to(input_dir).as_posix()} for path in current_process_files],
            width="stretch",
        )
    else:
        st.info("Noch keine Prozessdateien im Input-Pfad vorhanden.")

    st.caption("Verfuegbare CMDB-Dateien im Input-Pfad")
    if current_cmdb_files:
        available_cmdb_filenames = [path.name for path in current_cmdb_files]
        cmdb_config_column, relations_config_column = st.columns(2)
        with cmdb_config_column:
            selected_cmdb_filename = st.selectbox("Aktive CMDB-Entities-Datei", options=available_cmdb_filenames, key="active_cmdb_filename")
        with relations_config_column:
            selected_relations_filename = st.selectbox(
                "Aktive CMDB-Relationsdatei",
                options=[""] + available_cmdb_filenames,
                key="active_cmdb_relations_filename",
                format_func=lambda value: value or "(keine)",
            )
        if st.button("Aktive CMDB-Dateien uebernehmen", width="stretch"):
            updated_config = AppConfig(
                **{
                    **asdict(config),
                    "cmdb_filename": selected_cmdb_filename,
                    "cmdb_relations_filename": selected_relations_filename,
                }
            )
            save_config(updated_config)
            update_config_session_defaults(updated_config)
            relations_message = (
                f", Relations-Datei auf '{selected_relations_filename}'"
                if selected_relations_filename
                else ", Relations-Datei deaktiviert"
            )
            st.success(f"Aktive CMDB-Entities-Datei auf '{selected_cmdb_filename}' gesetzt{relations_message}.")
            st.rerun()
    else:
        st.info("Noch keine CMDB-Datei im Input-Pfad vorhanden.")

    st.caption(f"Konfigurierter Output-Pfad: `{resolve_project_path(config.output_path)}`")
    if used_output_fallback:
        st.warning(f"Der konfigurierte Output-Pfad ist aktuell nicht beschreibbar. Artefakte werden nach `{runtime_output_path}` geschrieben.")
    else:
        st.write(str(runtime_output_path))


def render_config_tab(config_path: Path) -> None:
    st.subheader("Anwendungskonfig")
    config = load_config(config_path)
    ensure_config_session_defaults(config)
    sync_config_session_defaults(config)

    with st.expander("Import", expanded=False):
        render_import_section(config)

    with st.expander("Konfiguration", expanded=False):
        render_path_picker_controls()

        with st.form("config_form"):
            llm_base_url = st.text_input("LLM Base URL", value=st.session_state["config_llm_base_url"])
            llm_model = st.text_input("LLM Model", value=st.session_state["config_llm_model"])
            llm_api_key_env = st.text_input("API Key Env Var", value=st.session_state["config_llm_api_key_env"])
            llm_context_window = st.number_input("Context Window", min_value=1, value=st.session_state["config_llm_context_window"])
            llm_timeout_seconds = st.number_input("LLM Timeout Seconds", min_value=1, value=int(config.llm_timeout_seconds))
            input_path = st.text_input("Input Path", value=st.session_state["config_input_path"])
            cmdb_filename = st.text_input("CMDB Filename", value=st.session_state["config_cmdb_filename"])
            cmdb_relations_filename = st.text_input("CMDB Relations Filename", value=st.session_state["config_cmdb_relations_filename"])
            output_path = st.text_input("Output Path", value=st.session_state["config_output_path"])
            cmdb_uuid_column = st.text_input("CMDB UUID Column", value=config.cmdb_uuid_column)
            cmdb_name_column = st.text_input("CMDB Name Column", value=config.cmdb_name_column)
            cmdb_entity_type_column = st.text_input("CMDB Entity Type Column", value=config.cmdb_entity_type_column)
            cmdb_server_type_column = st.text_input("CMDB Server Type Column", value=config.cmdb_server_type_column)
            cmdb_owner_name_column = st.text_input("CMDB Owner Name Column", value=config.cmdb_owner_name_column)
            cmdb_relation_source_column = st.text_input("CMDB Relation Source Column", value=config.cmdb_relation_source_column)
            cmdb_relation_type_column = st.text_input("CMDB Relation Type Column", value=config.cmdb_relation_type_column)
            cmdb_relation_target_column = st.text_input("CMDB Relation Target Column", value=config.cmdb_relation_target_column)
            cmdb_multivalue_separator = st.text_input("CMDB Multi Value Separator", value=config.cmdb_multivalue_separator)
            neo4j_url = st.text_input("Neo4j URL", value=st.session_state["config_neo4j_url"])
            if os.getenv("NEO4J_URI"):
                st.caption("NEO4J_URI wurde aus der Umgebung geladen. Der aktuell wirksame Wert ist im Feld sichtbar und kann hier dauerhaft ueberschrieben werden.")
            neo4j_user = st.text_input("Neo4j User", value=st.session_state["config_neo4j_user"])
            if os.getenv("NEO4J_USERNAME"):
                st.caption("NEO4J_USERNAME wurde aus der Umgebung geladen. Der aktuell wirksame Wert ist im Feld sichtbar und kann hier dauerhaft ueberschrieben werden.")
            neo4j_password = st.text_input("Neo4j Password", value=st.session_state["config_neo4j_password"], type="password")
            if os.getenv("NEO4J_PASSWORD"):
                st.caption("NEO4J_PASSWORD wurde aus der Umgebung geladen. Der aktuell wirksame Wert bleibt beim Speichern erhalten, bis Sie ihn hier explizit aendern.")
            neo4j_database = st.text_input("Neo4j Database", value=st.session_state["config_neo4j_database"])
            if os.getenv("NEO4J_DATABASE"):
                st.caption("NEO4J_DATABASE wurde aus der Umgebung geladen. Der aktuell wirksame Wert ist im Feld sichtbar und kann hier dauerhaft ueberschrieben werden.")
            fuzzy_threshold = st.number_input("Fuzzy Threshold", min_value=0.0, max_value=1.0, value=float(config.fuzzy_threshold), step=0.01)
            debug_mode = st.checkbox("Debug Mode", value=config.debug_mode)
            last_run_mode = st.selectbox("Last Run Mode", ["full", "partial"], index=["full", "partial"].index(normalize_run_mode(config.last_run_mode)))
            submitted = st.form_submit_button("Save Config")

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
                cmdb_entity_type_column=cmdb_entity_type_column,
                cmdb_server_type_column=cmdb_server_type_column,
                cmdb_owner_name_column=cmdb_owner_name_column,
                cmdb_relations_filename=cmdb_relations_filename.strip(),
                cmdb_relation_source_column=cmdb_relation_source_column,
                cmdb_relation_type_column=cmdb_relation_type_column,
                cmdb_relation_target_column=cmdb_relation_target_column,
                cmdb_multivalue_separator=cmdb_multivalue_separator or "|",
                input_path=input_path,
                cmdb_filename=cmdb_filename,
                output_path=output_path,
                last_run_mode=last_run_mode,
                debug_mode=debug_mode,
            )
            save_config(updated_config, config_path)
            if build_neo4j_client_key(updated_config) != previous_client_key:
                reset_session_neo4j_client(show_warning=True)
            update_config_session_defaults(updated_config)
            st.success("Configuration saved.")

        refresh_neo4j_status = st.button("Neo4j-Verbindung neu pruefen")
        connection_ok, connection_message = get_neo4j_connection_status(load_config(config_path), force_refresh=refresh_neo4j_status)
        if connection_ok:
            st.success(connection_message)
        else:
            st.error(connection_message)

        if st.button("Refresh Models"):
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
                st.write({"models": models})

        refresh_llm_status = st.button("LLM-Verbindung neu pruefen")
        llm_status_level, llm_status_message = get_llm_status(load_config(config_path), force_refresh=refresh_llm_status)
        if llm_status_level == "success":
            st.success(llm_status_message)
        elif llm_status_level == "warning":
            st.warning(llm_status_message)
        else:
            st.error(llm_status_message)

        st.caption("Current config")
        st.json(asdict(load_config(config_path)))

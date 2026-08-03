from __future__ import annotations

from dataclasses import asdict
from pathlib import Path

import streamlit as st

from core.app_config import AppConfig, load_config, normalize_run_mode, resolve_project_path, resolve_runtime_output_path, save_config
from core.constants import (
    DOCUMENT_STATUS_ERROR,
    DOCUMENT_STATUS_NO_MATCHES,
    DOCUMENT_STATUS_PROCESSED,
    DOCUMENT_STATUS_SKIPPED_UNCHANGED,
)
from processing.bpmn_transformer import BpmnTransformError, transform_bpmn_for_import
from processing.cmdb import CmdbLoadError, validate_cmdb_entity_file
from processing.import_utils import describe_cmdb_file, list_cmdb_candidate_files, list_process_files
from core.neo4j_utils import Neo4jConnectionError, Neo4jQueryError
from services.cmdb_service import persist_cmdb_sync
from services.import_service import build_import_completion_message, finalize_import_artifacts
from services.runtime_service import (
    IMPORT_RUN_FEEDBACK_STATE_KEY,
    ensure_import_session_defaults,
    render_run_feedback,
    request_review_last_import_scope,
    run_pipeline_with_live_feedback,
    set_run_feedback,
    update_config_session_defaults,
)
from ui.layout import render_page_header

_LAST_RUN_DOCUMENTS_STATE_KEY = "import_last_run_documents"

_NOT_IMPORTED_REASON = {
    DOCUMENT_STATUS_SKIPPED_UNCHANGED: "Unverändert seit letztem Lauf – übersprungen",
    DOCUMENT_STATUS_ERROR: "Fehler bei der Verarbeitung",
}


def render_import_tab(config_path: Path) -> None:
    render_page_header(
        "Import",
        "Verarbeiten Sie Prozessdateien aus der Inbox und synchronisieren Sie die CMDB nach Neo4j.",
        "Pipeline und CMDB-Sync",
    )
    config = load_config(config_path)
    render_import_section(config)


def render_import_section(config: AppConfig) -> None:
    ensure_import_session_defaults(config)
    render_run_feedback(IMPORT_RUN_FEEDBACK_STATE_KEY)
    render_last_run_summary()

    input_dir = resolve_project_path(config.input_path)
    runtime_output_path, used_output_fallback = resolve_runtime_output_path(config.output_path)
    current_process_files = list_process_files(input_dir)
    process_file_labels = {path.relative_to(input_dir).as_posix(): path for path in current_process_files}
    available_bpmn_files = [path for path in current_process_files if path.suffix.lower() in {".bpmn", ".xml"}]

    _render_process_import_section(config, input_dir, runtime_output_path, current_process_files, process_file_labels)
    _render_bpmn_transform_section(input_dir, process_file_labels, available_bpmn_files)
    _render_cmdb_sync_section(config, input_dir)

    st.caption(f"Konfigurierter Ausgabepfad: `{resolve_project_path(config.output_path)}`")
    if used_output_fallback:
        st.warning(f"Der konfigurierte Ausgabepfad ist aktuell nicht beschreibbar. Artefakte werden nach `{runtime_output_path}` geschrieben.")


def store_last_run_summary(documents: list, input_dir: Path) -> None:
    rows = []
    for document in documents:
        try:
            display_path = Path(document.source_path).relative_to(input_dir).as_posix()
        except ValueError:
            display_path = document.source_path
        rows.append(
            {
                "display_path": display_path,
                "status": document.status,
                "reason": document.error_message or _NOT_IMPORTED_REASON.get(document.status, ""),
            }
        )
    st.session_state[_LAST_RUN_DOCUMENTS_STATE_KEY] = rows


def render_last_run_summary() -> None:
    rows = st.session_state.get(_LAST_RUN_DOCUMENTS_STATE_KEY)
    if not rows:
        return

    imported_statuses = {DOCUMENT_STATUS_PROCESSED, DOCUMENT_STATUS_NO_MATCHES}
    imported = [row for row in rows if row["status"] in imported_statuses]
    not_imported = [row for row in rows if row["status"] not in imported_statuses]
    no_matches_count = sum(1 for row in rows if row["status"] == DOCUMENT_STATUS_NO_MATCHES)

    summary_parts = [f"{len(imported)} importiert"]
    if no_matches_count:
        summary_parts.append(f"davon {no_matches_count} ohne erkannte Anwendungen")
    skipped_count = sum(1 for row in rows if row["status"] == DOCUMENT_STATUS_SKIPPED_UNCHANGED)
    error_count = sum(1 for row in rows if row["status"] == DOCUMENT_STATUS_ERROR)
    if skipped_count:
        summary_parts.append(f"{skipped_count} übersprungen")
    if error_count:
        summary_parts.append(f"{error_count} mit Fehler")
    st.caption("Letzter Lauf: " + ", ".join(summary_parts) + ".")

    if not_imported:
        with st.expander(f"Nicht importierte Dateien ({len(not_imported)})", expanded=False):
            st.dataframe(
                [{"Datei": row["display_path"], "Grund": row["reason"]} for row in not_imported],
                width="stretch",
                hide_index=True,
            )


def _render_process_import_section(
    config: AppConfig,
    input_dir: Path,
    runtime_output_path: Path,
    current_process_files: list[Path],
    process_file_labels: dict[str, Path],
) -> None:
    with st.container(border=True):
        st.markdown("#### Prozessimport")
        st.caption(
            "Der Import verarbeitet neue Prozessdateien aus der Inbox `Input/`; verarbeitete Dateien werden anschließend archiviert. "
            "Legen Sie neue Prozessdateien und die aktiven CMDB-Dateien direkt im aktuellen Eingabepfad ab."
        )

        mode_column, run_column = st.columns([2, 1], vertical_alignment="bottom")
        with mode_column:
            selected_run_mode = st.selectbox(
                "Importmodus",
                options=["full", "partial"],
                key="import_run_mode",
                help=(
                    "`full` verarbeitet alle Prozessdateien im aktuellen Eingabepfad. "
                    "`partial` verarbeitet nur die hier explizit ausgewählten Dateien."
                ),
            )
        with run_column:
            start_pipeline = st.button("Pipeline starten", width="stretch", type="primary")

        selected_import_filenames: list[str] = []
        if selected_run_mode == "partial":
            selected_import_filenames = st.multiselect(
                "Dateien für Teilimport",
                options=list(process_file_labels.keys()),
                default=[],
                key="import_process_selection",
            )

        if start_pipeline:
            if not config.llm_model:
                st.warning("Bitte zuerst ein LLM-Modell konfigurieren.")
            elif selected_run_mode == "partial" and not selected_import_filenames:
                st.info("Bitte wählen Sie mindestens eine Prozessdatei für den Teilimport aus.")
            else:
                selected_input_paths = [process_file_labels[label] for label in selected_import_filenames]
                pipeline_input_paths = None if selected_run_mode == "full" else selected_input_paths
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
                if run_result is not None and duration is not None:
                    store_last_run_summary(run_result.documents, input_dir)
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


def _render_bpmn_transform_section(
    input_dir: Path,
    process_file_labels: dict[str, Path],
    available_bpmn_files: list[Path],
) -> None:
    with st.container(border=True):
        st.markdown("#### BPMN-Transformation")
        st.caption("Optional: Reduziert große BPMN/XML-Dateien vor dem eigentlichen Import auf kompakte Prozessdateien.")

        select_column, action_column = st.columns([2, 1], vertical_alignment="bottom")
        with select_column:
            selected_transform_filenames = st.multiselect(
                "BPMN für Transformation",
                options=[path.relative_to(input_dir).as_posix() for path in available_bpmn_files],
                default=[],
                key="transform_bpmn_selection",
            )
        with action_column:
            transform_clicked = st.button("BPMN transformieren", width="stretch")

        if transform_clicked:
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


def _render_cmdb_sync_section(config: AppConfig, input_dir: Path) -> None:
    with st.container(border=True):
        st.markdown("#### CMDB-Synchronisation")
        st.caption("Weisen Sie jeder CMDB-Objektart eine CSV-Datei aus dem Eingabepfad zu und übertragen Sie die Daten nach Neo4j.")

        available_csv_files = [describe_cmdb_file(path, input_dir) for path in list_cmdb_candidate_files(input_dir, config.cmdb_uuid_column, config.cmdb_name_column)]
        if not available_csv_files:
            st.info("Noch keine CMDB-Dateien im Eingabepfad vorhanden.")
            return

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

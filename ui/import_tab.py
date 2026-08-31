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
from core.i18n import translate
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

def _t(key: str, **values: object) -> str:
    return translate(key, st.session_state.get("bridgr_locale"), **values)


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

    st.caption(_t("ui.configured_output_path", path=resolve_project_path(config.output_path)))
    if used_output_fallback:
        st.warning(_t("ui.output_path_fallback", path=runtime_output_path))


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
                "reason": document.error_message or {
                    DOCUMENT_STATUS_SKIPPED_UNCHANGED: _t("import.reason_unchanged"),
                    DOCUMENT_STATUS_ERROR: _t("import.reason_error"),
                }.get(document.status, ""),
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

    summary_parts = [_t("import.summary.imported", count=len(imported))]
    if no_matches_count:
        summary_parts.append(_t("import.summary.no_matches", count=no_matches_count))
    skipped_count = sum(1 for row in rows if row["status"] == DOCUMENT_STATUS_SKIPPED_UNCHANGED)
    error_count = sum(1 for row in rows if row["status"] == DOCUMENT_STATUS_ERROR)
    if skipped_count:
        summary_parts.append(_t("import.summary.skipped", count=skipped_count))
    if error_count:
        summary_parts.append(_t("import.summary.errors", count=error_count))
    st.caption(_t("import.last_run", summary=", ".join(summary_parts)))

    if not_imported:
        with st.expander(_t("import.not_imported", count=len(not_imported)), expanded=False):
            st.dataframe(
                [{_t("import.file"): row["display_path"], _t("import.reason"): row["reason"]} for row in not_imported],
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
        st.markdown(f"#### {_t('import.process_import')}")
        st.caption(_t("import.process_intro"))

        mode_column, run_column = st.columns([2, 1], vertical_alignment="bottom")
        with mode_column:
            selected_run_mode = st.selectbox(
                _t("import.mode"),
                options=["full", "partial"],
                key="import_run_mode",
                help=_t("import.mode_help"),
            )
        with run_column:
            start_pipeline = st.button(_t("import.start"), width="stretch", type="primary")

        selected_import_filenames: list[str] = []
        if selected_run_mode == "partial":
            selected_import_filenames = st.multiselect(
                _t("import.partial_files"),
                options=list(process_file_labels.keys()),
                default=[],
                key="import_process_selection",
            )

        if start_pipeline:
            if not config.llm_model:
                st.warning(_t("import.llm_required"))
            elif selected_run_mode == "partial" and not selected_import_filenames:
                st.info(_t("import.partial_required"))
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
                    success_message_template=_t("import.success", duration="{duration}"),
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

        st.caption(_t("import.input_path", path=input_dir))
        if current_process_files:
            st.dataframe(
                [{_t("import.file"): path.relative_to(input_dir).as_posix()} for path in current_process_files],
                width="stretch",
            )
        else:
            st.info(_t("import.no_process_files"))


def _render_bpmn_transform_section(
    input_dir: Path,
    process_file_labels: dict[str, Path],
    available_bpmn_files: list[Path],
) -> None:
    with st.container(border=True):
        st.markdown(f"#### {_t('import.bpmn_transform')}")
        st.caption(_t("import.bpmn_intro"))

        select_column, action_column = st.columns([2, 1], vertical_alignment="bottom")
        with select_column:
            selected_transform_filenames = st.multiselect(
                _t("import.bpmn_files"),
                options=[path.relative_to(input_dir).as_posix() for path in available_bpmn_files],
                default=[],
                key="transform_bpmn_selection",
            )
        with action_column:
            transform_clicked = st.button(_t("import.transform"), width="stretch")

        if transform_clicked:
            if not available_bpmn_files:
                st.info(_t("import.no_bpmn_files"))
            elif not selected_transform_filenames:
                st.info(_t("import.select_bpmn"))
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
                        _t("import.transform_success", count=len(transformed_paths), path=input_dir / "transformed")
                    )
                    st.write(transformed_paths)


def _render_cmdb_sync_section(config: AppConfig, input_dir: Path) -> None:
    with st.container(border=True):
        st.markdown(f"#### {_t('import.cmdb_sync')}")
        st.caption(_t("import.cmdb_intro"))

        available_csv_files = [describe_cmdb_file(path, input_dir) for path in list_cmdb_candidate_files(input_dir, config.cmdb_uuid_column, config.cmdb_name_column)]
        if not available_csv_files:
            st.info(_t("import.no_cmdb_files"))
            return

        current_type_files = config.cmdb_type_files
        file_options = [""] + available_csv_files

        app_col, srv_col, if_col = st.columns(3)
        with app_col:
            app_default = current_type_files.get("application", "")
            app_idx = file_options.index(app_default) if app_default in file_options else 0
            selected_app_file = st.selectbox(_t("import.applications"), options=file_options, index=app_idx,
                                              format_func=lambda v: v or _t("import.none"), key="active_cmdb_application_file")
        with srv_col:
            srv_default = current_type_files.get("server", "")
            srv_idx = file_options.index(srv_default) if srv_default in file_options else 0
            selected_srv_file = st.selectbox(_t("import.servers"), options=file_options, index=srv_idx,
                                              format_func=lambda v: v or _t("import.none"), key="active_cmdb_server_file")
        with if_col:
            if_default = current_type_files.get("interface", "")
            if_idx = file_options.index(if_default) if if_default in file_options else 0
            selected_if_file = st.selectbox(_t("import.interfaces"), options=file_options, index=if_idx,
                                             format_func=lambda v: v or _t("import.none"), key="active_cmdb_interface_file")

        def _build_type_files_from_selection() -> dict[str, str]:
            return {k: v for k, v in {
                "application": selected_app_file,
                "server": selected_srv_file,
                "interface": selected_if_file,
            }.items() if v}

        action_col_save, action_col_sync = st.columns(2)
        with action_col_save:
            if st.button(_t("import.apply_type_files"), width="stretch"):
                new_type_files = _build_type_files_from_selection()
                updated_config = AppConfig(**{**asdict(config), "cmdb_type_files": new_type_files})
                save_config(updated_config)
                update_config_session_defaults(updated_config)
                label = ", ".join(f"{k}={v}" for k, v in new_type_files.items()) if new_type_files else _t("import.none")
                st.success(_t("import.type_files_saved", label=label))
                st.rerun()

        with action_col_sync:
            if st.button(_t("import.sync_cmdb"), width="stretch"):
                new_type_files = _build_type_files_from_selection()
                sync_config = AppConfig(**{**asdict(config), "cmdb_type_files": new_type_files})
                save_config(sync_config)
                update_config_session_defaults(sync_config)
                try:
                    result = persist_cmdb_sync(sync_config)
                except (CmdbLoadError, Neo4jConnectionError, Neo4jQueryError) as exc:
                    st.error(_t("import.cmdb_sync_error", error=exc))
                else:
                    st.success(
                        _t("import.cmdb_sync_success", entities=result.entity_count, relations=result.relation_count,
                           owners=result.owner_assignment_count, documents=result.refreshed_document_count)
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
                st.error(_t("import.cmdb_structure_error", file_name=file_name, type_label=type_label))
                st.dataframe(
                    [{_t("import.message"): _t("import.line_message", line=issue.line_number, message=issue.message)} for issue in issues],
                    width="stretch",
                    hide_index=True,
                )

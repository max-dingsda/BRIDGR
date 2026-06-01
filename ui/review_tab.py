from __future__ import annotations

from pathlib import Path

import streamlit as st

from app_config import AppConfig, load_config, resolve_input_cmdb_path, resolve_runtime_output_path
from cmdb import CmdbLoadError, build_cmdb_option_labels, find_cmdb_row_by_label, load_cmdb_rows
from constants import DOCUMENT_STATUS_OPTIONS, MATCH_SOURCE_REJECTED
from knowledge_base import load_knowledge_base
from run_artifacts import load_last_import_context, load_latest_run
from services.review_service import (
    confirm_review_link,
    reject_review_link,
    save_manual_link,
)
from services.runtime_service import (
    REVIEW_RUN_FEEDBACK_STATE_KEY,
    apply_pending_review_scope_defaults,
    render_run_feedback,
)
from ui_run_view import (
    build_document_details,
    build_document_status_rows,
    build_duplicate_application_warnings,
    build_review_rows,
    filter_documents,
    summarize_org_candidate_scope,
    summarize_run,
    summarize_review_artifacts,
)


def render_latest_run_summary(latest_run: dict, documents: list[dict]) -> None:
    summary = summarize_run(latest_run, documents)
    metric_columns = st.columns(6)
    metric_columns[0].metric("Modus", str(summary["run_mode"]))
    metric_columns[1].metric("Anzahl Dokumente", int(summary["documents"]))
    metric_columns[2].metric("Identifizierte Prozesse", int(summary["identified_processes"]))
    metric_columns[3].metric("Davon neu", int(summary["new_processes"]))
    metric_columns[4].metric("Davon bestehend", int(summary["existing_processes"]))
    metric_columns[5].metric("Fehlerhafte Dokumente", int(summary["errors"]))
    if summary["no_matches"]:
        st.caption(f"Dokumente ohne Anwendungszuordnung: {summary['no_matches']}")


def render_document_status_table(documents: list[dict]) -> None:
    rows = build_document_status_rows(documents)
    st.markdown("**Dokumentstatus**")
    if rows:
        st.dataframe(rows, width="stretch")
    else:
        st.info("Keine Dokumente für den aktuellen Filter gefunden.")


def render_review_artifact_summary(documents: list[dict]) -> None:
    knowledge_base = load_knowledge_base()
    summary = summarize_review_artifacts(documents, knowledge_base.org_unit_candidates)
    st.markdown("**Der letzte Import hat folgendes gefunden**")
    st.markdown(f"- {summary['exact_application_matches']} eindeutige Applikationszuordnungen")
    st.markdown(f"- {summary['review_application_matches']} zu prüfende Applikationszuordnungen")
    st.markdown(f"- {summary['exact_org_unit_matches']} eindeutige Organisationseinheiten")
    st.markdown(f"- {summary['review_org_unit_candidates']} zu prüfende Organisationseinheiten")


def render_duplicate_application_warnings(documents: list[dict]) -> None:
    warnings = build_duplicate_application_warnings(documents)
    if not warnings:
        return
    st.markdown("**Hinweise zur Prozessnotation**")
    for warning in warnings:
        variants = "; ".join(warning.get("varianten", []))
        st.warning(
            f"Im Prozess '{warning.get('prozess', '')}' scheint dieselbe Anwendung mehrfach unterschiedlich notiert zu sein: {variants}"
        )


def _resolve_cmdb_rows(config: AppConfig) -> list[dict[str, str]]:
    return load_cmdb_rows(
        resolve_input_cmdb_path(config),
        config.cmdb_uuid_column,
        config.cmdb_name_column,
    )


def _filter_application_cmdb_rows(config: AppConfig, cmdb_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    entity_type_column = config.cmdb_entity_type_column
    filtered_rows: list[dict[str, str]] = []
    for row in cmdb_rows:
        entity_type = (row.get(entity_type_column) or "").strip().lower()
        if not entity_type or entity_type == "application":
            filtered_rows.append(row)
    return filtered_rows


def render_review_item_actions(review_row: dict, config: AppConfig, cmdb_rows: list[dict[str, str]]) -> None:
    process_name = review_row.get("prozess", "")
    source_path = review_row.get("source_path", "")
    application_name = review_row.get("anwendung_im_prozess", "")
    matched_name = review_row.get("anwendung_in_cmdb", "")
    cmdb_id = review_row.get("cmdb_id")
    row_id = review_row.get("row_id", "")

    row_columns = st.columns([2, 3, 3, 1, 1, 1, 2])
    row_columns[0].write(process_name)
    row_columns[1].write(application_name)
    row_columns[2].write(matched_name)
    row_columns[3].write(review_row.get("confidence", ""))

    if cmdb_id and row_columns[4].button("Bestätigen", key=f"review-confirm::{row_id}", width="stretch"):
        st.success(confirm_review_link(config, process_name, application_name, cmdb_id, matched_name, source_path, cmdb_rows))
        st.rerun()

    if row_columns[5].button("Ablehnen", key=f"review-reject::{row_id}", width="stretch"):
        st.success(reject_review_link(config, process_name, application_name, cmdb_id, source_path, cmdb_rows))
        st.rerun()

    application_rows = _filter_application_cmdb_rows(config, cmdb_rows)
    cmdb_options = build_cmdb_option_labels(application_rows, config.cmdb_uuid_column, config.cmdb_name_column)
    if not cmdb_options:
        row_columns[6].write("-")
        return

    with row_columns[6].popover("Manuell anlegen", use_container_width=True):
        selected_label = st.selectbox(
            "CMDB-Ziel",
            options=cmdb_options,
            key=f"review-manual-select::{row_id}",
            label_visibility="collapsed",
        )
        if st.button("Speichern", key=f"review-manual-submit::{row_id}", width="stretch"):
            selected_row = find_cmdb_row_by_label(
                application_rows,
                selected_label,
                config.cmdb_uuid_column,
                config.cmdb_name_column,
            )
            if selected_row is None:
                st.error("Ausgewähltes CMDB-Ziel konnte nicht aufgelöst werden.")
                return
            st.success(
                save_manual_link(
                    config,
                    process_name,
                    application_name,
                    selected_row.get(config.cmdb_uuid_column, ""),
                    selected_row.get(config.cmdb_name_column, application_name),
                    source_path,
                    cmdb_rows,
                )
            )
            st.rerun()


def render_review_items_table(documents: list[dict], config: AppConfig, cmdb_rows: list[dict[str, str]]) -> None:
    review_rows = build_review_rows(documents)
    st.markdown("**Offene Zuordnungen**")
    if not review_rows:
        st.success("Keine offenen Zuordnungen für den aktuellen Filter.")
        return

    header_columns = st.columns([2, 3, 3, 1, 1, 1, 2])
    header_columns[0].markdown("**Prozess**")
    header_columns[1].markdown("**Anwendung im Prozess**")
    header_columns[2].markdown("**Anwendung in der CMDB**")
    header_columns[3].markdown("**Bewertung**")
    header_columns[4].markdown("**Bestätigen**")
    header_columns[5].markdown("**Ablehnen**")
    header_columns[6].markdown("**Manuell anlegen**")

    for review_row in review_rows:
        render_review_item_actions(review_row, config, cmdb_rows)


def render_document_details(documents: list[dict]) -> None:
    st.markdown("**Dokumentdetails**")
    details = build_document_details(documents)
    if not details:
        st.info("Keine Detaildaten für den aktuellen Filter vorhanden.")
        return

    for detail in details:
        with st.expander(detail["title"]):
            left_column, right_column = st.columns(2)
            with left_column:
                st.write(
                    {
                        "process_name": detail["process_name"],
                        "process_id": detail["process_id"],
                        "org_unit": detail["org_unit"],
                        "follows_after": detail["follows_after"],
                        "file_hash": detail["file_hash"],
                    }
                )
            with right_column:
                if detail["error_message"]:
                    st.error(detail["error_message"])
                else:
                    st.write({"review_items": detail["review_items"]})

            with st.expander("Technische Details", expanded=False):
                st.markdown("Rohanwendungen")
                st.json(detail["raw_applications"])
                st.markdown("Anwendungen")
                st.json(detail["applications"])
                st.markdown("Zuordnungen")
                st.json(detail["matches"])


def render_review_tab() -> None:
    st.subheader("Zuordnungen")
    config = load_config(Path("config.json"))
    apply_pending_review_scope_defaults()
    render_run_feedback(REVIEW_RUN_FEEDBACK_STATE_KEY)
    st.caption(
        "Hier bearbeiten Sie bereits bekannte schwache oder offene Zuordnungen. "
        "Es wird kein neuer Import aus der Inbox gestartet."
    )

    runtime_output_path, used_output_fallback = resolve_runtime_output_path(config.output_path)
    last_import_context = load_last_import_context(runtime_output_path)
    last_import_source_paths = last_import_context.get("source_paths", [])
    last_import_labels = last_import_context.get("display_paths", [])
    last_import_archive_path = last_import_context.get("archive_path", "")

    action_column, info_column = st.columns([1, 2])
    with action_column:
        review_scope = st.radio(
            "Umfang",
            options=["Nur letzter Import", "Dateien manuell wählen"],
            key="review_scope_mode",
        )
        selected_review_source_paths: list[str] = []
        if review_scope == "Nur letzter Import":
            if last_import_labels:
                st.caption(f"{len(last_import_labels)} Datei(en) aus dem letzten Import stehen zur Verfügung.")
                st.dataframe([{"Datei": label} for label in last_import_labels], width="stretch")
                if last_import_archive_path:
                    st.caption(f"Archivpfad des letzten Imports: `{last_import_archive_path}`")
                selected_review_source_paths = list(last_import_source_paths)
            else:
                st.info("Es liegt noch keine gespeicherte Auswahl aus dem letzten Import vor.")
        else:
            latest_run = load_latest_run(runtime_output_path) or {}
            manual_review_options = sorted(
                {
                    document.get("source_path", "")
                    for document in latest_run.get("documents", [])
                    if document.get("source_path")
                }
            )
            selected_review_source_paths = st.multiselect(
                "Dateien für Überprüfung",
                options=manual_review_options,
                default=[],
                key="review_process_selection",
                format_func=lambda value: Path(value).name,
            )
    with info_column:
        st.caption(
            "Die Ansicht liest den letzten gespeicherten Lauf aus `Output/latest_run.json` "
            "und zeigt offene bzw. schwache Zuordnungsfälle zur Bearbeitung."
        )

    latest_run = load_latest_run(runtime_output_path)
    if latest_run is None:
        if used_output_fallback:
            st.warning(f"Der konfigurierte Ausgabepfad ist nicht beschreibbar. Laufartefakte werden nach `{runtime_output_path}` umgeleitet.")
        st.info("Noch kein gespeicherter Pipeline-Lauf vorhanden.")
        return

    if latest_run.get("used_output_fallback"):
        st.warning(f"Laufartefakte werden aktuell nach `{latest_run.get('output_path', runtime_output_path)}` geschrieben.")

    selected_statuses = st.multiselect("Statusfilter", options=DOCUMENT_STATUS_OPTIONS, default=DOCUMENT_STATUS_OPTIONS)
    filtered_documents = filter_documents(latest_run, selected_statuses)
    active_scope_paths = selected_review_source_paths
    if active_scope_paths:
        filtered_documents = [
            document
            for document in filtered_documents
            if document.get("source_path", "") in active_scope_paths
        ]
    elif review_scope == "Dateien manuell wählen":
        st.info("Bitte wählen Sie mindestens eine Prozessdatei für die Überprüfung aus.")
        filtered_documents = []
    render_latest_run_summary(latest_run, filtered_documents)
    try:
        cmdb_rows = _resolve_cmdb_rows(config)
    except CmdbLoadError as exc:
        st.error(str(exc))
        return
    render_review_artifact_summary(filtered_documents)
    render_document_status_table(filtered_documents)
    knowledge_base = load_knowledge_base()
    candidate_scope = summarize_org_candidate_scope(filtered_documents, knowledge_base.org_unit_candidates)
    if candidate_scope["scoped_open_candidates"]:
        st.info(
            f"Es liegen {candidate_scope['scoped_open_candidates']} offene Organisationseinheiten-Kandidat(en) "
            "aus dem aktuell betrachteten Prozessimport vor. Diese müssen im Tab **Organisation** bestätigt, "
            "zugeordnet oder abgewiesen werden."
        )
    if candidate_scope["external_open_candidates"]:
        st.info(
            f"Zusätzlich liegen {candidate_scope['external_open_candidates']} weitere offene "
            "Organisationseinheiten-Kandidat(en) außerhalb dieses Prozessimports vor, typischerweise aus dem "
            "CMDB-Import. Auch diese können im Tab **Organisation** bearbeitet werden."
        )
    render_duplicate_application_warnings(filtered_documents)
    render_review_items_table(filtered_documents, config, cmdb_rows)
    render_document_details(filtered_documents)

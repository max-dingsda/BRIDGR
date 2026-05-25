from __future__ import annotations

from dataclasses import asdict
from pathlib import Path

import streamlit as st

from app_config import AppConfig, load_config, resolve_project_path, resolve_runtime_output_path, save_config
from cmdb import build_cmdb_option_labels, find_cmdb_row_by_label, load_cmdb_rows
from env_loader import load_env_files
from import_utils import list_process_files, sanitize_uploaded_name, save_uploaded_file
from knowledge_base import confirm_link, load_knowledge_base, reject_link, save_knowledge_base
from llm_client import LlmClientConfig, LlmClientError, OpenAICompatibleClient
from pipeline import run_pipeline
from run_artifacts import load_latest_run
from ui_run_view import (
    build_document_details,
    build_document_status_rows,
    build_review_rows,
    filter_documents,
    summarize_run,
)


def render_query_tab() -> None:
    st.subheader("Tab 1 - Kommunikation")
    question = st.text_input("Frage an den Wissensgraphen", placeholder="Welche Anwendungen unterstuetzt Prozess X?")
    if st.button("Senden", key="send_query"):
        if not question:
            st.warning("Bitte zuerst eine Frage eingeben.")
            return
        st.info("Der Query-Layer ist im Scaffold noch nicht implementiert.")


def render_review_tab() -> None:
    st.subheader("Tab 2 - Link Editing")
    config = load_config(Path("config.json"))

    action_column, info_column = st.columns([1, 2])
    with action_column:
        if st.button("Pipeline Preview starten", key="review_preview", width="stretch"):
            if not config.llm_model:
                st.warning("Bitte zuerst ein LLM-Modell in Tab 3 konfigurieren.")
            else:
                try:
                    run_pipeline(config)
                except Exception as exc:
                    st.error(str(exc))
                else:
                    st.success("Preview-Lauf abgeschlossen. Artefakte im Output-Ordner wurden aktualisiert.")
    with info_column:
        st.caption("Die Ansicht liest den letzten gespeicherten Lauf aus `Output/latest_run.json`.")

    runtime_output_path, used_output_fallback = resolve_runtime_output_path(config.output_path)
    latest_run = load_latest_run(runtime_output_path)
    if latest_run is None:
        if used_output_fallback:
            st.warning(f"Der konfigurierte Output-Pfad ist nicht beschreibbar. Laufartefakte werden nach `{runtime_output_path}` umgeleitet.")
        st.info("Noch kein gespeicherter Pipeline-Lauf vorhanden.")
        return

    if latest_run.get("used_output_fallback"):
        st.warning(f"Laufartefakte werden aktuell nach `{latest_run.get('output_path', runtime_output_path)}` geschrieben.")

    render_latest_run_summary(latest_run)
    selected_statuses = st.multiselect(
        "Statusfilter",
        options=["processed", "skipped_unchanged", "no_matches", "error"],
        default=["processed", "skipped_unchanged", "no_matches", "error"],
    )
    filtered_documents = filter_documents(latest_run, selected_statuses)
    cmdb_rows = load_cmdb_rows(resolve_project_path(config.cmdb_path))
    render_document_status_table(filtered_documents)
    render_review_items_table(filtered_documents)
    render_document_details(filtered_documents, config, cmdb_rows)


def render_latest_run_summary(latest_run: dict) -> None:
    summary = summarize_run(latest_run)

    metric_columns = st.columns(5)
    metric_columns[0].metric("Run Mode", str(summary["run_mode"]))
    metric_columns[1].metric("Documents", int(summary["documents"]))
    metric_columns[2].metric("Processed", int(summary["processed"]))
    metric_columns[3].metric("Skipped", int(summary["skipped"]))
    metric_columns[4].metric("Errors", int(summary["errors"]))
    if summary["no_matches"]:
        st.caption(f"Documents without application matches: {summary['no_matches']}")


def render_document_status_table(documents: list[dict]) -> None:
    rows = build_document_status_rows(documents)
    st.markdown("**Dokumentstatus**")
    if rows:
        st.dataframe(rows, width="stretch")
    else:
        st.info("Keine Dokumente fuer den aktuellen Filter gefunden.")


def render_review_items_table(documents: list[dict]) -> None:
    review_rows = build_review_rows(documents)
    st.markdown("**Review-Items**")
    if review_rows:
        st.dataframe(review_rows, width="stretch")
    else:
        st.success("Keine Review-Items fuer den aktuellen Filter gefunden.")


def render_document_details(documents: list[dict], config: AppConfig, cmdb_rows: list[dict[str, str]]) -> None:
    st.markdown("**Dokumentdetails**")
    details = build_document_details(documents)
    if not details:
        st.info("Keine Detaildaten fuer den aktuellen Filter vorhanden.")
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

            st.markdown("Applications")
            st.json(detail["applications"])
            st.markdown("Matches")
            st.json(detail["matches"])
            render_review_actions(detail, config, cmdb_rows)
            render_manual_link_form(detail, config, cmdb_rows)


def render_review_actions(detail: dict, config: AppConfig, cmdb_rows: list[dict[str, str]]) -> None:
    process_name = detail["process_name"]
    matches = detail["matches"]
    if not matches:
        return

    st.markdown("Aktionen")
    cmdb_options = build_cmdb_option_labels(cmdb_rows, config.cmdb_uuid_column, config.cmdb_name_column)
    for index, match in enumerate(matches):
        application_name = match.get("application_name", "")
        matched_name = match.get("matched_name") or ""
        cmdb_id = match.get("cmdb_id")
        source = match.get("source", "")

        action_columns = st.columns([3, 1, 1])
        action_columns[0].write(
            {
                "application_name": application_name,
                "matched_name": matched_name,
                "cmdb_id": cmdb_id,
                "source": source,
                "confidence": match.get("confidence", ""),
            }
        )

        confirm_key = f"confirm::{detail['file_hash']}::{index}"
        correct_select_key = f"correct-select::{detail['file_hash']}::{index}"
        correct_key = f"correct::{detail['file_hash']}::{index}"
        reject_key = f"reject::{detail['file_hash']}::{index}"

        if cmdb_id and action_columns[1].button("Bestaetigen", key=confirm_key, width="stretch"):
            knowledge_base = load_knowledge_base()
            updated_kb = confirm_link(
                knowledge_base,
                process_name=process_name,
                application_name=application_name,
                cmdb_id=cmdb_id,
                matched_name=matched_name or application_name,
                source="manuell_bestaetigt",
            )
            save_knowledge_base(updated_kb)
            run_pipeline(config)
            st.success(f"Link fuer '{application_name}' bestaetigt.")
            st.rerun()

        if action_columns[2].button("Ablehnen", key=reject_key, width="stretch"):
            knowledge_base = load_knowledge_base()
            updated_kb = reject_link(
                knowledge_base,
                process_name=process_name,
                application_name=application_name,
            )
            save_knowledge_base(updated_kb)
            run_pipeline(config)
            st.success(f"Link fuer '{application_name}' abgelehnt.")
            st.rerun()

        if cmdb_options:
            selected_label = st.selectbox(
                f"Korrigiertes CMDB-Ziel fuer {application_name}",
                options=cmdb_options,
                key=correct_select_key,
            )
            if st.button(f"Korrigieren: {application_name}", key=correct_key, width="stretch"):
                selected_row = find_cmdb_row_by_label(
                    cmdb_rows,
                    selected_label,
                    config.cmdb_uuid_column,
                    config.cmdb_name_column,
                )
                if selected_row is None:
                    st.error("Ausgewaehltes CMDB-Ziel konnte nicht aufgeloest werden.")
                else:
                    knowledge_base = load_knowledge_base()
                    updated_kb = confirm_link(
                        knowledge_base,
                        process_name=process_name,
                        application_name=application_name,
                        cmdb_id=selected_row.get(config.cmdb_uuid_column, ""),
                        matched_name=selected_row.get(config.cmdb_name_column, application_name),
                        source="manuell_korrigiert",
                    )
                    save_knowledge_base(updated_kb)
                    run_pipeline(config)
                    st.success(f"Link fuer '{application_name}' wurde korrigiert.")
                    st.rerun()


def render_manual_link_form(detail: dict, config: AppConfig, cmdb_rows: list[dict[str, str]]) -> None:
    process_name = detail["process_name"]
    if not process_name:
        return

    cmdb_options = build_cmdb_option_labels(cmdb_rows, config.cmdb_uuid_column, config.cmdb_name_column)
    if not cmdb_options:
        st.info("Keine CMDB-Eintraege fuer manuellen Link verfuegbar.")
        return

    st.markdown("Manuellen Link anlegen")
    manual_name_key = f"manual-name::{detail['file_hash']}"
    manual_target_key = f"manual-target::{detail['file_hash']}"
    manual_submit_key = f"manual-submit::{detail['file_hash']}"

    manual_application_name = st.text_input(
        "Bezeichnung im Prozesskontext",
        value="",
        key=manual_name_key,
        placeholder="z.B. SAP Sales oder Vertragssystem",
    )
    selected_label = st.selectbox(
        "CMDB-Ziel",
        options=cmdb_options,
        key=manual_target_key,
    )

    if st.button("Manuellen Link speichern", key=manual_submit_key, width="stretch"):
        selected_row = find_cmdb_row_by_label(
            cmdb_rows,
            selected_label,
            config.cmdb_uuid_column,
            config.cmdb_name_column,
        )
        if selected_row is None:
            st.error("Ausgewaehltes CMDB-Ziel konnte nicht aufgeloest werden.")
            return

        application_name = manual_application_name.strip() or selected_row.get(config.cmdb_name_column, "")
        knowledge_base = load_knowledge_base()
        updated_kb = confirm_link(
            knowledge_base,
            process_name=process_name,
            application_name=application_name,
            cmdb_id=selected_row.get(config.cmdb_uuid_column, ""),
            matched_name=selected_row.get(config.cmdb_name_column, application_name),
            source="manueller_link",
        )
        save_knowledge_base(updated_kb)
        run_pipeline(config)
        st.success(f"Manueller Link fuer '{application_name}' gespeichert.")
        st.rerun()


def render_config_tab(config_path: Path) -> None:
    st.subheader("Tab 3 - Anwendungskonfig")
    config = load_config(config_path)

    with st.form("config_form"):
        llm_base_url = st.text_input("LLM Base URL", value=config.llm_base_url)
        llm_model = st.text_input("LLM Model", value=config.llm_model)
        llm_api_key_env = st.text_input("API Key Env Var", value=config.llm_api_key_env)
        llm_context_window = st.number_input("Context Window", min_value=1, value=config.llm_context_window)
        process_input_path = st.text_input("Process Input Path", value=config.process_input_path)
        cmdb_path = st.text_input("CMDB Path", value=config.cmdb_path)
        output_path = st.text_input("Output Path", value=config.output_path)
        cmdb_uuid_column = st.text_input("CMDB UUID Column", value=config.cmdb_uuid_column)
        cmdb_name_column = st.text_input("CMDB Name Column", value=config.cmdb_name_column)
        neo4j_url = st.text_input("Neo4j URL", value=config.neo4j_url)
        neo4j_user = st.text_input("Neo4j User", value=config.neo4j_user)
        fuzzy_threshold = st.number_input(
            "Fuzzy Threshold",
            min_value=0.0,
            max_value=1.0,
            value=float(config.fuzzy_threshold),
            step=0.01,
        )
        last_run_mode = st.selectbox(
            "Last Run Mode",
            ["initial", "full", "delta"],
            index=["initial", "full", "delta"].index(config.last_run_mode),
        )
        submitted = st.form_submit_button("Save Config")

    if submitted:
        updated_config = AppConfig(
            llm_base_url=llm_base_url,
            llm_model=llm_model,
            llm_api_key_env=llm_api_key_env,
            llm_context_window=int(llm_context_window),
            neo4j_url=neo4j_url,
            neo4j_user=neo4j_user,
            fuzzy_threshold=float(fuzzy_threshold),
            cmdb_uuid_column=cmdb_uuid_column,
            cmdb_name_column=cmdb_name_column,
            process_input_path=process_input_path,
            cmdb_path=cmdb_path,
            output_path=output_path,
            last_run_mode=last_run_mode,
        )
        save_config(updated_config, config_path)
        st.success("Configuration saved.")

    if st.button("Refresh Models"):
        client = OpenAICompatibleClient(
            LlmClientConfig(
                base_url=config.llm_base_url,
                model=config.llm_model,
                api_key_env=config.llm_api_key_env,
            )
        )
        try:
            models = client.list_models()
        except LlmClientError as exc:
            st.error(str(exc))
        else:
            st.write({"models": models})

    st.caption("Current config")
    st.json(asdict(load_config(config_path)))
    render_import_section(load_config(config_path))


def render_import_section(config: AppConfig) -> None:
    st.markdown("**Import**")

    process_input_dir = Path(config.process_input_path)
    process_input_dir = resolve_project_path(config.process_input_path)
    cmdb_path = resolve_project_path(config.cmdb_path)

    uploaded_process_files = st.file_uploader(
        "BPMN- oder XML-Dateien importieren",
        type=["bpmn", "xml"],
        accept_multiple_files=True,
        key="process_upload",
    )
    uploaded_cmdb_file = st.file_uploader(
        "CMDB-Datei importieren",
        type=["csv"],
        accept_multiple_files=False,
        key="cmdb_upload",
    )

    save_column, run_column = st.columns(2)
    with save_column:
        if st.button("Importdateien speichern", width="stretch"):
            saved_files: list[str] = []
            for uploaded_file in uploaded_process_files or []:
                target_path = process_input_dir / sanitize_uploaded_name(uploaded_file.name)
                save_uploaded_file(target_path, uploaded_file.getvalue())
                saved_files.append(str(target_path))

            if uploaded_cmdb_file is not None:
                save_uploaded_file(cmdb_path, uploaded_cmdb_file.getvalue())
                saved_files.append(str(cmdb_path))

            if saved_files:
                st.success(f"{len(saved_files)} Datei(en) gespeichert.")
                st.rerun()
            else:
                st.info("Keine neuen Dateien zum Speichern ausgewaehlt.")

    with run_column:
        if st.button("Pipeline starten", width="stretch"):
            if not config.llm_model:
                st.warning("Bitte zuerst ein LLM-Modell konfigurieren.")
            else:
                try:
                    run_pipeline(config)
                except Exception as exc:
                    st.error(str(exc))
                else:
                    st.success("Pipeline-Lauf abgeschlossen. Ergebnisse liegen im Output-Ordner.")

    current_process_files = list_process_files(process_input_dir)
    st.caption(f"Aktueller Input-Pfad: `{process_input_dir}`")
    if current_process_files:
        st.write([str(path) for path in current_process_files])
    else:
        st.info("Noch keine BPMN-/XML-Dateien im Input-Pfad vorhanden.")

    st.caption(f"Aktuelle CMDB-Datei: `{cmdb_path}`")
    if cmdb_path.exists():
        st.write(str(cmdb_path))
    else:
        st.info("Noch keine CMDB-Datei vorhanden.")

    runtime_output_path, used_output_fallback = resolve_runtime_output_path(config.output_path)
    st.caption(f"Konfigurierter Output-Pfad: `{resolve_project_path(config.output_path)}`")
    if used_output_fallback:
        st.warning(f"Der konfigurierte Output-Pfad ist aktuell nicht beschreibbar. Artefakte werden nach `{runtime_output_path}` geschrieben.")
    else:
        st.write(str(runtime_output_path))


def main() -> None:
    load_env_files()
    st.set_page_config(page_title="BRIDGR", layout="wide")
    st.title("BRIDGR")
    tabs = st.tabs(["Kommunikation", "Link Editing", "Anwendungskonfig"])
    config_path = Path("config.json")

    with tabs[0]:
        render_query_tab()
    with tabs[1]:
        render_review_tab()
    with tabs[2]:
        render_config_tab(config_path)


if __name__ == "__main__":
    main()

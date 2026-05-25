from __future__ import annotations

from dataclasses import asdict
import os
from pathlib import Path

import streamlit as st

from app_config import AppConfig, load_config, resolve_input_cmdb_path, resolve_project_path, resolve_runtime_output_path, save_config
from cmdb import build_cmdb_option_labels, find_cmdb_row_by_label, load_cmdb_rows
from dialog_utils import pick_directory, pick_file
from env_loader import load_env_files
from import_utils import list_cmdb_files, list_process_files, sanitize_uploaded_name, save_uploaded_file
from knowledge_base import confirm_link, load_knowledge_base, reject_link, save_knowledge_base
from llm_client import LlmClientConfig, LlmClientError, OpenAICompatibleClient
from neo4j_utils import Neo4jClient, Neo4jConfig, Neo4jConnectionError, QueryValidationError
from pipeline import run_pipeline
from query_layer import answer_question
from run_artifacts import load_latest_run
from ui_run_view import (
    build_document_details,
    build_document_status_rows,
    build_review_rows,
    filter_documents,
    summarize_run,
)


def render_query_tab() -> None:
    st.subheader("Kommunikation")
    config = load_config(Path("config.json"))
    question = st.text_input("Frage an den Wissensgraphen", placeholder="Welche Anwendungen unterstuetzt Prozess X?")
    if st.button("Senden", key="send_query"):
        if not question:
            st.warning("Bitte zuerst eine Frage eingeben.")
            return
        if not config.llm_model:
            st.warning("Bitte zuerst ein LLM-Modell konfigurieren.")
            return
        if not config.neo4j_password:
            st.warning("Bitte zuerst die Neo4j-Zugangsdaten konfigurieren.")
            return
        try:
            llm_client = OpenAICompatibleClient(
                LlmClientConfig(
                    base_url=config.llm_base_url,
                    model=config.llm_model,
                    api_key_env=config.llm_api_key_env,
                )
            )
            neo4j_client = Neo4jClient(
                Neo4jConfig(
                    url=config.neo4j_url,
                    user=config.neo4j_user,
                    password=config.neo4j_password,
                    database=config.neo4j_database,
                )
            )
            answer_text, cypher_query, rows = answer_question(
                question=question,
                llm_client=llm_client,
                neo4j_client=neo4j_client,
                cypher_prompt_path=resolve_project_path("prompts/cypher_gen.md"),
                answer_prompt_path=resolve_project_path("prompts/answer_query.md"),
            )
        except (LlmClientError, Neo4jConnectionError, QueryValidationError) as exc:
            st.error(str(exc))
            return
        finally:
            try:
                neo4j_client.close()
            except Exception:
                pass

        st.markdown("**Antwort**")
        st.write(answer_text)
        st.markdown("**Ergebnis**")
        if rows:
            st.dataframe(rows, width="stretch")
        else:
            st.info("Keine Treffer gefunden.")
        with st.expander("Technische Details", expanded=False):
            st.markdown("**Cypher**")
            st.code(cypher_query, language="cypher")


def render_review_tab() -> None:
    st.subheader("Link Editing")
    config = load_config(Path("config.json"))

    action_column, info_column = st.columns([1, 2])
    with action_column:
        if st.button("Pipeline Preview starten", key="review_preview", width="stretch"):
            if not config.llm_model:
                st.warning("Bitte zuerst ein LLM-Modell in Anwendungskonfig konfigurieren.")
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
    cmdb_rows = load_cmdb_rows(resolve_input_cmdb_path(config))
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
    st.subheader("Anwendungskonfig")
    config = load_config(config_path)
    ensure_config_session_defaults(config)

    with st.expander("Import", expanded=False):
        render_import_section(config)

    with st.expander("Konfiguration", expanded=False):
        render_path_picker_controls()

        with st.form("config_form"):
            llm_base_url = st.text_input("LLM Base URL", value=st.session_state["config_llm_base_url"])
            llm_model = st.text_input("LLM Model", value=st.session_state["config_llm_model"])
            llm_api_key_env = st.text_input("API Key Env Var", value=st.session_state["config_llm_api_key_env"])
            llm_context_window = st.number_input("Context Window", min_value=1, value=st.session_state["config_llm_context_window"])
            input_path = st.text_input("Input Path", value=st.session_state["config_input_path"])
            cmdb_filename = st.text_input("CMDB Filename", value=st.session_state["config_cmdb_filename"])
            output_path = st.text_input("Output Path", value=st.session_state["config_output_path"])
            cmdb_uuid_column = st.text_input("CMDB UUID Column", value=config.cmdb_uuid_column)
            cmdb_name_column = st.text_input("CMDB Name Column", value=config.cmdb_name_column)
            neo4j_url = st.text_input("Neo4j URL", value=config.neo4j_url)
            neo4j_user = st.text_input("Neo4j User", value=config.neo4j_user)
            neo4j_password = st.text_input("Neo4j Password", value="", type="password")
            if os.getenv("NEO4J_PASSWORD"):
                st.caption(
                    "Das Feld bleibt absichtlich leer. BRIDGR nutzt aktuell `NEO4J_PASSWORD` aus der Umgebung; "
                    "dieses Feld ist nur fuer eine manuelle Ueberschreibung gedacht und wird nicht automatisch "
                    "mit dem Env-Wert befuellt oder nach `config.json` geschrieben."
                )
            neo4j_database = st.text_input("Neo4j Database", value=config.neo4j_database)
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
                neo4j_password=neo4j_password.strip(),
                neo4j_database=neo4j_database,
                fuzzy_threshold=float(fuzzy_threshold),
                cmdb_uuid_column=cmdb_uuid_column,
                cmdb_name_column=cmdb_name_column,
                input_path=input_path,
                cmdb_filename=cmdb_filename,
                output_path=output_path,
                last_run_mode=last_run_mode,
            )
            save_config(updated_config, config_path)
            update_config_session_defaults(updated_config)
            st.success("Configuration saved.")

        if st.button("Refresh Models"):
            client = OpenAICompatibleClient(
                LlmClientConfig(
                    base_url=st.session_state["config_llm_base_url"],
                    model=st.session_state["config_llm_model"],
                    api_key_env=st.session_state["config_llm_api_key_env"],
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


def ensure_config_session_defaults(config: AppConfig) -> None:
    if "config_llm_base_url" not in st.session_state:
        update_config_session_defaults(config)


def update_config_session_defaults(config: AppConfig) -> None:
    st.session_state["config_llm_base_url"] = config.llm_base_url
    st.session_state["config_llm_model"] = config.llm_model
    st.session_state["config_llm_api_key_env"] = config.llm_api_key_env
    st.session_state["config_llm_context_window"] = config.llm_context_window
    st.session_state["config_input_path"] = config.input_path
    st.session_state["config_cmdb_filename"] = config.cmdb_filename
    st.session_state["config_output_path"] = config.output_path


def render_path_picker_controls() -> None:
    st.markdown("**Pfade auswaehlen**")
    input_column, cmdb_column, output_column = st.columns(3)

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

    if output_column.button("Output-Ordner waehlen", width="stretch"):
        selected_path = pick_directory(st.session_state["config_output_path"])
        if selected_path:
            st.session_state["config_output_path"] = selected_path
            st.rerun()


def render_import_section(config: AppConfig) -> None:
    st.markdown("**Import**")

    input_dir = resolve_project_path(config.input_path)
    cmdb_path = resolve_input_cmdb_path(config)

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
                target_path = input_dir / sanitize_uploaded_name(uploaded_file.name)
                save_uploaded_file(target_path, uploaded_file.getvalue())
                saved_files.append(str(target_path))

            if uploaded_cmdb_file is not None:
                target_path = input_dir / sanitize_uploaded_name(uploaded_cmdb_file.name)
                save_uploaded_file(target_path, uploaded_cmdb_file.getvalue())
                saved_files.append(str(cmdb_path))
                updated_config = AppConfig(**{**asdict(config), "cmdb_filename": sanitize_uploaded_name(uploaded_cmdb_file.name)})
                save_config(updated_config)
                update_config_session_defaults(updated_config)

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
                    runtime_config = AppConfig(
                        **{
                            **asdict(config),
                            "cmdb_filename": st.session_state.get("active_cmdb_filename", config.cmdb_filename),
                        }
                    )
                    run_pipeline(runtime_config)
                except Exception as exc:
                    st.error(str(exc))
                else:
                    st.success("Pipeline-Lauf abgeschlossen. Ergebnisse liegen im Output-Ordner.")

    current_process_files = list_process_files(input_dir)
    current_cmdb_files = list_cmdb_files(input_dir)
    ensure_active_cmdb_selection(config, current_cmdb_files)

    st.caption(f"Aktueller Input-Pfad: `{input_dir}`")
    if current_process_files:
        st.write([str(path) for path in current_process_files])
    else:
        st.info("Noch keine BPMN-/XML-Dateien im Input-Pfad vorhanden.")

    st.caption("Verfuegbare CMDB-Dateien im Input-Pfad")
    if current_cmdb_files:
        selected_cmdb_filename = st.selectbox(
            "Aktive CMDB-Datei",
            options=[path.name for path in current_cmdb_files],
            key="active_cmdb_filename",
        )
        if st.button("Aktive CMDB-Datei uebernehmen", width="stretch"):
            updated_config = AppConfig(**{**asdict(config), "cmdb_filename": selected_cmdb_filename})
            save_config(updated_config)
            update_config_session_defaults(updated_config)
            st.success(f"Aktive CMDB-Datei auf '{selected_cmdb_filename}' gesetzt.")
            st.rerun()
    else:
        st.info("Noch keine CMDB-Datei im Input-Pfad vorhanden.")

    runtime_output_path, used_output_fallback = resolve_runtime_output_path(config.output_path)
    st.caption(f"Konfigurierter Output-Pfad: `{resolve_project_path(config.output_path)}`")
    if used_output_fallback:
        st.warning(f"Der konfigurierte Output-Pfad ist aktuell nicht beschreibbar. Artefakte werden nach `{runtime_output_path}` geschrieben.")
    else:
        st.write(str(runtime_output_path))


def ensure_active_cmdb_selection(config: AppConfig, cmdb_files: list[Path]) -> None:
    available_filenames = [path.name for path in cmdb_files]
    if "active_cmdb_filename" not in st.session_state:
        st.session_state["active_cmdb_filename"] = config.cmdb_filename
    if available_filenames and st.session_state["active_cmdb_filename"] not in available_filenames:
        st.session_state["active_cmdb_filename"] = available_filenames[0]


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

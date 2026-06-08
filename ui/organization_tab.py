from __future__ import annotations

from pathlib import Path

import streamlit as st

from core.app_config import load_config
from processing.knowledge_base import load_knowledge_base
from core.neo4j_utils import Neo4jConnectionError, Neo4jQueryError
from services.organization_service import (
    accept_org_candidate,
    accept_process_owner_candidate,
    add_org_unit_entry,
    assign_role_to_org_unit,
    clear_process_owner,
    load_all_processes_with_owner,
    load_process_owner_candidates,
    load_unassigned_roles,
    mark_role_as_role_only,
    map_org_candidate,
    persist_organization_sync,
    reject_org_candidate,
    reject_process_owner_candidate,
    set_process_owner,
)


def render_organization_tab() -> None:
    st.subheader("Organisation")
    config = load_config(Path("config.json"))
    knowledge_base = load_knowledge_base()
    org_units = sorted(knowledge_base.org_units, key=lambda entry: entry.get("name", "").casefold())

    try:
        all_processes = load_all_processes_with_owner(config)
    except Exception:
        all_processes = []

    _render_org_units_section(config, knowledge_base, org_units, all_processes)
    _render_candidates_section(config, knowledge_base, org_units)
    _render_process_owner_candidates_section(config, org_units)
    _render_process_owner_section(config, org_units, all_processes)
    _render_unassigned_roles_section(config, org_units)
    _render_decided_candidates_section(knowledge_base)


def _render_org_units_section(config, knowledge_base, org_units, all_processes) -> None:
    with st.expander("Organisationseinheiten", expanded=False):
        if not org_units:
            st.info("Noch keine Organisationseinheiten gepflegt.")
        else:
            if st.button("Organisation nach Neo4j synchronisieren", key="org-sync-neo4j", width="stretch"):
                try:
                    synced_org_units, refreshed_documents = persist_organization_sync(config)
                except (Neo4jConnectionError, Neo4jQueryError) as exc:
                    st.error(f"Organisation konnte nicht nach Neo4j synchronisiert werden: {exc}")
                else:
                    if refreshed_documents:
                        st.success(
                            f"{synced_org_units} Organisationseinheit(en) synchronisiert. "
                            f"{refreshed_documents} Dokument(e) aus dem letzten Lauf wurden für Prozessbeziehungen neu eingespielt."
                        )
                    else:
                        st.success(f"{synced_org_units} Organisationseinheit(en) nach Neo4j synchronisiert.")
                st.rerun()

            for org_unit in org_units:
                org_unit_name = org_unit.get("name", "")
                org_key = org_unit_name.casefold().replace(" ", "_")
                with st.container(border=True):
                    header_cols = st.columns([3, 1])
                    header_cols[0].markdown(f"**{org_unit_name}**")
                    header_cols[0].caption(
                        f"Quelle: {org_unit.get('source', '')} | Angelegt: {org_unit.get('created_at', '')}"
                    )
                    with header_cols[1]:
                        manage_key = f"org-manage-toggle::{org_key}"
                        if st.button("Prozesse verwalten", key=manage_key, width="stretch"):
                            toggle_key = f"org-manage-open::{org_key}"
                            st.session_state[toggle_key] = not st.session_state.get(toggle_key, False)
                            st.rerun()

                    toggle_key = f"org-manage-open::{org_key}"
                    if st.session_state.get(toggle_key, False):
                        _render_process_manager_for_org_unit(config, org_unit_name, org_key, all_processes)

        with st.form("organization-add-form"):
            new_org_unit_name = st.text_input("Neue Organisationseinheit")
            add_submitted = st.form_submit_button("Organisationseinheit hinzufügen")
        if add_submitted:
            level, message = add_org_unit_entry(config, knowledge_base, new_org_unit_name)
            getattr(st, level)(message)
            st.rerun()


def _render_process_manager_for_org_unit(config, org_unit_name: str, org_key: str, all_processes: list[dict]) -> None:
    if not all_processes:
        st.caption("Keine Prozesse im Graphen gefunden.")
        return

    owned_by_me = {p["prozess_id"] for p in all_processes if p["eigentuemer"] == org_unit_name}

    def process_label(p: dict) -> str:
        if p["eigentuemer"] and p["eigentuemer"] != org_unit_name:
            return f"{p['prozess']} (→ {p['eigentuemer']})"
        return p["prozess"]

    process_options = [p["prozess_id"] for p in all_processes]
    process_labels = {p["prozess_id"]: process_label(p) for p in all_processes}

    default_selection = [pid for pid in process_options if pid in owned_by_me]

    with st.form(key=f"org-process-form::{org_key}"):
        selected_ids = st.multiselect(
            "Verantwortliche Prozesse",
            options=process_options,
            default=default_selection,
            format_func=lambda pid: process_labels.get(pid, pid),
            key=f"org-process-select::{org_key}",
        )
        submitted = st.form_submit_button("Speichern")

    if submitted:
        newly_added = set(selected_ids) - owned_by_me
        newly_removed = owned_by_me - set(selected_ids)
        errors: list[str] = []
        for pid in newly_added:
            level, message = set_process_owner(config, pid, org_unit_name)
            if level != "success":
                errors.append(message)
        for pid in newly_removed:
            clear_process_owner(config, pid)
        if errors:
            st.error(" | ".join(errors))
        else:
            st.success(f"{len(newly_added)} zugewiesen, {len(newly_removed)} entfernt.")
        st.rerun()


def _render_process_owner_section(config, org_units, all_processes: list[dict]) -> None:
    with st.expander("Prozesse ohne Eigentümer", expanded=False):
        if not all_processes:
            st.info("Keine Prozesse im Graphen gefunden.")
            return

        ownerless = [p for p in all_processes if not p["eigentuemer"]]
        if not ownerless:
            st.info("Alle Prozesse haben einen Eigentümer.")
            return

        existing_org_unit_names = [entry.get("name", "") for entry in org_units if entry.get("name")]
        if not existing_org_unit_names:
            st.info("Noch keine Organisationseinheiten vorhanden. Bitte zuerst Kandidaten bestätigen oder eine Organisationseinheit anlegen.")
            return

        with st.form("process-owner-batch-form"):
            process_options = [process["prozess_id"] for process in ownerless]
            process_labels = {
                process["prozess_id"]: (process["prozess"] or process["prozess_id"])
                for process in ownerless
            }
            selected_process_ids = st.multiselect(
                "Mehrere Prozesse gleichzeitig zuweisen",
                options=process_options,
                format_func=lambda process_id: process_labels.get(process_id, process_id),
                key="proc-owner-batch-selection",
            )
            batch_columns = st.columns([3, 1])
            batch_owner = batch_columns[0].selectbox(
                "Gemeinsamer Eigentümer",
                options=[""] + existing_org_unit_names,
                key="proc-owner-batch-owner",
            )
            batch_submitted = batch_columns[1].form_submit_button("Batch zuweisen", width="stretch")
        if batch_submitted:
            if not selected_process_ids:
                st.warning("Bitte mindestens einen Prozess auswählen.")
            elif not batch_owner:
                st.warning("Bitte eine Organisationseinheit auswählen.")
            else:
                errors: list[str] = []
                for process_id in selected_process_ids:
                    level, message = set_process_owner(config, process_id, batch_owner)
                    if level != "success":
                        errors.append(message)
                if errors:
                    st.error(" | ".join(errors))
                else:
                    st.success(f"{len(selected_process_ids)} Prozess(e) wurden \"{batch_owner}\" zugeordnet.")
                st.rerun()

        for process in ownerless:
            process_id = process["prozess_id"]
            process_name = process["prozess"] or process_id
            proc_key = (process_id or process_name).replace(" ", "_").replace("/", "_")
            with st.container(border=True):
                st.markdown(f"**{process_name}**")
                cols = st.columns([3, 1])
                selected_owner = cols[0].selectbox(
                    "Eigentümer zuweisen",
                    options=[""] + existing_org_unit_names,
                    key=f"proc-owner-select::{proc_key}",
                )
                if cols[1].button("Zuweisen", key=f"proc-owner-assign::{proc_key}", width="stretch"):
                    if not selected_owner:
                        st.warning("Bitte eine Organisationseinheit auswählen.")
                    else:
                        level, message = set_process_owner(config, process_id, selected_owner)
                        getattr(st, level)(message)
                        st.rerun()


def _render_process_owner_candidates_section(config, org_units) -> None:
    with st.expander("Vorgeschlagene Prozess-Eigentümer", expanded=False):
        try:
            candidates = load_process_owner_candidates(config)
        except Exception as exc:
            st.warning(f"Vorgeschlagene Prozess-Eigentümer konnten nicht geladen werden: {exc}")
            return

        if not candidates:
            st.info("Aktuell liegen keine vorgeschlagenen Prozess-Eigentümer vor.")
            return

        existing_org_unit_names = [entry.get("name", "") for entry in org_units if entry.get("name")]
        st.caption("Bestätigte oder neu angelegte Organisationseinheiten stehen nach dem nächsten Rerun direkt in den folgenden Auswahllisten zur Verfügung.")
        for candidate in candidates:
            process_id = candidate["process_id"]
            process_name = candidate["process_name"] or process_id
            suggested = candidate["candidate_org_unit"]
            source = Path(candidate.get("source_path", "")).name
            cand_key = (process_id or process_name).replace(" ", "_").replace("/", "_")
            with st.container(border=True):
                st.markdown(f"**{process_name}**")
                st.caption(f"Vorgeschlagener Eigentümer: **{suggested}** | Quelle: {source}")
                cols = st.columns([2, 1, 1])
                selected_org = cols[0].selectbox(
                    "Organisationseinheit bestätigen",
                    options=[""] + existing_org_unit_names,
                    index=(existing_org_unit_names.index(suggested) + 1) if suggested in existing_org_unit_names else 0,
                    key=f"poc-select::{cand_key}",
                )
                if cols[1].button("Bestätigen", key=f"poc-accept::{cand_key}", width="stretch"):
                    target = selected_org or suggested
                    level, message = accept_process_owner_candidate(config, process_id, target)
                    getattr(st, level)(message)
                    st.rerun()
                if cols[2].button("Abweisen", key=f"poc-reject::{cand_key}", width="stretch"):
                    level, message = reject_process_owner_candidate(config, process_id)
                    getattr(st, level)(message)
                    st.rerun()


def _render_candidates_section(config, knowledge_base, org_units) -> None:
    with st.expander("Kandidaten", expanded=False):
        open_candidates = [
            entry
            for entry in knowledge_base.org_unit_candidates
            if entry.get("status", "open") == "open"
        ]
        if not open_candidates:
            st.info("Aktuell liegen keine offenen Kandidaten vor.")
            return

        existing_org_unit_options = [entry.get("name", "") for entry in org_units if entry.get("name")]
        for candidate in sorted(open_candidates, key=lambda entry: entry.get("candidate_name", "").casefold()):
            candidate_name = candidate.get("candidate_name", "")
            candidate_key = candidate.get("normalized_name", candidate_name.casefold())
            with st.container(border=True):
                st.markdown(f"**{candidate_name}**")
                process_names = ", ".join(candidate.get("process_names", [])) or "-"
                role_names = ", ".join(candidate.get("role_names", [])) or "-"
                source_paths = ", ".join(Path(path).name for path in candidate.get("source_paths", [])) or "-"
                st.caption(f"Prozesse: {process_names}")
                st.caption(f"Rollen: {role_names}")
                st.caption(f"Quellen: {source_paths}")

                action_columns = st.columns([2, 1, 2, 1, 1])
                selected_target = action_columns[0].selectbox(
                    "Bestehende Organisationseinheit",
                    options=[""] + existing_org_unit_options,
                    key=f"org-candidate-select::{candidate_key}",
                )
                if action_columns[1].button("Zuordnen", key=f"org-candidate-map::{candidate_key}", width="stretch"):
                    if not selected_target:
                        st.warning("Bitte zuerst eine bestehende Organisationseinheit auswählen.")
                    else:
                        level, message = map_org_candidate(config, knowledge_base, candidate_name, selected_target)
                        getattr(st, level)(message)
                        st.rerun()

                proposed_name = action_columns[2].text_input(
                    "Als neue Organisationseinheit übernehmen",
                    value=candidate_name,
                    key=f"org-candidate-new::{candidate_key}",
                )
                if action_columns[3].button("Übernehmen", key=f"org-candidate-accept::{candidate_key}", width="stretch"):
                    level, message = accept_org_candidate(config, knowledge_base, candidate_name, proposed_name)
                    getattr(st, level)(message)
                    st.rerun()

                if action_columns[4].button("Abweisen", key=f"org-candidate-reject::{candidate_key}", width="stretch"):
                    level, message = reject_org_candidate(knowledge_base, candidate_name)
                    getattr(st, level)(message)
                    st.rerun()


def _render_unassigned_roles_section(config, org_units) -> None:
    with st.expander("Nicht zugeordnete Rollen", expanded=False):
        try:
            unassigned_roles = load_unassigned_roles(config)
        except Exception as exc:
            st.warning(f"Rollen konnten nicht aus Neo4j geladen werden: {exc}")
            return

        if not unassigned_roles:
            st.info("Alle Rollen sind bereits einer Organisationseinheit zugeordnet oder wurden als reine Rolle markiert.")
            return

        existing_org_unit_names = [entry.get("name", "") for entry in org_units if entry.get("name")]
        st.caption("Mit \"Rolle\" blendest du Begriffe aus, die bewusst keine Organisationseinheit darstellen.")
        for role_entry in unassigned_roles:
            role_name = role_entry["rolle"]
            process_names = ", ".join(role_entry.get("prozesse", [])) or "-"
            role_key = role_name.casefold().replace(" ", "_")
            with st.container(border=True):
                st.markdown(f"**{role_name}**")
                st.caption(f"Prozesse: {process_names}")
                assign_columns = st.columns([2, 1, 2, 1, 1])
                selected_org = assign_columns[0].selectbox(
                    "Bestehende Organisationseinheit",
                    options=[""] + existing_org_unit_names,
                    key=f"role-assign-existing::{role_key}",
                )
                if assign_columns[1].button("Zuordnen", key=f"role-assign-map::{role_key}", width="stretch"):
                    if not selected_org:
                        st.warning("Bitte zuerst eine bestehende Organisationseinheit auswählen.")
                    else:
                        level, message = assign_role_to_org_unit(config, role_name, selected_org)
                        getattr(st, level)(message)
                        st.rerun()
                new_org_name = assign_columns[2].text_input(
                    "Als neue Organisationseinheit anlegen",
                    value=role_name,
                    key=f"role-assign-new::{role_key}",
                )
                if assign_columns[3].button("Anlegen & zuordnen", key=f"role-assign-create::{role_key}", width="stretch"):
                    if not new_org_name.strip():
                        st.warning("Bitte einen Namen für die neue Organisationseinheit eingeben.")
                    else:
                        level, message = assign_role_to_org_unit(config, role_name, new_org_name)
                        getattr(st, level)(message)
                        st.rerun()
                if assign_columns[4].button("Rolle", key=f"role-only::{role_key}", width="stretch"):
                    level, message = mark_role_as_role_only(role_name)
                    getattr(st, level)(message)
                    st.rerun()


def _render_decided_candidates_section(knowledge_base) -> None:
    with st.expander("Bereits entschiedene Kandidaten", expanded=False):
        decided_candidates = [
            entry
            for entry in knowledge_base.org_unit_candidates
            if entry.get("status", "open") != "open"
        ]
        if not decided_candidates:
            st.info("Noch keine entschiedenen Kandidaten vorhanden.")
        else:
            st.dataframe(
                [
                    {
                        "Kandidat": entry.get("candidate_name", ""),
                        "Status": entry.get("status", ""),
                        "Gemappt auf": entry.get("mapped_org_unit", ""),
                        "Zuletzt gesehen": entry.get("last_seen", ""),
                    }
                    for entry in decided_candidates
                ],
                width="stretch",
            )

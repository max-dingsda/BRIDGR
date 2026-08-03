from __future__ import annotations

import json
from pathlib import Path

import streamlit as st

from core.app_config import load_config
from core.neo4j_utils import Neo4jConnectionError, Neo4jQueryError
from services.correction_service import revert_manual_decision
from services.decision_service import list_recent_manual_decisions
from services.merge_service import (
    get_org_unit_merge_preview,
    get_process_merge_preview,
    load_process_merge_candidates,
    merge_org_units,
    merge_processes,
)
from services.organization_service import (
    accept_org_candidate,
    accept_process_owner_candidate,
    add_org_unit_entry,
    assign_role_to_org_unit,
    clear_process_owner,
    load_all_processes_with_owner,
    load_org_units_from_neo4j,
    load_process_owner_candidates,
    load_unassigned_roles,
    mark_role_as_role_only,
    map_org_candidate,
    persist_organization_sync,
    reject_org_candidate,
    reject_process_owner_candidate,
    set_process_owner,
)
from services.runtime_service import get_session_neo4j_client
from services.runtime_service import (
    ORGANIZATION_RUN_FEEDBACK_STATE_KEY,
    render_run_feedback,
    set_run_feedback,
)
from skills.graph_writer import GraphWriter, normalize_org_unit_name
from ui.layout import render_page_header


def render_organization_tab() -> None:
    render_page_header(
        "Organisation",
        "Verwalten Sie Organisationseinheiten, Eigentümer, Rollen sowie manuelle Korrekturen und Konsolidierungen im Graphen.",
        "Kandidaten, Eigentümer und Merge",
    )
    render_run_feedback(ORGANIZATION_RUN_FEEDBACK_STATE_KEY)
    config = load_config(Path("config.json"))

    try:
        org_units = sorted(load_org_units_from_neo4j(config), key=lambda e: e.get("name", "").casefold())
    except Exception:
        org_units = []

    try:
        all_processes = load_all_processes_with_owner(config)
    except Exception:
        all_processes = []

    _render_org_units_section(config, org_units, all_processes)
    _render_candidates_section(config, org_units)
    _render_process_owner_candidates_section(config, org_units)
    _render_process_owner_section(config, org_units, all_processes)
    _render_unassigned_roles_section(config, org_units)
    _render_recent_decisions_section(config)
    _render_org_unit_merge_section(config, org_units)
    _render_process_merge_section(config)
    _render_decided_candidates_section(config)


def _build_role_assignment_options(org_units: list[dict], role_name: str) -> tuple[list[str], str]:
    normalized_role_name = normalize_org_unit_name(role_name)
    existing_org_unit_names = [
        entry.get("name", "")
        for entry in org_units
        if entry.get("name") and normalize_org_unit_name(entry.get("name", "")) != normalized_role_name
    ]
    suggested_new_org_name = "" if any(
        entry.get("name") and normalize_org_unit_name(entry.get("name", "")) == normalized_role_name
        for entry in org_units
    ) else role_name
    return existing_org_unit_names, suggested_new_org_name


_SECTION_ORG_UNITS = "org_section_org_units_open"
_SECTION_CANDIDATES = "org_section_candidates_open"
_SECTION_PROCESS_OWNER_CANDIDATES = "org_section_process_owner_candidates_open"
_SECTION_PROCESS_OWNER = "org_section_process_owner_open"
_SECTION_ROLES = "org_section_roles_open"
_SECTION_DECIDED = "org_section_decided_open"
_SECTION_RECENT_DECISIONS = "org_section_recent_decisions_open"
_SECTION_MERGE = "org_section_merge_open"
_SECTION_PROCESS_MERGE = "org_section_process_merge_open"


def _rerun_keep(section_key: str) -> None:
    st.session_state[section_key] = True
    st.rerun()


def _render_org_units_section(config, org_units, all_processes) -> None:
    with st.expander("Organisationseinheiten", expanded=st.session_state.get(_SECTION_ORG_UNITS, False)):
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
                _rerun_keep(_SECTION_ORG_UNITS)

            for org_unit in org_units:
                org_unit_name = org_unit.get("name", "")
                org_key = org_unit_name.casefold().replace(" ", "_")
                with st.container(border=True):
                    header_cols = st.columns([3, 1])
                    header_cols[0].markdown(f"**{org_unit_name}**")
                    with header_cols[1]:
                        manage_key = f"org-manage-toggle::{org_key}"
                        if st.button("Prozesse verwalten", key=manage_key, width="stretch"):
                            toggle_key = f"org-manage-open::{org_key}"
                            st.session_state[toggle_key] = not st.session_state.get(toggle_key, False)
                            _rerun_keep(_SECTION_ORG_UNITS)

                    toggle_key = f"org-manage-open::{org_key}"
                    if st.session_state.get(toggle_key, False):
                        _render_process_manager_for_org_unit(config, org_unit_name, org_key, all_processes)

        with st.form("organization-add-form"):
            new_org_unit_name = st.text_input("Neue Organisationseinheit")
            add_submitted = st.form_submit_button("Organisationseinheit hinzufügen")
        if add_submitted:
            level, message = add_org_unit_entry(config, new_org_unit_name)
            getattr(st, level)(message)
            _rerun_keep(_SECTION_ORG_UNITS)


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
            process_name = process_labels.get(pid, pid)
            level, message = set_process_owner(config, pid, org_unit_name, process_name=process_name)
            if level != "success":
                errors.append(message)
        for pid in newly_removed:
            clear_process_owner(config, pid)
        if errors:
            st.error(" | ".join(errors))
        else:
            st.success(f"{len(newly_added)} zugewiesen, {len(newly_removed)} entfernt.")
        _rerun_keep(_SECTION_ORG_UNITS)


def _render_process_owner_section(config, org_units, all_processes: list[dict]) -> None:
    ownerless = [p for p in all_processes if not p["eigentuemer"]]
    with st.expander(f"Prozesse ohne Eigentümer ({len(ownerless)})", expanded=st.session_state.get(_SECTION_PROCESS_OWNER, False)):
        if not all_processes:
            st.info("Keine Prozesse im Graphen gefunden.")
            return

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
                    process_name = process_labels.get(process_id, process_id)
                    level, message = set_process_owner(config, process_id, batch_owner, process_name=process_name)
                    if level != "success":
                        errors.append(message)
                if errors:
                    st.error(" | ".join(errors))
                else:
                    st.success(f"{len(selected_process_ids)} Prozess(e) wurden \"{batch_owner}\" zugeordnet.")
                _rerun_keep(_SECTION_PROCESS_OWNER)

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
                        level, message = set_process_owner(config, process_id, selected_owner, process_name=process_name)
                        getattr(st, level)(message)
                        _rerun_keep(_SECTION_PROCESS_OWNER)


def _render_process_owner_candidates_section(config, org_units) -> None:
    _load_error: Exception | None = None
    try:
        candidates = load_process_owner_candidates(config)
    except Exception as exc:
        candidates = []
        _load_error = exc

    with st.expander(f"Vorgeschlagene Prozess-Eigentümer ({len(candidates)})", expanded=st.session_state.get(_SECTION_PROCESS_OWNER_CANDIDATES, False)):
        if _load_error:
            st.warning(f"Vorgeschlagene Prozess-Eigentümer konnten nicht geladen werden: {_load_error}")
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
                    level, message = accept_process_owner_candidate(config, process_id, target, process_name=process_name)
                    getattr(st, level)(message)
                    _rerun_keep(_SECTION_PROCESS_OWNER_CANDIDATES)
                if cols[2].button("Abweisen", key=f"poc-reject::{cand_key}", width="stretch"):
                    level, message = reject_process_owner_candidate(config, process_id)
                    getattr(st, level)(message)
                    _rerun_keep(_SECTION_PROCESS_OWNER_CANDIDATES)


def _render_candidates_section(config, org_units) -> None:
    graph_writer = GraphWriter()
    neo4j_client = get_session_neo4j_client(config)
    open_candidates = graph_writer.load_org_unit_candidates(neo4j_client, status="open")
    with st.expander(f"Kandidaten ({len(open_candidates)})", expanded=st.session_state.get(_SECTION_CANDIDATES, False)):
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
                        level, message = map_org_candidate(config, candidate_name, selected_target)
                        getattr(st, level)(message)
                        _rerun_keep(_SECTION_CANDIDATES)

                proposed_name = action_columns[2].text_input(
                    "Als neue Organisationseinheit übernehmen",
                    value=candidate_name,
                    key=f"org-candidate-new::{candidate_key}",
                )
                if action_columns[3].button("Übernehmen", key=f"org-candidate-accept::{candidate_key}", width="stretch"):
                    level, message = accept_org_candidate(config, candidate_name, proposed_name)
                    getattr(st, level)(message)
                    _rerun_keep(_SECTION_CANDIDATES)

                if action_columns[4].button("Abweisen", key=f"org-candidate-reject::{candidate_key}", width="stretch"):
                    level, message = reject_org_candidate(config, candidate_name)
                    getattr(st, level)(message)
                    _rerun_keep(_SECTION_CANDIDATES)


def _render_unassigned_roles_section(config, org_units) -> None:
    _load_error: Exception | None = None
    try:
        unassigned_roles = load_unassigned_roles(config)
    except Exception as exc:
        unassigned_roles = []
        _load_error = exc

    with st.expander(f"Nicht zugeordnete Rollen ({len(unassigned_roles)})", expanded=st.session_state.get(_SECTION_ROLES, False)):
        if _load_error:
            st.warning(f"Rollen konnten nicht aus Neo4j geladen werden: {_load_error}")
            return

        if not unassigned_roles:
            st.info("Alle Rollen sind bereits einer Organisationseinheit zugeordnet oder wurden als reine Rolle markiert.")
            return

        st.caption("Mit \"Rolle\" blendest du Begriffe aus, die bewusst keine Organisationseinheit darstellen.")
        for role_entry in unassigned_roles:
            role_name = role_entry["rolle"]
            process_names = ", ".join(role_entry.get("prozesse", [])) or "-"
            role_key = role_name.casefold().replace(" ", "_")
            existing_org_unit_names, suggested_new_org_name = _build_role_assignment_options(org_units, role_name)
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
                        _rerun_keep(_SECTION_ROLES)
                new_org_name = assign_columns[2].text_input(
                    "Als neue Organisationseinheit anlegen",
                    value=suggested_new_org_name,
                    key=f"role-assign-new::{role_key}",
                )
                if assign_columns[3].button("Anlegen & zuordnen", key=f"role-assign-create::{role_key}", width="stretch"):
                    if not new_org_name.strip():
                        st.warning("Bitte einen Namen für die neue Organisationseinheit eingeben.")
                    else:
                        level, message = assign_role_to_org_unit(config, role_name, new_org_name)
                        getattr(st, level)(message)
                        _rerun_keep(_SECTION_ROLES)
                if assign_columns[4].button("Rolle", key=f"role-only::{role_key}", width="stretch"):
                    level, message = mark_role_as_role_only(config, role_name)
                    getattr(st, level)(message)
                    _rerun_keep(_SECTION_ROLES)


def _render_decided_candidates_section(config) -> None:
    with st.expander("Bereits entschiedene Kandidaten", expanded=False):
        graph_writer = GraphWriter()
        neo4j_client = get_session_neo4j_client(config)
        decided_candidates = [
            entry
            for status in ("mapped", "rejected")
            for entry in graph_writer.load_org_unit_candidates(neo4j_client, status=status)
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


def _describe_manual_decision(decision) -> str:
    if decision.decision_type == "manual_link":
        return "Manueller Anwendungslink"
    if decision.decision_type == "confirmed_candidate_link":
        return "Bestätigter Anwendungskandidat"
    if decision.decision_type == "manual_process_owner_assignment":
        return "Manuelle Prozess-Eigentümerzuordnung"
    if decision.decision_type == "manual_role_assignment":
        return "Manuelle Rollenzuordnung"
    if decision.decision_type == "entity_merge":
        return "Objekt-Merge"
    if decision.decision_type == "decision_revert":
        return "Rücknahme einer Entscheidung"
    return decision.decision_type


def _describe_manual_decision_context(decision) -> str:
    try:
        payload = json.loads(getattr(decision, "payload_json", "") or "{}")
    except json.JSONDecodeError:
        return ""

    if decision.decision_type == "manual_process_owner_assignment":
        process_id = str(payload.get("process_id", "")).strip()
        process_name = str(payload.get("process_name", "")).strip()
        org_unit_name = str(payload.get("org_unit_name", "")).strip()
        process_label = process_name or process_id
        if process_label or org_unit_name:
            return f"Prozess: {process_label or '-'} | Eigentümer: {org_unit_name or '-'}"

    if decision.decision_type == "manual_role_assignment":
        role_name = str(payload.get("role_name", "")).strip()
        org_unit_name = str(payload.get("org_unit_name", "")).strip()
        if role_name or org_unit_name:
            return f"Rolle: {role_name or '-'} | Organisationseinheit: {org_unit_name or '-'}"

    if decision.decision_type in {"manual_link", "confirmed_candidate_link"}:
        process_id = str(payload.get("process_id", "")).strip()
        application_name = str(payload.get("application_name", "")).strip()
        matched_name = str(payload.get("matched_name", "")).strip()
        if process_id or application_name or matched_name:
            return (
                f"Prozess: {process_id or '-'} | Begriff: {application_name or '-'}"
                f" | Ziel: {matched_name or '-'}"
            )

    if decision.decision_type == "entity_merge":
        entity_type = str(payload.get("entity_type", "")).strip()
        source_name = str(payload.get("source_name", "")).strip()
        target_name = str(payload.get("target_name", "")).strip()
        if entity_type or source_name or target_name:
            return f"Typ: {entity_type or '-'} | Quelle: {source_name or '-'} | Ziel: {target_name or '-'}"

    if decision.decision_type == "decision_revert":
        reverted_type = str(payload.get("reverted_type", "")).strip()
        reverted_decision_id = str(payload.get("reverted_decision_id", "")).strip()
        if reverted_type or reverted_decision_id:
            return f"Zurückgenommen: {reverted_type or '-'} | Ursprungs-ID: {reverted_decision_id or '-'}"

    return ""


def _render_recent_decisions_section(config) -> None:
    load_error: Exception | None = None
    try:
        decisions = list_recent_manual_decisions(get_session_neo4j_client(config), limit=15)
    except Exception as exc:
        decisions = []
        load_error = exc

    with st.expander("Letzte manuelle Änderungen", expanded=st.session_state.get(_SECTION_RECENT_DECISIONS, False)):
        if load_error:
            st.warning(f"Manuelle Änderungen konnten nicht geladen werden: {load_error}")
            return
        if not decisions:
            st.info("Noch keine manuellen Änderungen im Entscheidungslog vorhanden.")
            return

        st.caption("Hier können gezielt nachvollziehbare manuelle Eingriffe zurückgenommen werden.")
        for decision in decisions:
            with st.container(border=True):
                cols = st.columns([4, 2, 1])
                cols[0].markdown(f"**{_describe_manual_decision(decision)}**")
                context = _describe_manual_decision_context(decision)
                if context:
                    cols[0].caption(context)
                cols[1].caption(f"Status: {decision.status}")
                cols[1].caption(f"Zeitpunkt: {decision.created_at}")
                if _decision_is_revertable(decision) and cols[2].button("Zurücknehmen", key=f"decision-revert::{decision.decision_id}", width="stretch"):
                    level, message = revert_manual_decision(config, decision.decision_id)
                    set_run_feedback(ORGANIZATION_RUN_FEEDBACK_STATE_KEY, level, message)
                    _rerun_keep(_SECTION_RECENT_DECISIONS)


def _render_org_unit_merge_section(config, org_units) -> None:
    existing_org_unit_names = [entry.get("name", "") for entry in org_units if entry.get("name")]
    with st.expander("Organisationseinheiten konsolidieren", expanded=st.session_state.get(_SECTION_MERGE, False)):
        if len(existing_org_unit_names) < 2:
            st.info("Für einen Merge werden mindestens zwei Organisationseinheiten benötigt.")
            return

        st.caption(
            "Verwenden Sie diesen Bereich, um Dubletten zusammenzuführen. "
            "Der Quellname wird als Alias des Zielobjekts weitergeführt."
        )
        source_name = st.selectbox(
            "Quelle",
            options=[""] + existing_org_unit_names,
            key="org-merge-source",
        )
        target_options = [""] + [name for name in existing_org_unit_names if name != source_name]
        target_name = st.selectbox(
            "Ziel",
            options=target_options,
            key="org-merge-target",
        )

        if source_name and target_name:
            _render_merge_precheck(
                lambda: get_org_unit_merge_preview(config, source_name, target_name),
                key_prefix="org-merge-precheck",
            )

        if st.button("Merge ausführen", key="org-merge-submit", width="stretch"):
            if not source_name or not target_name:
                st.warning("Bitte Quelle und Ziel auswählen.")
            else:
                level, message = merge_org_units(config, source_name, target_name)
                set_run_feedback(ORGANIZATION_RUN_FEEDBACK_STATE_KEY, level, message)
                _rerun_keep(_SECTION_MERGE)


def _render_process_merge_section(config) -> None:
    load_error: Exception | None = None
    try:
        process_candidates = load_process_merge_candidates(config)
    except Exception as exc:
        process_candidates = []
        load_error = exc

    with st.expander("Prozesse konsolidieren", expanded=st.session_state.get(_SECTION_PROCESS_MERGE, False)):
        if load_error:
            st.warning(f"Prozesse konnten nicht geladen werden: {load_error}")
            return
        if len(process_candidates) < 2:
            st.info("Für einen Merge werden mindestens zwei Prozesse benötigt.")
            return

        process_options = [entry["element_id"] for entry in process_candidates]
        process_labels = {
            entry["element_id"]: (
                f"{entry.get('process_name', '')} [{entry.get('process_id', '')}]"
                if entry.get("process_id")
                else entry.get("process_name", "") or entry["element_id"]
            )
            for entry in process_candidates
        }

        source_ref = st.selectbox(
            "Prozess-Quelle",
            options=[""] + process_options,
            format_func=lambda element_id: process_labels.get(element_id, element_id),
            key="process-merge-source",
        )
        target_ref = st.selectbox(
            "Prozess-Ziel",
            options=[""] + [option for option in process_options if option != source_ref],
            format_func=lambda element_id: process_labels.get(element_id, element_id),
            key="process-merge-target",
        )

        if source_ref and target_ref:
            _render_merge_precheck(
                lambda: get_process_merge_preview(config, source_ref, target_ref),
                key_prefix="process-merge-precheck",
            )

        if st.button("Prozess-Merge ausführen", key="process-merge-submit", width="stretch"):
            if not source_ref or not target_ref:
                st.warning("Bitte Quelle und Ziel auswählen.")
            else:
                level, message = merge_processes(config, source_ref, target_ref)
                set_run_feedback(ORGANIZATION_RUN_FEEDBACK_STATE_KEY, level, message)
                _rerun_keep(_SECTION_PROCESS_MERGE)


def _render_merge_precheck(load_preview, *, key_prefix: str) -> None:
    try:
        preview = load_preview()
    except Exception as exc:
        st.warning(f"Precheck konnte nicht geladen werden: {exc}")
        return

    outgoing_duplicates = [
        rel for rel in preview.source_outgoing if _relationship_key(rel) in set(preview.target_outgoing_keys)
    ]
    incoming_duplicates = [
        rel for rel in preview.source_incoming if _relationship_key(rel) in set(preview.target_incoming_keys)
    ]
    property_conflicts = _build_property_conflicts(preview)

    st.info(
        f"Precheck für {preview.entity_type}: Quelle **{preview.source_name or preview.source_ref}** "
        f"→ Ziel **{preview.target_name or preview.target_ref}**"
    )

    summary_cols = st.columns(4)
    summary_cols[0].metric("Ausgehende Kanten", len(preview.source_outgoing))
    summary_cols[1].metric("Eingehende Kanten", len(preview.source_incoming))
    summary_cols[2].metric("Dubletten am Ziel", len(outgoing_duplicates) + len(incoming_duplicates))
    summary_cols[3].metric("Alias-Übernahme", len(preview.source_alias_names))

    if property_conflicts:
        st.warning("Property-Konflikte erkannt. Der Merge übernimmt aktuell fehlende Zielwerte konservativ.")
        st.dataframe(property_conflicts, width="stretch")
    else:
        st.caption("Keine offensichtlichen Property-Konflikte aus den Quell-Properties erkannt.")

    if preview.source_alias_names:
        st.caption(f"Quell-Aliase: {', '.join(preview.source_alias_names)}")

    moved_edges = len(preview.source_outgoing) + len(preview.source_incoming)
    duplicate_edges = len(outgoing_duplicates) + len(incoming_duplicates)
    st.markdown("**Was passiert?**")
    st.caption(f"{moved_edges} Kante(n) der Quelle werden fachlich geprüft und auf das Ziel übertragen.")
    if duplicate_edges:
        st.caption(f"{duplicate_edges} bereits vorhandene gleichartige Kante(n) am Ziel werden nicht doppelt angelegt.")
    if property_conflicts:
        st.caption(f"{len(property_conflicts)} Property-Konflikt(e): vorhandene Zielwerte bleiben erhalten.")

    with st.expander("Zu übernehmende Kanten", expanded=False):
        _render_relationship_rows(
            [
                {
                    "Richtung": "ausgehend",
                    "Typ": rel["rel_type"],
                    "Gegenknoten": f"{rel['other_label']}: {rel['other_ref']}",
                    "Bereits am Ziel": "ja" if _relationship_key(rel) in set(preview.target_outgoing_keys) else "nein",
                }
                for rel in preview.source_outgoing
            ]
            + [
                {
                    "Richtung": "eingehend",
                    "Typ": rel["rel_type"],
                    "Gegenknoten": f"{rel['other_label']}: {rel['other_ref']}",
                    "Bereits am Ziel": "ja" if _relationship_key(rel) in set(preview.target_incoming_keys) else "nein",
                }
                for rel in preview.source_incoming
            ]
        )


def _relationship_key(rel: dict[str, str]) -> str:
    return f"{rel.get('rel_type', '')}|{rel.get('other_label', '')}|{rel.get('other_ref', '')}"


def _decision_is_revertable(decision) -> bool:
    return getattr(decision, "status", "") == "active" and getattr(decision, "decision_type", "") != "decision_revert"


def _build_property_conflicts(preview) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    source_properties = getattr(preview, "source_properties", {}) or {}
    target_properties = getattr(preview, "target_properties", {}) or {}
    for key, value in source_properties.items():
        if value in (None, "", False):
            continue
        if key in {"created_at"}:
            continue
        target_value = target_properties.get(key)
        if target_value in (None, "", False):
            continue
        if str(target_value) == str(value):
            continue
        rows.append(
            {
                "Property": str(key),
                "Quellwert": str(value),
                "Zielwert": str(target_value),
                "Hinweis": "Aktuelle Merge-Logik behält den Zielwert bei.",
            }
        )
    return rows


def _render_relationship_rows(rows: list[dict[str, str]]) -> None:
    if not rows:
        st.caption("Keine Kanten aus der Quelle gefunden.")
        return
    st.dataframe(rows, width="stretch")

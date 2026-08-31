from __future__ import annotations

import json

import streamlit as st

from core.i18n import translate_source
from services.correction_service import revert_manual_decision
from services.decision_service import list_recent_manual_decisions
from services.merge_service import (
    get_process_merge_preview,
    load_process_merge_candidates,
    merge_processes,
)
from services.runtime_service import get_session_neo4j_client, set_run_feedback
from ui.layout import get_active_locale

SECTION_RECENT_DECISIONS = "curation_section_recent_decisions_open"
SECTION_PROCESS_MERGE = "curation_section_process_merge_open"


def _t(text: str, **values: object) -> str:
    return translate_source(text, get_active_locale()).format(**values)


def _rerun_keep(section_key: str) -> None:
    st.session_state[section_key] = True
    st.rerun()


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


def _decision_is_revertable(decision) -> bool:
    return getattr(decision, "status", "") == "active" and getattr(decision, "decision_type", "") != "decision_revert"


def render_recent_decisions_section(config, feedback_state_key: str) -> None:
    load_error: Exception | None = None
    try:
        decisions = list_recent_manual_decisions(get_session_neo4j_client(config), limit=15)
    except Exception as exc:
        decisions = []
        load_error = exc

    with st.expander(_t("Letzte manuelle Änderungen"), expanded=st.session_state.get(SECTION_RECENT_DECISIONS, False)):
        if load_error:
            st.warning(_t("Manuelle Änderungen konnten nicht geladen werden: {error}", error=load_error))
            return
        if not decisions:
            st.info(_t("Noch keine manuellen Änderungen im Entscheidungslog vorhanden."))
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
                if _decision_is_revertable(decision) and cols[2].button(_t("Zurücknehmen"), key=f"decision-revert::{decision.decision_id}", width="stretch"):
                    level, message = revert_manual_decision(config, decision.decision_id)
                    set_run_feedback(feedback_state_key, level, message)
                    _rerun_keep(SECTION_RECENT_DECISIONS)


def render_process_merge_section(config, feedback_state_key: str) -> None:
    load_error: Exception | None = None
    try:
        process_candidates = load_process_merge_candidates(config)
    except Exception as exc:
        process_candidates = []
        load_error = exc

    with st.expander(_t("Prozesse konsolidieren"), expanded=st.session_state.get(SECTION_PROCESS_MERGE, False)):
        if load_error:
            st.warning(_t("Prozesse konnten nicht geladen werden: {error}", error=load_error))
            return
        if len(process_candidates) < 2:
            st.info(_t("Für einen Merge werden mindestens zwei Prozesse benötigt."))
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
            _t("Prozess-Quelle"),
            options=[""] + process_options,
            format_func=lambda element_id: process_labels.get(element_id, element_id),
            key="process-merge-source",
        )
        target_ref = st.selectbox(
            _t("Prozess-Ziel"),
            options=[""] + [option for option in process_options if option != source_ref],
            format_func=lambda element_id: process_labels.get(element_id, element_id),
            key="process-merge-target",
        )

        if source_ref and target_ref:
            render_merge_precheck(
                lambda: get_process_merge_preview(config, source_ref, target_ref),
                key_prefix="process-merge-precheck",
            )

        if st.button(_t("Prozess-Merge ausführen"), key="process-merge-submit", width="stretch"):
            if not source_ref or not target_ref:
                st.warning(_t("Bitte Quelle und Ziel auswählen."))
            else:
                level, message = merge_processes(config, source_ref, target_ref)
                set_run_feedback(feedback_state_key, level, message)
                _rerun_keep(SECTION_PROCESS_MERGE)


def render_merge_precheck(load_preview, *, key_prefix: str) -> None:
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
        st.caption(_t("Keine Kanten aus der Quelle gefunden."))
        return
    st.dataframe(rows, width="stretch")

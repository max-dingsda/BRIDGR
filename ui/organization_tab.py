from __future__ import annotations

from pathlib import Path

import streamlit as st

from app_config import load_config
from knowledge_base import load_knowledge_base
from neo4j_utils import Neo4jConnectionError, Neo4jQueryError
from services.organization_service import (
    accept_org_candidate,
    add_org_unit_entry,
    map_org_candidate,
    persist_organization_sync,
    reject_org_candidate,
)


def render_organization_tab() -> None:
    st.subheader("Organisation")
    config = load_config(Path("config.json"))
    knowledge_base = load_knowledge_base()

    st.markdown("**Organisationseinheiten**")
    org_units = sorted(knowledge_base.org_units, key=lambda entry: entry.get("name", "").casefold())
    if org_units:
        st.dataframe(
            [
                {
                    "Name": entry.get("name", ""),
                    "Quelle": entry.get("source", ""),
                    "Angelegt am": entry.get("created_at", ""),
                }
                for entry in org_units
            ],
            width="stretch",
        )
        if st.button("Organisation nach Neo4j synchronisieren", key="org-sync-neo4j", width="stretch"):
            try:
                synced_org_units, refreshed_documents = persist_organization_sync(config)
            except (Neo4jConnectionError, Neo4jQueryError) as exc:
                st.error(f"Organisation konnte nicht nach Neo4j synchronisiert werden: {exc}")
            else:
                if refreshed_documents:
                    st.success(
                        f"{synced_org_units} Organisationseinheit(en) synchronisiert. {refreshed_documents} Dokument(e) aus dem letzten Lauf wurden fuer Prozessbeziehungen neu eingespielt."
                    )
                else:
                    st.success(f"{synced_org_units} Organisationseinheit(en) nach Neo4j synchronisiert.")
            st.rerun()
    else:
        st.info("Noch keine Organisationseinheiten gepflegt.")

    with st.form("organization-add-form"):
        new_org_unit_name = st.text_input("Neue Organisationseinheit")
        add_submitted = st.form_submit_button("Organisationseinheit hinzufuegen")
    if add_submitted:
        level, message = add_org_unit_entry(config, knowledge_base, new_org_unit_name)
        getattr(st, level)(message)
        st.rerun()

    st.markdown("**Kandidaten**")
    open_candidates = [
        entry
        for entry in knowledge_base.org_unit_candidates
        if entry.get("status", "open") == "open"
    ]
    if not open_candidates:
        st.info("Aktuell liegen keine offenen Kandidaten vor.")
    else:
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
                    "Bestehende Org-Einheit",
                    options=[""] + existing_org_unit_options,
                    key=f"org-candidate-select::{candidate_key}",
                )
                if action_columns[1].button("Mappen", key=f"org-candidate-map::{candidate_key}", width="stretch"):
                    if not selected_target:
                        st.warning("Bitte zuerst eine bestehende Organisationseinheit auswaehlen.")
                    else:
                        level, message = map_org_candidate(config, knowledge_base, candidate_name, selected_target)
                        getattr(st, level)(message)
                        st.rerun()

                proposed_name = action_columns[2].text_input(
                    "Als neue Org-Einheit uebernehmen",
                    value=candidate_name,
                    key=f"org-candidate-new::{candidate_key}",
                )
                if action_columns[3].button("Uebernehmen", key=f"org-candidate-accept::{candidate_key}", width="stretch"):
                    level, message = accept_org_candidate(config, knowledge_base, candidate_name, proposed_name)
                    getattr(st, level)(message)
                    st.rerun()

                if action_columns[4].button("Abweisen", key=f"org-candidate-reject::{candidate_key}", width="stretch"):
                    level, message = reject_org_candidate(knowledge_base, candidate_name)
                    getattr(st, level)(message)
                    st.rerun()

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

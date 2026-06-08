from __future__ import annotations

import io
from pathlib import Path

import streamlit as st

from core.app_config import load_config
from services.archimate_import_service import (
    ARCHIMATE_ELEMENT_TYPES,
    ARCHIMATE_RELATION_TYPES,
    load_archimate_mapping,
    save_archimate_mapping,
    persist_archimate_import,
)
from services.archimate_export_service import export_graph_as_archimate

_BRIDGR_LABELS = ["Prozess", "Anwendung", "Schnittstelle", "Server", "OrgEinheit", "Rolle"]
_LABEL_PAIRS = [
    "Anwendung->Prozess",
    "Rolle->Prozess",
    "OrgEinheit->Rolle",
    "Prozess->Prozess",
    "Anwendung->Schnittstelle",
    "Anwendung->Server",
    "Schnittstelle->Server",
    "OrgEinheit->Anwendung",
    "OrgEinheit->Schnittstelle",
    "OrgEinheit->Server",
]
_NO_MAPPING = "(nicht mappen)"
_ELEMENT_TYPE_OPTIONS = [_NO_MAPPING] + sorted(ARCHIMATE_ELEMENT_TYPES)
_RELATION_TYPE_OPTIONS = sorted(ARCHIMATE_RELATION_TYPES)


def render_archimate_tab() -> None:
    st.subheader("EA-Modell")
    config_path = Path("config.json")
    try:
        config = load_config(config_path)
    except Exception as exc:
        st.error(f"Konfiguration konnte nicht geladen werden: {exc}")
        return

    mapping = load_archimate_mapping()

    _render_mapping_section(mapping)
    st.divider()
    _render_import_section(config, mapping)
    st.divider()
    _render_export_section(config, mapping)


def _render_mapping_section(mapping: dict) -> None:
    st.markdown("#### Mapping konfigurieren")

    # Import mapping is stored as {ArchiMate-type → BRIDGR-label}.
    # For display we invert to {BRIDGR-label → ArchiMate-type} so every row
    # corresponds to one BRIDGR label — same layout as the export column.
    elem_import_storage: dict[str, str] = mapping.get("elements", {}).get("import", {})
    elem_import_display: dict[str, str] = {v: k for k, v in elem_import_storage.items()}
    elem_export: dict[str, str] = mapping.get("elements", {}).get("export", {})
    rel_import: dict[str, list[str]] = mapping.get("relationships", {}).get("import", {})
    rel_export: dict[str, str] = mapping.get("relationships", {}).get("export", {})

    updated_elem_import_display: dict[str, str] = {}
    updated_elem_export: dict[str, str] = {}
    updated_rel_import: dict[str, list[str]] = {}
    updated_rel_export: dict[str, str] = {}

    with st.expander("Elemente", expanded=False):
        col_label, col_import, col_export = st.columns([2, 3, 3])
        col_label.markdown("**BRIDGR-Label**")
        col_import.markdown("**Import: ArchiMate-Typ**")
        col_export.markdown("**Export: ArchiMate-Typ**")

        for label in _BRIDGR_LABELS:
            # Display: look up by BRIDGR label (inverted dict)
            current_import = elem_import_display.get(label, _NO_MAPPING)
            current_export = elem_export.get(label, _NO_MAPPING)
            c_label, c_imp, c_exp = st.columns([2, 3, 3])
            c_label.markdown(f"`{label}`")

            imp_idx = _ELEMENT_TYPE_OPTIONS.index(current_import) if current_import in _ELEMENT_TYPE_OPTIONS else 0
            exp_idx = _ELEMENT_TYPE_OPTIONS.index(current_export) if current_export in _ELEMENT_TYPE_OPTIONS else 0

            chosen_import = c_imp.selectbox(
                f"import_{label}", _ELEMENT_TYPE_OPTIONS, index=imp_idx,
                label_visibility="collapsed", key=f"elem_import_{label}",
            )
            chosen_export = c_exp.selectbox(
                f"export_{label}", _ELEMENT_TYPE_OPTIONS, index=exp_idx,
                label_visibility="collapsed", key=f"elem_export_{label}",
            )
            if chosen_import != _NO_MAPPING:
                updated_elem_import_display[label] = chosen_import
            if chosen_export != _NO_MAPPING:
                updated_elem_export[label] = chosen_export

    # Relationship widgets are expensive (20 multiselects). Only render when
    # the user explicitly requests it.
    show_rel = st.checkbox(
        "Beziehungs-Mapping bearbeiten",
        value=False,
        key="show_rel_mapping",
    )
    if show_rel:
        with st.expander("Beziehungen", expanded=True):
            col_pair, col_imp, col_exp = st.columns([3, 4, 3])
            col_pair.markdown("**Label-Paar**")
            col_imp.markdown("**Import: akzeptierte AM-Typen**")
            col_exp.markdown("**Export: kanonischer AM-Typ**")

            for pair in _LABEL_PAIRS:
                current_imp_list = rel_import.get(pair, [])
                current_exp = rel_export.get(pair, _NO_MAPPING)
                c_pair, c_imp, c_exp = st.columns([3, 4, 3])
                c_pair.markdown(f"`{pair}`")

                chosen_imp_list = c_imp.multiselect(
                    f"import_{pair}", _RELATION_TYPE_OPTIONS,
                    default=[t for t in current_imp_list if t in _RELATION_TYPE_OPTIONS],
                    label_visibility="collapsed", key=f"rel_import_{pair}",
                )
                exp_opts = [_NO_MAPPING] + _RELATION_TYPE_OPTIONS
                exp_idx = exp_opts.index(current_exp) if current_exp in exp_opts else 0
                chosen_exp = c_exp.selectbox(
                    f"export_{pair}", exp_opts, index=exp_idx,
                    label_visibility="collapsed", key=f"rel_export_{pair}",
                )
                updated_rel_import[pair] = chosen_imp_list
                if chosen_exp != _NO_MAPPING:
                    updated_rel_export[pair] = chosen_exp
    else:
        # Keep current relationship mapping unchanged when the section is hidden
        updated_rel_import = rel_import
        updated_rel_export = rel_export

    st.caption(
        "Änderungen werden erst nach dem Klick auf 'Mapping speichern' in "
        "archimate_mapping.json geschrieben."
    )
    if st.button("Mapping speichern", key="save_archimate_mapping"):
        # Invert import display dict back to storage format: {AM-type → BRIDGR-label}
        storage_elem_import = {am_type: bridgr_label
                               for bridgr_label, am_type in updated_elem_import_display.items()}
        mapping["elements"] = {"import": storage_elem_import, "export": updated_elem_export}
        mapping["relationships"] = {"import": updated_rel_import, "export": updated_rel_export}
        try:
            save_archimate_mapping(mapping)
            st.success("Mapping gespeichert.")
        except Exception as exc:
            st.error(f"Fehler beim Speichern: {exc}")

    _render_candidates_section(mapping)


def _render_candidates_section(mapping: dict) -> None:
    candidates: list[dict] = mapping.get("pending_candidates", [])
    if not candidates:
        return

    st.markdown("#### Offene Zuordnungen")
    st.caption(
        f"{len(candidates)} ArchiMate-Element(e) konnten nicht eindeutig zugeordnet werden."
    )
    for i, cand in enumerate(candidates):
        col_info, col_confirm, col_reject = st.columns([5, 1, 1])
        col_info.markdown(
            f"**{cand['archimate_name']}** (`{cand['archimate_type']}`) "
            f"→ Vorschlag: **{cand['suggested_match']}** "
            f"(Score: {cand['score']:.0%})"
        )
        if col_confirm.button("✓", key=f"confirm_cand_{i}"):
            _confirm_candidate(mapping, cand)
            st.rerun()
        if col_reject.button("✗", key=f"reject_cand_{i}"):
            _reject_candidate(mapping, cand)
            st.rerun()


def _confirm_candidate(mapping: dict, candidate: dict) -> None:
    mapping["pending_candidates"] = [
        c for c in mapping.get("pending_candidates", [])
        if c.get("archimate_id") != candidate["archimate_id"]
    ]
    save_archimate_mapping(mapping)


def _reject_candidate(mapping: dict, candidate: dict) -> None:
    mapping["pending_candidates"] = [
        c for c in mapping.get("pending_candidates", [])
        if c.get("archimate_id") != candidate["archimate_id"]
    ]
    save_archimate_mapping(mapping)


def _render_import_section(config, mapping: dict) -> None:
    st.markdown("#### Import")
    uploaded = st.file_uploader(
        "ArchiMate-Datei hochladen (.xml oder .archimate)",
        type=["xml", "archimate"],
        key="archimate_upload",
    )
    if uploaded is not None and st.button("Importieren", key="archimate_import_btn"):
        tmp_path = Path(config.input_path) / uploaded.name
        try:
            tmp_path.parent.mkdir(parents=True, exist_ok=True)
            tmp_path.write_bytes(uploaded.read())
            result = persist_archimate_import(config, tmp_path)
            st.success(
                f"Import abgeschlossen: {result.elements_imported} Elemente importiert, "
                f"{result.elements_as_candidates} Kandidaten, "
                f"{result.elements_skipped} übersprungen, "
                f"{result.relations_imported} Beziehungen importiert, "
                f"{result.relations_skipped} Beziehungen übersprungen."
            )
            if result.skipped_types:
                skipped_summary = ", ".join(
                    f"{t} ({n})" for t, n in sorted(result.skipped_types.items())
                )
                st.info(f"Übersprungene ArchiMate-Typen: {skipped_summary}")
        except Exception as exc:
            st.error(f"Import fehlgeschlagen: {exc}")
        finally:
            if tmp_path.exists():
                tmp_path.unlink(missing_ok=True)


def _render_export_section(config, mapping: dict) -> None:
    st.markdown("#### Export")
    st.caption(
        "Der Export umfasst immer den vollständigen BRIDGR-Graphen. "
        "Teilexporte sind ohne Views/Viewpoints nicht möglich."
    )
    if st.button("Als ArchiMate exportieren", key="archimate_export_btn"):
        try:
            result = export_graph_as_archimate(config, mapping)
            st.success(
                f"Export abgeschlossen: {result.elements_exported} Elemente, "
                f"{result.relations_exported} Beziehungen. "
                f"Datei: `{result.output_path}`"
            )
        except Exception as exc:
            st.error(f"Export fehlgeschlagen: {exc}")

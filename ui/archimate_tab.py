from __future__ import annotations

import uuid
from collections import defaultdict
from pathlib import Path

import streamlit as st

from core.app_config import load_config
from core.graph_schema import QUERY_NODE_SCHEMA, QUERY_RELATIONSHIP_PATTERNS, QUERY_RELATIONSHIP_SCHEMA
from services.archimate_import_service import (
    ARCHIMATE_ELEMENT_TYPES,
    ARCHIMATE_RELATION_TYPES,
    load_archimate_mapping,
    save_archimate_mapping,
    persist_archimate_import,
)
from services.archimate_export_service import (
    export_graph_as_archimate,
    fetch_untyped_nodes,
    write_archimate_types,
)

_INTERNAL_LABELS = {"Alias"}
_WEAK_RELATIONSHIP_TYPES = {"KÖNNTE_DIENEN", "KÖNNTE_VERANTWORTEN", "KANN_MEINEN"}

_BRIDGR_LABELS: list[str] = sorted(l for l in QUERY_NODE_SCHEMA if l not in _INTERNAL_LABELS)
_LABEL_PAIRS: list[str] = sorted(dict.fromkeys(
    f"{p.source_label}->{p.target_label}"
    for p in QUERY_RELATIONSHIP_PATTERNS
    if p.relationship_type not in _WEAK_RELATIONSHIP_TYPES
))
_NO_MAPPING = "(nicht mappen)"
_RELATION_TYPE_OPTIONS = sorted(ARCHIMATE_RELATION_TYPES)
_BRIDGR_RELATION_OPTIONS: list[str] = sorted(
    r for r in QUERY_RELATIONSHIP_SCHEMA if r not in _WEAK_RELATIONSHIP_TYPES
)

# Session state keys
_STATE_IMPORT_ROWS = "archimate_import_rows"
_STATE_EXPORT_REVIEW = "archimate_export_review_active"
_STATE_EXPORT_UNTYPED = "archimate_export_untyped_nodes"


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


# ---------------------------------------------------------------------------
# Mapping section
# ---------------------------------------------------------------------------

def _render_mapping_section(mapping: dict) -> None:
    st.markdown("#### Mapping konfigurieren")

    elem_import_storage: dict[str, str] = mapping.get("elements", {}).get("import", {})
    elem_export: dict[str, str] = mapping.get("elements", {}).get("export", {})
    rel_import: dict[str, list[str]] = mapping.get("relationships", {}).get("import", {})
    rel_export: dict[str, str] = mapping.get("relationships", {}).get("export", {})

    # --- Import mapping (per AM-type rows, m:1 supported) ---
    with st.expander("Import: ArchiMate → BRIDGR", expanded=False):
        _ensure_import_rows_initialized(elem_import_storage)
        updated_import_storage = _render_import_mapping_editor()

    # --- Export mapping (per BRIDGR-label, 1:1) ---
    updated_elem_export: dict[str, str] = {}
    with st.expander("Export: BRIDGR → ArchiMate", expanded=False):
        col_label, col_export = st.columns([2, 4])
        col_label.markdown("**BRIDGR-Label**")
        col_export.markdown("**Export: ArchiMate-Typ**")

        exp_options = [_NO_MAPPING] + sorted(ARCHIMATE_ELEMENT_TYPES)
        for label in _BRIDGR_LABELS:
            current_export = elem_export.get(label, _NO_MAPPING)
            c_label, c_exp = st.columns([2, 4])
            c_label.markdown(f"`{label}`")
            exp_idx = exp_options.index(current_export) if current_export in exp_options else 0
            chosen_export = c_exp.selectbox(
                f"export_{label}", exp_options, index=exp_idx,
                label_visibility="collapsed", key=f"elem_export_{label}",
            )
            if chosen_export != _NO_MAPPING:
                updated_elem_export[label] = chosen_export

    # --- Relationship mapping (optional, rarely changed) ---
    rel_bridgr: dict[str, str] = mapping.get("relationships", {}).get("bridgr_relation", {})
    updated_rel_import: dict[str, list[str]] = {}
    updated_rel_export: dict[str, str] = {}
    updated_rel_bridgr: dict[str, str] = {}
    show_rel = st.checkbox(
        "Beziehungs-Mapping bearbeiten",
        value=False,
        key="show_rel_mapping",
    )
    if show_rel:
        with st.expander("Beziehungen", expanded=True):
            col_pair, col_imp, col_exp, col_bridgr = st.columns([3, 4, 2, 3])
            col_pair.markdown("**Label-Paar**")
            col_imp.markdown("**Import: akzeptierte AM-Typen**")
            col_exp.markdown("**Export: AM-Typ**")
            col_bridgr.markdown("**BRIDGR-Relation**")

            bridgr_opts = [_NO_MAPPING] + _BRIDGR_RELATION_OPTIONS
            for pair in _LABEL_PAIRS:
                current_imp_list = rel_import.get(pair, [])
                current_exp = rel_export.get(pair, _NO_MAPPING)
                current_bridgr = rel_bridgr.get(pair, _NO_MAPPING)
                c_pair, c_imp, c_exp, c_bridgr = st.columns([3, 4, 2, 3])
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
                bridgr_idx = bridgr_opts.index(current_bridgr) if current_bridgr in bridgr_opts else 0
                chosen_bridgr = c_bridgr.selectbox(
                    f"bridgr_{pair}", bridgr_opts, index=bridgr_idx,
                    label_visibility="collapsed", key=f"rel_bridgr_{pair}",
                )
                updated_rel_import[pair] = chosen_imp_list
                if chosen_exp != _NO_MAPPING:
                    updated_rel_export[pair] = chosen_exp
                if chosen_bridgr != _NO_MAPPING:
                    updated_rel_bridgr[pair] = chosen_bridgr
    else:
        updated_rel_import = rel_import
        updated_rel_export = rel_export
        updated_rel_bridgr = rel_bridgr

    st.caption(
        "Änderungen werden erst nach dem Klick auf 'Mapping speichern' in "
        "archimate_mapping.json geschrieben."
    )
    if st.button("Mapping speichern", key="save_archimate_mapping"):
        mapping["elements"] = {"import": updated_import_storage, "export": updated_elem_export}
        mapping["relationships"] = {
            "import": updated_rel_import,
            "export": updated_rel_export,
            "bridgr_relation": updated_rel_bridgr,
        }
        try:
            save_archimate_mapping(mapping)
            # Clear session state so rows reinitialize from the saved file
            st.session_state.pop(_STATE_IMPORT_ROWS, None)
            st.success("Mapping gespeichert.")
        except Exception as exc:
            st.error(f"Fehler beim Speichern: {exc}")

    _render_candidates_section(mapping)


def _ensure_import_rows_initialized(elem_import_storage: dict[str, str]) -> None:
    if _STATE_IMPORT_ROWS not in st.session_state:
        st.session_state[_STATE_IMPORT_ROWS] = [
            {"id": f"r{i}", "am_type": k, "bridgr_label": v}
            for i, (k, v) in enumerate(elem_import_storage.items())
        ]


def _render_import_mapping_editor() -> dict[str, str]:
    """Render per-AM-type rows with add/delete. Returns {AM-type -> BRIDGR-label}."""
    rows: list[dict] = st.session_state[_STATE_IMPORT_ROWS]

    col_am, col_lbl, col_del = st.columns([4, 4, 1])
    col_am.markdown("**ArchiMate-Typ**")
    col_lbl.markdown("**BRIDGR-Label**")
    col_del.markdown("")

    to_delete: str | None = None
    for row in rows:
        row_id = row["id"]
        am_key = f"imp_am_{row_id}"
        lbl_key = f"imp_lbl_{row_id}"

        am_current = st.session_state.get(am_key, row["am_type"])
        lbl_current = st.session_state.get(lbl_key, row["bridgr_label"])

        am_idx = ARCHIMATE_ELEMENT_TYPES.index(am_current) if am_current in ARCHIMATE_ELEMENT_TYPES else 0
        lbl_idx = _BRIDGR_LABELS.index(lbl_current) if lbl_current in _BRIDGR_LABELS else 0

        c_am, c_lbl, c_del = st.columns([4, 4, 1])
        c_am.selectbox(
            "AM-Typ", ARCHIMATE_ELEMENT_TYPES, index=am_idx,
            label_visibility="collapsed", key=am_key,
        )
        c_lbl.selectbox(
            "BRIDGR-Label", _BRIDGR_LABELS, index=lbl_idx,
            label_visibility="collapsed", key=lbl_key,
        )
        if c_del.button("✕", key=f"imp_del_{row_id}"):
            to_delete = row_id

    if to_delete is not None:
        st.session_state[_STATE_IMPORT_ROWS] = [r for r in rows if r["id"] != to_delete]
        st.rerun()

    if st.button("+ Mapping hinzufügen", key="imp_add_row"):
        new_id = uuid.uuid4().hex[:8]
        st.session_state[_STATE_IMPORT_ROWS].append({
            "id": new_id,
            "am_type": ARCHIMATE_ELEMENT_TYPES[0],
            "bridgr_label": _BRIDGR_LABELS[0],
        })
        st.rerun()

    # Collect current widget values → storage dict {AM-type -> BRIDGR-label}
    storage: dict[str, str] = {}
    for row in st.session_state[_STATE_IMPORT_ROWS]:
        row_id = row["id"]
        am_type = st.session_state.get(f"imp_am_{row_id}", row["am_type"])
        bridgr_label = st.session_state.get(f"imp_lbl_{row_id}", row["bridgr_label"])
        storage[am_type] = bridgr_label
    return storage


# ---------------------------------------------------------------------------
# Candidates section
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Import section
# ---------------------------------------------------------------------------

_SKIP_REASON_LABELS: dict[str, str] = {
    "unresolvable_endpoint": "unbekannter Endpunkt",
    "type_not_accepted":     "Typ nicht konfiguriert",
    "no_bridgr_relation":    "kein BRIDGR-Mapping",
}


def _render_skipped_relations(skipped: list[dict]) -> None:
    with st.expander(f"Übersprungene Beziehungen ({len(skipped)})", expanded=False):
        for entry in skipped:
            reason_label = _SKIP_REASON_LABELS.get(entry["reason"], entry["reason"])
            st.markdown(
                f"- `[{reason_label}]` "
                f"**{entry['source']}** –[{entry['rel_type']}]→ **{entry['target']}**"
            )

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
            candidate_note = (
                f", davon {result.elements_as_candidates} zur Prüfung markiert"
                if result.elements_as_candidates else ""
            )
            st.success(
                f"Import abgeschlossen: "
                f"{result.elements_imported + result.elements_as_candidates} Elemente importiert"
                f"{candidate_note}, "
                f"{result.elements_skipped} übersprungen, "
                f"{result.relations_imported} Beziehungen importiert, "
                f"{result.relations_skipped} Beziehungen übersprungen."
            )
            if result.skipped_relations:
                _render_skipped_relations(result.skipped_relations)
        except Exception as exc:
            st.error(f"Import fehlgeschlagen: {exc}")
        finally:
            if tmp_path.exists():
                tmp_path.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# Export section with pre-check
# ---------------------------------------------------------------------------

def _render_export_section(config, mapping: dict) -> None:
    st.markdown("#### Export")
    st.caption(
        "Der Export umfasst immer den vollständigen BRIDGR-Graphen. "
        "Teilexporte sind ohne Views/Viewpoints nicht möglich."
    )

    if st.session_state.get(_STATE_EXPORT_REVIEW):
        _render_export_review(config, mapping)
    else:
        if st.button("Als ArchiMate exportieren", key="archimate_export_btn"):
            export_elem_map: dict[str, str] = mapping.get("elements", {}).get("export", {})
            try:
                untyped = fetch_untyped_nodes(config, export_elem_map)
            except Exception as exc:
                st.error(f"Datenbankabfrage fehlgeschlagen: {exc}")
                return
            if not untyped:
                _do_export(config, mapping)
            else:
                st.session_state[_STATE_EXPORT_UNTYPED] = untyped
                st.session_state[_STATE_EXPORT_REVIEW] = True
                st.rerun()


def _render_export_review(config, mapping: dict) -> None:
    untyped: list[dict] = st.session_state.get(_STATE_EXPORT_UNTYPED, [])

    st.info(
        f"{len(untyped)} Node(s) ohne ArchiMate-Typ gefunden. "
        "Bitte Exporttypen prüfen und bestätigen."
    )

    groups: dict[str, list[dict]] = defaultdict(list)
    for node in untyped:
        groups[node["label"]].append(node)

    for label, nodes in sorted(groups.items()):
        proposed = nodes[0]["proposed_type"]
        with st.expander(
            f"{label} — {len(nodes)} Node(s) → {proposed} (Standard)",
            expanded=False,
        ):
            col_name, col_type = st.columns([3, 3])
            col_name.markdown("**Node**")
            col_type.markdown("**Export-Typ**")
            for node in nodes:
                widget_key = f"exp_rev_{node['label']}_{node['name']}"
                current = st.session_state.get(widget_key, proposed)
                am_opts = sorted(ARCHIMATE_ELEMENT_TYPES)
                idx = am_opts.index(current) if current in am_opts else 0
                c_name, c_type = st.columns([3, 3])
                c_name.text(node["name"])
                c_type.selectbox(
                    f"t_{node['label']}_{node['name']}",
                    am_opts,
                    index=idx,
                    label_visibility="collapsed",
                    key=widget_key,
                )

    col_confirm, col_cancel = st.columns([2, 1])
    if col_confirm.button("Vorschläge übernehmen und exportieren", key="exp_review_confirm"):
        write_list = [
            {
                "label": n["label"],
                "name": n["name"],
                "archimate_type": st.session_state.get(
                    f"exp_rev_{n['label']}_{n['name']}", n["proposed_type"]
                ),
            }
            for n in untyped
            if st.session_state.get(f"exp_rev_{n['label']}_{n['name']}", n["proposed_type"])
        ]
        try:
            write_archimate_types(config, write_list)
        except Exception as exc:
            st.error(f"Fehler beim Schreiben der ArchiMate-Typen: {exc}")
            return
        st.session_state[_STATE_EXPORT_REVIEW] = False
        _do_export(config, mapping)

    if col_cancel.button("Abbrechen", key="exp_review_cancel"):
        st.session_state[_STATE_EXPORT_REVIEW] = False
        st.rerun()


def _do_export(config, mapping: dict) -> None:
    try:
        result = export_graph_as_archimate(config, mapping)
        st.success(
            f"Export abgeschlossen: {result.elements_exported} Elemente, "
            f"{result.relations_exported} Beziehungen. "
            f"Datei: `{result.output_path}`"
        )
    except Exception as exc:
        st.error(f"Export fehlgeschlagen: {exc}")

# BRIDGR — Acceptance Snapshot

Status overview of implemented and open features. Update this file when features are completed or scope changes.

---

## Currently Implemented

- BPMN, TXT, DOCX and PDF process import
- BPMN transformer for large BPMN/XML files
- Import/archive workflow with `full` and `partial`
- Review without starting a fresh inbox import
- Organization curation tab with collapsible sections, process owner assignment, batch owner assignment for ownerless processes, role-to-OrgUnit mapping (KANN_EINNEHMEN), and explicit role-only marking
- Normalized CMDB entity model and basic CMDB relation write path
- LLM-as-orchestrator chat layer with `prompt-only` and `tool-use` modes
- Full conversation history for follow-up questions; no imperative disambiguation state in code
- Alias enrichment as deterministic hint-passing to the LLM
- ArchiMate Exchange Format 3.x import with configurable type mapping and identity resolution
- ArchiMate export (full graph, without views/viewpoints) with export pre-check for untyped nodes
- EA-Modell tab (Tab 5) with extended import mapping editor (m:1, per-AM-type rows), export mapping, import and export actions
- `archimate_mapping.json` as external single source of truth for ArchiMate type mapping
- Attribute-level source-of-truth principle: each import source owns and writes only its own attributes

## Not Fully Completed Yet

- Complete UI/review support for all new CMDB object types
- Full CMDB-driven ownership review workflow in the UI
- Support for non-CSV CMDB formats
- ArchiMate Views/Viewpoints in export
- Selective ArchiMate export (requires Views)
- Automatic relationship backfill after ArchiMate candidate confirmation (currently requires re-import)

# Graph Report - BRIDGR  (2026-06-09)

## Corpus Check
- 99 files · ~197,982 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 1704 nodes · 5864 edges · 100 communities (70 shown, 30 thin omitted)
- Extraction: 81% EXTRACTED · 19% INFERRED · 0% AMBIGUOUS · INFERRED: 1091 edges (avg confidence: 0.52)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `7a62e2b9`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- [[_COMMUNITY_Community 0|Community 0]]
- [[_COMMUNITY_Community 1|Community 1]]
- [[_COMMUNITY_Community 2|Community 2]]
- [[_COMMUNITY_Community 3|Community 3]]
- [[_COMMUNITY_Community 4|Community 4]]
- [[_COMMUNITY_Community 5|Community 5]]
- [[_COMMUNITY_Community 6|Community 6]]
- [[_COMMUNITY_Community 7|Community 7]]
- [[_COMMUNITY_Community 8|Community 8]]
- [[_COMMUNITY_Community 9|Community 9]]
- [[_COMMUNITY_Community 10|Community 10]]
- [[_COMMUNITY_Community 11|Community 11]]
- [[_COMMUNITY_Community 12|Community 12]]
- [[_COMMUNITY_Community 13|Community 13]]
- [[_COMMUNITY_Community 14|Community 14]]
- [[_COMMUNITY_Community 15|Community 15]]
- [[_COMMUNITY_Community 16|Community 16]]
- [[_COMMUNITY_Community 17|Community 17]]
- [[_COMMUNITY_Community 18|Community 18]]
- [[_COMMUNITY_Community 19|Community 19]]
- [[_COMMUNITY_Community 20|Community 20]]
- [[_COMMUNITY_Community 21|Community 21]]
- [[_COMMUNITY_Community 22|Community 22]]
- [[_COMMUNITY_Community 23|Community 23]]
- [[_COMMUNITY_Community 24|Community 24]]
- [[_COMMUNITY_Community 25|Community 25]]
- [[_COMMUNITY_Community 26|Community 26]]
- [[_COMMUNITY_Community 27|Community 27]]
- [[_COMMUNITY_Community 28|Community 28]]
- [[_COMMUNITY_Community 29|Community 29]]
- [[_COMMUNITY_Community 30|Community 30]]
- [[_COMMUNITY_Community 31|Community 31]]
- [[_COMMUNITY_Community 32|Community 32]]
- [[_COMMUNITY_Community 33|Community 33]]
- [[_COMMUNITY_Community 34|Community 34]]
- [[_COMMUNITY_Community 35|Community 35]]
- [[_COMMUNITY_Community 36|Community 36]]
- [[_COMMUNITY_Community 37|Community 37]]
- [[_COMMUNITY_Community 38|Community 38]]
- [[_COMMUNITY_Community 39|Community 39]]
- [[_COMMUNITY_Community 40|Community 40]]
- [[_COMMUNITY_Community 41|Community 41]]
- [[_COMMUNITY_Community 42|Community 42]]
- [[_COMMUNITY_Community 43|Community 43]]
- [[_COMMUNITY_Community 44|Community 44]]
- [[_COMMUNITY_Community 45|Community 45]]
- [[_COMMUNITY_Community 46|Community 46]]
- [[_COMMUNITY_Community 47|Community 47]]
- [[_COMMUNITY_Community 48|Community 48]]
- [[_COMMUNITY_Community 49|Community 49]]
- [[_COMMUNITY_Community 50|Community 50]]
- [[_COMMUNITY_Community 51|Community 51]]
- [[_COMMUNITY_Community 52|Community 52]]
- [[_COMMUNITY_Community 53|Community 53]]
- [[_COMMUNITY_Community 55|Community 55]]
- [[_COMMUNITY_Community 56|Community 56]]
- [[_COMMUNITY_Community 57|Community 57]]
- [[_COMMUNITY_Community 58|Community 58]]
- [[_COMMUNITY_Community 59|Community 59]]
- [[_COMMUNITY_Community 60|Community 60]]
- [[_COMMUNITY_Community 61|Community 61]]
- [[_COMMUNITY_Community 62|Community 62]]
- [[_COMMUNITY_Community 63|Community 63]]
- [[_COMMUNITY_Community 64|Community 64]]
- [[_COMMUNITY_Community 65|Community 65]]
- [[_COMMUNITY_Community 66|Community 66]]
- [[_COMMUNITY_Community 67|Community 67]]
- [[_COMMUNITY_Community 68|Community 68]]
- [[_COMMUNITY_Community 69|Community 69]]
- [[_COMMUNITY_Community 70|Community 70]]
- [[_COMMUNITY_Community 71|Community 71]]
- [[_COMMUNITY_Community 72|Community 72]]
- [[_COMMUNITY_Community 73|Community 73]]
- [[_COMMUNITY_Community 76|Community 76]]
- [[_COMMUNITY_Community 77|Community 77]]
- [[_COMMUNITY_Community 79|Community 79]]
- [[_COMMUNITY_Community 80|Community 80]]
- [[_COMMUNITY_Community 81|Community 81]]
- [[_COMMUNITY_Community 82|Community 82]]
- [[_COMMUNITY_Community 83|Community 83]]
- [[_COMMUNITY_Community 84|Community 84]]
- [[_COMMUNITY_Community 85|Community 85]]
- [[_COMMUNITY_Community 86|Community 86]]
- [[_COMMUNITY_Community 87|Community 87]]
- [[_COMMUNITY_Community 88|Community 88]]
- [[_COMMUNITY_Community 89|Community 89]]
- [[_COMMUNITY_Community 90|Community 90]]
- [[_COMMUNITY_Community 91|Community 91]]
- [[_COMMUNITY_Community 92|Community 92]]
- [[_COMMUNITY_Community 93|Community 93]]
- [[_COMMUNITY_Community 94|Community 94]]
- [[_COMMUNITY_Community 95|Community 95]]
- [[_COMMUNITY_Community 96|Community 96]]
- [[_COMMUNITY_Community 97|Community 97]]
- [[_COMMUNITY_Community 98|Community 98]]
- [[_COMMUNITY_Community 99|Community 99]]

## God Nodes (most connected - your core abstractions)
1. `AppConfig` - 137 edges
2. `AppConfig` - 134 edges
3. `ExtractedProcess` - 93 edges
4. `GraphWriter` - 91 edges
5. `KnowledgeBase` - 81 edges
6. `OpenAICompatibleClient` - 78 edges
7. `KnowledgeBase` - 78 edges
8. `GraphWriter` - 75 edges
9. `MatchResult` - 65 edges
10. `Neo4jClient` - 63 edges

## Surprising Connections (you probably didn't know these)
- `Initial Lauf` --references--> `KnowledgeBase`  [EXTRACTED]
  Specs/Bridgr_Architektur_v09.md → services/organization_service.py
- `Full Update` --references--> `KnowledgeBase`  [EXTRACTED]
  Specs/Bridgr_Architektur_v09.md → services/organization_service.py
- `Delta Update` --references--> `KnowledgeBase`  [EXTRACTED]
  Specs/Bridgr_Architektur_v09.md → services/organization_service.py
- `Typ-Inkonsistenz zwischen match.py und knowledge_base.py` --references--> `KnowledgeBase`  [EXTRACTED]
  Specs/review_findings.md → services/organization_service.py
- `Concept: External Test Review to Catch Self-Written Test Blind Spots` --rationale_for--> `Test: Review (collect_review_items)`  [INFERRED]
  Specs/test_audit.md → tests/test_review.py

## Import Cycles
- None detected.

## Communities (100 total, 30 thin omitted)

### Community 0 - "Community 0"
Cohesion: 0.07
Nodes (125): CmdbEntity, CmdbRelation, Neo4jClient, Neo4jConfig, Neo4jConnectionError, Neo4jServiceUnavailableError, ApplicationReference (extract_base), DOCX Extractor (+117 more)

### Community 1 - "Community 1"
Cohesion: 0.08
Nodes (48): ApplicationReference, ApplicationReference (dataclass), ExtractedProcess (dataclass), BPMN Extractor, ApplicationReference, BpmnExtractor, TextExtractor, TextExtractorError (+40 more)

### Community 2 - "Community 2"
Cohesion: 0.06
Nodes (84): Alias Service, lookup_alias_matches(), sync_knowledge_base_aliases(), sync_knowledge_base_aliases (alias_service), CMDB Service, persist_cmdb_sync(), sync_cmdb_to_neo4j(), GraphWriter.sync_cmdb() (+76 more)

### Community 3 - "Community 3"
Cohesion: 0.14
Nodes (43): Fuzzy Matching, float, _add_pending_candidate(), ArchiMateElement, ArchiMateImportResult, ArchiMateRelation, _default_mapping(), _fuzzy_match_name() (+35 more)

### Community 4 - "Community 4"
Cohesion: 0.06
Nodes (107): Return the absolute path to the configured CMDB file.      The returned path may, Return a writable output directory and whether a fallback was used.      Unlike, resolve_input_cmdb_path(), resolve_runtime_output_path(), build_cmdb_option_labels(), CmdbLoadError, CmdbValidationIssue, _collect_csv_shape_issues() (+99 more)

### Community 5 - "Community 5"
Cohesion: 0.08
Nodes (42): is_directory_writable(), is_legacy_input_path(), load_config(), normalize_path_value(), normalize_run_mode(), bool, Path, str (+34 more)

### Community 7 - "Community 7"
Cohesion: 0.15
Nodes (55): int, Organization Service, persist_org_candidate_mapping_refresh(), persist_organization_sync(), save_knowledge_base(), accept_org_candidate(), accept_process_owner_candidate(), add_org_unit_entry() (+47 more)

### Community 8 - "Community 8"
Cohesion: 0.09
Nodes (47): build_query_schema_reference(), _extract_variable_labels(), str, RelationshipPattern, _resolve_labels(), _validate_labels(), _validate_properties(), validate_query_schema() (+39 more)

### Community 9 - "Community 9"
Cohesion: 0.25
Nodes (20): bytes, _csv_has_columns(), describe_cmdb_file(), list_cmdb_entity_files(), list_cmdb_files(), list_cmdb_relation_files(), list_process_files(), bool (+12 more)

### Community 10 - "Community 10"
Cohesion: 0.06
Nodes (120): main(), Pipeline Run Tracker (app.py), Session & Connection Management (app.py), main(), execute_cypher Tool Schema (LLM tool call), Concept: Conversation History for Context, _extract_json_object(), LlmClientConfig (+112 more)

### Community 11 - "Community 11"
Cohesion: 0.10
Nodes (36): Import Service, build_import_completion_message (import_service), finalize_import_artifacts(), documents, archive_path, display_paths, run_mode, source_paths (+28 more)

### Community 12 - "Community 12"
Cohesion: 0.05
Nodes (41): elements, export, import, Anwendung, Anwendung->Prozess, Anwendung->Schnittstelle, Anwendung->Server, OrgEinheit (+33 more)

### Community 13 - "Community 13"
Cohesion: 0.07
Nodes (27): chat_mode, cmdb_entity_type_column, cmdb_filename, cmdb_multivalue_separator, cmdb_name_column, cmdb_owner_name_column, cmdb_relation_source_column, cmdb_relation_target_column (+19 more)

### Community 14 - "Community 14"
Cohesion: 0.19
Nodes (19): FakeNeo4jClient, _parse_export(), Element, Path, str, _RecordingWriteClient, _run(), test_export_counts_correct() (+11 more)

### Community 15 - "Community 15"
Cohesion: 0.20
Nodes (26): BpmnTransformError, _build_process_transform_text(), _build_transform_filename(), _extract_application_names(), _extract_lane_names(), _extract_participant_names_by_process(), _extract_process_entries(), _extract_unassigned_participant_names() (+18 more)

### Community 16 - "Community 16"
Cohesion: 0.06
Nodes (30): Architektur-Compliance, Aufgegriffen und umgesetzt, Bewusst zurueckgestellt, Bridgr — Code Review Findings, code:python (# Aktuell: pauschal), F-01 — Hardcodierte Produktions-Credentials in config.json, F-02 — Generische Exception-Behandlung in `neo4j_utils.py`, F-03 — LLM-Client verwendet `urllib` statt `requests` (+22 more)

### Community 17 - "Community 17"
Cohesion: 0.10
Nodes (26): Bridgr, ABFRAGE-LAYER (Nutzung), Anwendung, CMDB-Export, Konfiguration, Delta Update, BPMN-Extraktion, generische Extraktion (+18 more)

### Community 18 - "Community 18"
Cohesion: 0.14
Nodes (34): AppConfig, AppConfig, AppConfig, AppConfig, Inkonsistente Pfadauflösung, test_ensure_import_session_defaults_uses_config_mode(), test_ensure_query_chat_defaults_initializes_chat_state(), test_get_llm_status_reports_endpoint_error() (+26 more)

### Community 19 - "Community 19"
Cohesion: 0.11
Nodes (38): Concept: External Test Review to Catch Self-Written Test Blind Spots, RejectedLink, RejectedLink, Skill: Extract Base, build_fuzzy_candidates(), classify_match_confidence(), compute_containment_score(), is_application_rejected() (+30 more)

### Community 20 - "Community 20"
Cohesion: 0.07
Nodes (26): chat_mode, cmdb_entity_type_column, cmdb_filename, cmdb_multivalue_separator, cmdb_name_column, cmdb_owner_name_column, cmdb_relation_source_column, cmdb_relation_target_column (+18 more)

### Community 21 - "Community 21"
Cohesion: 0.34
Nodes (19): build_client(), FakeResponse, FakeSession, MonkeyPatch, test_extract_json_object_handles_nested_json_without_regex(), test_generate_json_extracts_json_object_from_markdown_wrapped_response(), test_generate_json_logs_requests_and_responses(), test_generate_json_raises_after_exhausting_repair_attempts() (+11 more)

### Community 23 - "Community 23"
Cohesion: 0.10
Nodes (20): 1. Abhaengigkeiten, 2. Streamlit starten, 3. Pipeline per CLI starten, Aktuelle UI-Funktionen, Aktueller Stand, BPMN-Transformer fuer grosse Modelle, Debug-Modus, Hinweise (+12 more)

### Community 24 - "Community 24"
Cohesion: 0.25
Nodes (7): UX Issue: Import Buried Behind Two Clicks, Concept: KB-First Matching (KB -> Fuzzy -> LLM Fallback), UX Issue: Review Tab Shows Same Data Twice, UX Issue: Tab Order Inverted vs Workflow, UI: Organization Tab, UI: Review Tab (Link Editing), Test: Review Tab

### Community 25 - "Community 25"
Cohesion: 0.13
Nodes (15): 7.1 Zweck, 7.2 Abschnitt `Umfang`, 7.3 Feld `Statusfilter`, 7.4 Bereich `Dokumentstatus`, 7.5 Bereich `Offene Zuordnungen`, 7.6 Bereich `Dokumentdetails`, 7.7 Wann Sie diesen Tab nutzen sollten, 7. Tab `Zuordnungen` (+7 more)

### Community 26 - "Community 26"
Cohesion: 0.17
Nodes (10): Fuzzy-Matching-Entscheidung, Prozess-Namens-Matching, BRIDGR README, Neo4j Python Driver, Pandas, PyPDF, python-docx, Requests (+2 more)

### Community 27 - "Community 27"
Cohesion: 0.14
Nodes (14): ArchiMate — Konzeptionelle Planung, ArchiMate-Tab: UI-Konzept, Beispiel ArchiMate Exchange Format (vereinfacht), Bereich 1 — Mapping konfigurieren, Bereich 2 — Import & Export, Dateiformate, Entscheidungen, Export-Pipeline (Entwurf) (+6 more)

### Community 28 - "Community 28"
Cohesion: 0.31
Nodes (9): extract_bpmn_process_ids (identity), extract_bpmn_process_ids(), str, Return all BPMN process ids found in the given XML text., identity.py ist ein Minimal-Stub, Test Suite: Identity (BPMN Process IDs), test_extract_bpmn_process_ids_raises_for_malformed_xml(), test_extract_bpmn_process_ids_returns_all_process_ids() (+1 more)

### Community 31 - "Community 31"
Cohesion: 0.14
Nodes (13): 11.1 Erster Import, 11.2 Offene Zuordnungen bereinigen, 11.3 Fragen an den Graph stellen, 11. Typische Nutzungsszenarien, 12. Häufige Probleme, 13. Kurzfassung für neue Benutzer, 1. Zweck der Anwendung, 2. Für wen ist BRIDGR gedacht? (+5 more)

### Community 33 - "Community 33"
Cohesion: 0.28
Nodes (9): Concept: Deterministic Alias Enrichment on Empty Results, Concept: Dual-Mode Chat (tool-use / prompt-only), Concept: EA Chatbot Vision (natural language IT landscape), Concept: execute_cypher Tool, Concept: Inbox Principle for Input/, Concept: LLM as Orchestrator, Concept: Two-Layer Architecture (Pipeline + Query), UI: Config Tab (+1 more)

### Community 34 - "Community 34"
Cohesion: 0.42
Nodes (6): str, sanitize_cypher_response(), test_sanitize_cypher_response_returns_plain_query_unchanged(), test_sanitize_cypher_response_strips_cypher_fence(), test_sanitize_cypher_response_strips_plain_fence(), test_sanitize_cypher_response_strips_surrounding_whitespace()

### Community 35 - "Community 35"
Cohesion: 0.14
Nodes (14): 8.1 Bereich `Import`, 8.3 Bereich `Wissensbasis`, 8. Tab `Konfiguration`, Button `Aktive CMDB-Dateien übernehmen`, Button `BPMN transformieren`, Button `CMDB nach Neo4j synchronisieren`, Button `Pipeline starten`, Feld `Aktive CMDB-Entities-Datei` (+6 more)

### Community 36 - "Community 36"
Cohesion: 0.15
Nodes (13): Architekturprinzip: Konfigurierbares Mapping — zwei Richtungen, unterschiedliche Kardinalität, Beziehungs-Mapping: m:1 auf Import, kanonisch auf Export, Dateistruktur `archimate_mapping.json`, Element-Mapping, Export (BRIDGR → ArchiMate): kanonischer Typ, Export (BRIDGR → ArchiMate): m:1 erlaubt, Import (ArchiMate → BRIDGR): m:1, Import (ArchiMate → BRIDGR): strikt 1:1 (+5 more)

### Community 37 - "Community 37"
Cohesion: 0.22
Nodes (10): Concept: Read-Only Cypher Validation, Finding: LLM Generates Multiple MATCH Statements Without WITH, Finding: LLM Generates UNION with Mismatched Aliases, Finding: LLM Uses Non-Schema Relationship HOSTET, Answer rules, Cypher examples, Cypher rules, Graph schema (+2 more)

### Community 38 - "Community 38"
Cohesion: 0.15
Nodes (13): 10.1 Zweck, 10.2 Abschnitt `Mapping konfigurieren`, 10.3 Abschnitt `Offene Zuordnungen`, 10.4 Abschnitt `Import`, 10.5 Abschnitt `Export`, 10. Tab `EA-Modell`, Button `Als ArchiMate exportieren`, Button `Importieren` (+5 more)

### Community 39 - "Community 39"
Cohesion: 0.15
Nodes (13): 8.2 Bereich `Einstellungen`, Abschnitt `CMDB-Spaltenmapping — Entities`, Abschnitt `CMDB-Spaltenmapping — Relationen`, Abschnitt `Datei-Pfade`, Abschnitt `Import & Matching`, Abschnitt `LLM`, Abschnitt `Neo4j`, Abschnitt `Pfade auswählen` (+5 more)

### Community 41 - "Community 41"
Cohesion: 0.15
Nodes (13): 9.1 Zweck, 9.2 Abschnitt `Organisationseinheiten`, 9.3 Abschnitt `Kandidaten`, 9.4 Abschnitt `Vorgeschlagene Prozess-Eigentümer`, 9.5 Abschnitt `Prozesse ohne Eigentümer`, 9.6 Abschnitt `Nicht zugeordnete Rollen`, 9.7 Abschnitt `Bereits entschiedene Kandidaten`, 9. Tab `Organisation` (+5 more)

### Community 42 - "Community 42"
Cohesion: 0.50
Nodes (4): match_application (skills/match), match_application_candidates (skills/match), normalize_name_for_matching (skills/match), Test Suite: Match Application

### Community 44 - "Community 44"
Cohesion: 0.18
Nodes (10): 14. Akzeptanzkriterien, 15. Getroffene Entscheidungen, 1. Ziel, 2. Gesamtarchitektur, 4. Scope v0.21, 6. Anwendungsschichten, 7. Importlogik, 8. Matching und Review (+2 more)

### Community 46 - "Community 46"
Cohesion: 0.18
Nodes (11): 5. Domaenenmodell, Anwendung, folgt_auf, Neue Properties aus ArchiMate-Import, OrgEinheit, Prozess, Rolle, Rollenzuordnung (+3 more)

### Community 49 - "Community 49"
Cohesion: 0.42
Nodes (6): str, validate_manual_application_name(), test_validate_manual_application_name_rejects_empty_value(), test_validate_manual_application_name_rejects_invalid_characters(), test_validate_manual_application_name_rejects_overlong_value(), test_validate_manual_application_name_returns_normalized_value()

### Community 50 - "Community 50"
Cohesion: 0.22
Nodes (9): 1. Information Architecture — kritisches Problem, 2. Tab 3 — Anwendungskonfig: zwei Welten in einem Tab, 3. Tab 2 — Link Editing: Redundanz und kognitive Überlastung, 4. Tab 4 — Organisation: Cramped Actions, 5. Sprachliche Konsistenz, 6. Kein Onboarding-Zustand, Gesamteindruck, Priorisierte Empfehlungen (+1 more)

### Community 62 - "Community 62"
Cohesion: 0.25
Nodes (8): 6.1 Zweck, 6.2 Bereich und Elemente, 6.3 Wichtige Hinweise, 6. Tab `Kommunikation`, Button `Als CSV exportieren`, Chat-Antworten, Chat-Eingabe `Frage an den Wissensgraphen`, `Neues Gespräch`

### Community 63 - "Community 63"
Cohesion: 0.25
Nodes (8): 16.1 Komponentendiagramm, 16.2 Klassenmodell, 16.3 Sequenzdiagramme, 16. UML-Diagramme, Sequenz 1 – Dokument-Import-Pipeline, Sequenz 2 – Natürlichsprachige Graph-Abfrage, Sequenz 3 – CMDB-Synchronisation, Sequenz 4 – Review: Anwendungslink bestätigen / ablehnen

### Community 64 - "Community 64"
Cohesion: 0.29
Nodes (7): Das Problem konkret, Das zentrale technische Problem: Identity Resolution, Lösungsansatz, Mehrsprachige Namen, Primäre Identität nach Fuzzy-Match-Bestätigung, Properties an importierten Knoten, Übersprungene Beziehungen bei unaufgelösten Endpoints

### Community 65 - "Community 65"
Cohesion: 0.29
Nodes (7): 10.1 Visionsziel, 10.2 Architekturprinzip: LLM als Orchestrator, 10.3 Tool: execute_cypher, 10.4 System-Prompt, 10.5 Konversationshistorie, 10.6 Dual-Mode-Betrieb, 10. Abfrage-Layer

### Community 66 - "Community 66"
Cohesion: 0.29
Nodes (7): 13.1 Services und Verantwortlichkeiten, 13.2 Import-Pipeline, 13.3 Export-Pipeline, 13.4 archimate_mapping.json — Struktur, 13.5 EA-Modell-Tab (Tab 5), 13.6 Bekannte Einschraenkungen (v0.21), 13. ArchiMate-Integration

### Community 67 - "Community 67"
Cohesion: 0.40
Nodes (5): 9.1 Vollstaendiges Schreibmodell, 9.2 Schreibregeln pro Quelle, 9.3 Idempotenz, 9.4 Kardinalitaet Prozess-Owner, 9. Graph Writer

### Community 68 - "Community 68"
Cohesion: 0.50
Nodes (4): 3.1 Benötigte Daten, 3.2 Benötigte technische Angaben, 3.3 Wichtige Ordner, 3. Voraussetzungen

### Community 69 - "Community 69"
Cohesion: 0.50
Nodes (4): 4.1 Anwendung starten, 4.2 Grundkonfiguration in BRIDGR, 4.3 Dateien vorbereiten, 4. Initiales Setup

### Community 70 - "Community 70"
Cohesion: 0.50
Nodes (4): 11.1 Bestehender Flow: OrgEinheiten und CMDB-Kandidaten, 11.2 Flow: Prozess-Owner-Pflege, 11.3 Flow: Rollenzuordnung, 11. Organisation-Tab (Tab 4)

### Community 71 - "Community 71"
Cohesion: 0.50
Nodes (4): 3.1 Eingangsdateien, 3.2 Inbox-Prinzip, 3.3 Archivierung verarbeiteter Dateien, 3. Inputs und Dateifluss

### Community 72 - "Community 72"
Cohesion: 0.67
Nodes (3): 12. Konfiguration, archimate_mapping.json (ArchiMate-Mapping-Konfiguration), config.json (Laufzeit-Konfiguration)

### Community 86 - "Community 86"
Cohesion: 0.15
Nodes (21): ArchiMateExportResult, _build_archimate_export(), export_graph_as_archimate(), fetch_untyped_nodes(), _normalize_rel_type(), AppConfig, Neo4jClient, str (+13 more)

### Community 87 - "Community 87"
Cohesion: 0.12
Nodes (16): Allgemeine Workflow-Beobachtungen, Beobachtung: Chat-History nach Seiten-Reload weg, Beobachtung: kein Undo, BRIDGR Feedback — Live-Review via Claude in Chrome, Finding #1 — Kontextauflösung bei Folgefragen / LLM überspringt Tool Call — ✅ ERLEDIGT, Positive Überraschung: Reaktionsgeschwindigkeit der UI, Priorisierungsübersicht, Sitzungsgebundenheit ist der größte Workflow-Bruch (+8 more)

### Community 88 - "Community 88"
Cohesion: 0.31
Nodes (14): save_archimate_mapping(), _confirm_candidate(), _do_export(), _ensure_import_rows_initialized(), str, Render per-AM-type rows with add/delete. Returns {AM-type -> BRIDGR-label}., _reject_candidate(), render_archimate_tab() (+6 more)

### Community 89 - "Community 89"
Cohesion: 0.18
Nodes (10): 14. Akzeptanzkriterien, 15. Getroffene Entscheidungen, 1. Ziel, 2. Gesamtarchitektur, 4. Scope v0.22, 6. Anwendungsschichten, 7. Importlogik, 8. Matching und Review (+2 more)

### Community 90 - "Community 90"
Cohesion: 0.18
Nodes (11): 5. Domaenenmodell, Anwendung, folgt_auf, Neue Properties aus ArchiMate-Import, OrgEinheit, Prozess, Rolle, Rollenzuordnung (+3 more)

### Community 91 - "Community 91"
Cohesion: 0.25
Nodes (9): ExtractedProcess (extract_base), BpmnExtractor (extract_bpmn), DocxExtractor (extract_docx), PdfExtractor (extract_pdf), TextExtractor (extract_txt), Test Suite: Extract BPMN, Test Suite: Extract DOCX, Test Suite: Extract PDF (+1 more)

### Community 92 - "Community 92"
Cohesion: 0.25
Nodes (8): 16.1 Komponentendiagramm, 16.2 Klassenmodell, 16.3 Sequenzdiagramme, 16. UML-Diagramme, Sequenz 1 – Dokument-Import-Pipeline, Sequenz 2 – Natürlichsprachige Graph-Abfrage, Sequenz 3 – CMDB-Synchronisation, Sequenz 4 – Review: Anwendungslink bestätigen / ablehnen

### Community 93 - "Community 93"
Cohesion: 0.29
Nodes (7): 10.1 Visionsziel, 10.2 Architekturprinzip: LLM als Orchestrator, 10.3 Tool: execute_cypher, 10.4 System-Prompt, 10.5 Konversationshistorie, 10.6 Dual-Mode-Betrieb, 10. Abfrage-Layer

### Community 94 - "Community 94"
Cohesion: 0.29
Nodes (7): 13.1 Services und Verantwortlichkeiten, 13.2 Import-Pipeline, 13.3 Export-Pipeline, 13.4 archimate_mapping.json — Struktur, 13.5 EA-Modell-Tab (Tab 5), 13.6 Bekannte Einschraenkungen (v0.22), 13. ArchiMate-Integration

### Community 95 - "Community 95"
Cohesion: 0.33
Nodes (6): 9.1 Vollstaendiges Schreibmodell, 9.2 Schreibregeln pro Quelle, 9.3 Idempotenz, 9.4 Kardinalitaet Prozess-Owner, 9.5 Attribut-Eigentuemer-Prinzip, 9. Graph Writer

### Community 96 - "Community 96"
Cohesion: 0.50
Nodes (3): AppConfig, str, write_debug_log()

### Community 97 - "Community 97"
Cohesion: 0.50
Nodes (4): 11.1 Bestehender Flow: OrgEinheiten und CMDB-Kandidaten, 11.2 Flow: Prozess-Owner-Pflege, 11.3 Flow: Rollenzuordnung, 11. Organisation-Tab (Tab 4)

### Community 98 - "Community 98"
Cohesion: 0.50
Nodes (4): 3.1 Eingangsdateien, 3.2 Inbox-Prinzip, 3.3 Archivierung verarbeiteter Dateien, 3. Inputs und Dateifluss

### Community 99 - "Community 99"
Cohesion: 0.67
Nodes (3): 12. Konfiguration, archimate_mapping.json (ArchiMate-Mapping-Konfiguration), config.json (Laufzeit-Konfiguration)

## Knowledge Gaps
- **454 isolated node(s):** `PreToolUse`, `llm_base_url`, `llm_model`, `llm_api_key_env`, `llm_context_window` (+449 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **30 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `AppConfig` connect `Community 18` to `Community 0`, `Community 1`, `Community 2`, `Community 3`, `Community 4`, `Community 5`, `Community 7`, `Community 10`, `Community 11`, `Community 14`, `Community 86`?**
  _High betweenness centrality (0.070) - this node is a cross-community bridge._
- **Why does `AppConfig` connect `Community 18` to `Community 96`, `Community 0`, `Community 2`, `Community 3`, `Community 4`, `Community 5`, `Community 7`, `Community 10`, `Community 11`, `Community 14`, `Community 86`?**
  _High betweenness centrality (0.057) - this node is a cross-community bridge._
- **Why does `Concept: Dual-Mode Chat (tool-use / prompt-only)` connect `Community 33` to `Community 26`, `Community 10`?**
  _High betweenness centrality (0.040) - this node is a cross-community bridge._
- **Are the 67 inferred relationships involving `AppConfig` (e.g. with `BPMN Extractor` and `DOCX Extractor`) actually correct?**
  _`AppConfig` has 67 INFERRED edges - model-reasoned connections that need verification._
- **Are the 73 inferred relationships involving `AppConfig` (e.g. with `AppConfig` and `str`) actually correct?**
  _`AppConfig` has 73 INFERRED edges - model-reasoned connections that need verification._
- **Are the 61 inferred relationships involving `ExtractedProcess` (e.g. with `AppConfig` and `ApplicationReference`) actually correct?**
  _`ExtractedProcess` has 61 INFERRED edges - model-reasoned connections that need verification._
- **Are the 46 inferred relationships involving `GraphWriter` (e.g. with `Extractor` and `GraphWriter`) actually correct?**
  _`GraphWriter` has 46 INFERRED edges - model-reasoned connections that need verification._
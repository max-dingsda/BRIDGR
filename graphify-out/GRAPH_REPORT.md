# Graph Report - BRIDGR  (2026-05-31)

## Corpus Check
- 97 files · ~99,358 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 1877 nodes · 5714 edges · 104 communities (87 shown, 17 thin omitted)
- Extraction: 77% EXTRACTED · 23% INFERRED · 0% AMBIGUOUS · INFERRED: 1301 edges (avg confidence: 0.52)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `6644adb5`
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
- [[_COMMUNITY_Community 50|Community 50]]
- [[_COMMUNITY_Community 51|Community 51]]
- [[_COMMUNITY_Community 52|Community 52]]
- [[_COMMUNITY_Community 53|Community 53]]
- [[_COMMUNITY_Community 54|Community 54]]
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
- [[_COMMUNITY_Community 74|Community 74]]
- [[_COMMUNITY_Community 75|Community 75]]
- [[_COMMUNITY_Community 76|Community 76]]
- [[_COMMUNITY_Community 77|Community 77]]
- [[_COMMUNITY_Community 78|Community 78]]
- [[_COMMUNITY_Community 79|Community 79]]
- [[_COMMUNITY_Community 80|Community 80]]
- [[_COMMUNITY_Community 81|Community 81]]
- [[_COMMUNITY_Community 82|Community 82]]
- [[_COMMUNITY_Community 83|Community 83]]
- [[_COMMUNITY_Community 85|Community 85]]
- [[_COMMUNITY_Community 94|Community 94]]
- [[_COMMUNITY_Community 95|Community 95]]
- [[_COMMUNITY_Community 96|Community 96]]
- [[_COMMUNITY_Community 97|Community 97]]
- [[_COMMUNITY_Community 98|Community 98]]
- [[_COMMUNITY_Community 99|Community 99]]
- [[_COMMUNITY_Community 100|Community 100]]
- [[_COMMUNITY_Community 101|Community 101]]
- [[_COMMUNITY_Community 102|Community 102]]
- [[_COMMUNITY_Community 103|Community 103]]

## God Nodes (most connected - your core abstractions)
1. `AppConfig` - 131 edges
2. `OpenAICompatibleClient` - 98 edges
3. `ExtractedProcess` - 92 edges
4. `GraphWriter` - 90 edges
5. `MatchResult` - 75 edges
6. `KnowledgeBase` - 66 edges
7. `LlmClientConfig` - 65 edges
8. `run_pipeline()` - 64 edges
9. `Neo4jClient` - 63 edges
10. `TextExtractor` - 60 edges

## Surprising Connections (you probably didn't know these)
- `AppConfig` --uses--> `AppConfig`  [INFERRED]
  debug_utils.py → app_config.py
- `str` --uses--> `AppConfig`  [INFERRED]
  debug_utils.py → app_config.py
- `AppConfig` --uses--> `AppConfig`  [INFERRED]
  services/import_service.py → app_config.py
- `Path` --uses--> `AppConfig`  [INFERRED]
  tests/test_import_service.py → app_config.py
- `test_run_document_builds_matches_and_review_items()` --calls--> `Graph Writer`  [EXTRACTED]
  tests/test_pipeline.py → Specs/Bridgr_Architektur_v09.md

## Communities (104 total, 17 thin omitted)

### Community 0 - "Community 0"
Cohesion: 0.08
Nodes (47): Any, _extract_return_aliases(), _has_match_after_return_without_transition(), Neo4jAuthenticationError, Neo4jQuerySyntaxError, _strip_cypher_strings_and_comments(), _translate_neo4j_exception(), _validate_query_structure() (+39 more)

### Community 1 - "Community 1"
Cohesion: 0.06
Nodes (30): 10. Abfrage-Layer, 11. Anwendungskonfig, 12. Akzeptanzkriterien, 13. Getroffene Entscheidungen, 1. Ziel, 2. Gesamtarchitektur, 3. Inputs, 4. Scope v0.14 (+22 more)

### Community 2 - "Community 2"
Cohesion: 0.16
Nodes (31): CmdbEntity, CmdbRelation, NormalizedCmdb, Graph Writer, CmdbEntity, CmdbRelation, ExtractedProcess, Neo4jClient (+23 more)

### Community 3 - "Community 3"
Cohesion: 0.04
Nodes (44): 10. Betrieb, 11. Akzeptanzkriterien (v1 / PoC), 12. Differenzierung, 13. Offene Punkte, 14. Getroffene Entscheidungen, 1. Ziel, 2. Gesamtarchitektur, 3. Inputs (+36 more)

### Community 4 - "Community 4"
Cohesion: 0.10
Nodes (59): bool, ExtractedProcess, float, int, MatchResult, Neo4jClient, Path, BpmnTransformError (+51 more)

### Community 5 - "Community 5"
Cohesion: 0.09
Nodes (76): clear_knowledge_base_and_refresh(), render_manual_link_form(), render_review_actions(), render_review_item_actions(), render_manual_link_form(), render_organization_tab(), render_review_actions(), render_review_item_actions() (+68 more)

### Community 6 - "Community 6"
Cohesion: 0.11
Nodes (41): OrgUnitCandidate, OrgUnitEntry, RejectedLink, ConfirmedLink, float, confirmed, disambiguation, confirmed (+33 more)

### Community 7 - "Community 7"
Cohesion: 0.09
Nodes (61): render_path_picker_controls(), normalize_run_mode(), _csv_has_columns(), describe_cmdb_file(), list_cmdb_entity_files(), list_cmdb_files(), list_cmdb_relation_files(), list_process_files() (+53 more)

### Community 8 - "Community 8"
Cohesion: 0.06
Nodes (30): 10. Abfrage-Layer, 11. Anwendungskonfig, 12. Ausbau-Reihenfolge fuer unstrukturierte Formate, 13. Akzeptanzkriterien, 14. Getroffene Entscheidungen, 1. Ziel, 2. Gesamtarchitektur, 3. Inputs (+22 more)

### Community 9 - "Community 9"
Cohesion: 0.06
Nodes (71): build_query_schema_reference(), _extract_variable_labels(), RelationshipPattern, _resolve_labels(), _validate_labels(), _validate_properties(), validate_query_schema(), _validate_relationship_patterns() (+63 more)

### Community 10 - "Community 10"
Cohesion: 0.06
Nodes (30): cmdb_entity_type_column, cmdb_filename, cmdb_multivalue_separator, cmdb_name_column, cmdb_owner_name_column, cmdb_relation_source_column, cmdb_relation_target_column, cmdb_relation_type_column (+22 more)

### Community 11 - "Community 11"
Cohesion: 0.04
Nodes (44): 10. Betrieb, 11. Akzeptanzkriterien (v1 / PoC), 12. Differenzierung, 13. Offene Punkte, 14. Getroffene Entscheidungen, 1. Ziel, 2. Gesamtarchitektur, 3. Inputs (+36 more)

### Community 12 - "Community 12"
Cohesion: 0.15
Nodes (12): files, code, document, image, paper, video, graphifyignore_patterns, needs_graph (+4 more)

### Community 13 - "Community 13"
Cohesion: 0.04
Nodes (44): 10. Betrieb, 11. Akzeptanzkriterien (v1 / PoC), 12. Differenzierung, 13. Offene Punkte, 14. Getroffene Entscheidungen, 1. Ziel, 2. Gesamtarchitektur, 3. Inputs (+36 more)

### Community 14 - "Community 14"
Cohesion: 0.31
Nodes (7): extract_bpmn_process_ids(), str, Return all BPMN process ids found in the given XML text., identity.py ist ein Minimal-Stub, test_extract_bpmn_process_ids_raises_for_malformed_xml(), test_extract_bpmn_process_ids_returns_all_process_ids(), test_extract_bpmn_process_ids_returns_empty_list_when_no_processes()

### Community 15 - "Community 15"
Cohesion: 0.33
Nodes (5): edges, hyperedges, input_tokens, nodes, output_tokens

### Community 16 - "Community 16"
Cohesion: 0.33
Nodes (5): edges, hyperedges, input_tokens, nodes, output_tokens

### Community 17 - "Community 17"
Cohesion: 0.47
Nodes (6): DocuSign, Microsoft Excel, SAP SRM, SAP FI, SAP SD, SAP WM

### Community 18 - "Community 18"
Cohesion: 0.40
Nodes (4): edges, input_tokens, nodes, output_tokens

### Community 19 - "Community 19"
Cohesion: 0.18
Nodes (10): documents, import_archive_path, import_archived_files, documents, output_path, run_mode, used_output_fallback, output_path (+2 more)

### Community 34 - "Community 34"
Cohesion: 0.08
Nodes (24): code:bash (mkdir -p graphify-out), code:bash ($(cat .graphify_python) -c "), code:bash ($(cat .graphify_python) -c "), code:bash ($(cat .graphify_python) -c "), code:bash ($(cat .graphify_python) -c "), code:bash (# Detect the correct Python interpreter (handles pipx, venv,), code:bash ($(cat .graphify_python) -c "), code:bash ($(cat .graphify_python) -c ") (+16 more)

### Community 35 - "Community 35"
Cohesion: 0.05
Nodes (42): 10. Betrieb, 11. Akzeptanzkriterien (v1 / PoC), 12. Differenzierung, 13. Offene Punkte, 1. Ziel, 2. Gesamtarchitektur, 3. Inputs, 4. MVP-Scope (v1) (+34 more)

### Community 36 - "Community 36"
Cohesion: 0.12
Nodes (16): code:block1 (/graphify                                             # full), code:bash ($(cat .graphify_python) -c "), code:bash ($(cat .graphify_python) -c "), code:bash (python3 -m graphify.watch INPUT_PATH --debounce 3), code:bash (graphify hook install    # install), code:bash (graphify claude install), code:bash (graphify claude uninstall  # remove the section), For --cluster-only (+8 more)

### Community 37 - "Community 37"
Cohesion: 0.06
Nodes (34): 10. Differenzierung, 11. Offene Punkte, 1. Ziel, 2. Gesamtarchitektur, 3. Inputs, 4. MVP-Scope (v1), 5.1 Projektstruktur, 5.2 Komponenten (+26 more)

### Community 38 - "Community 38"
Cohesion: 0.06
Nodes (32): 1. Ziel, 2. Gesamtarchitektur, 3. Inputs, 4.1 Projektstruktur, 4.2 Komponenten, 4. Pipeline, 5. Graph-Datenmodell, 6. Abfrage-Layer (+24 more)

### Community 39 - "Community 39"
Cohesion: 0.06
Nodes (30): Architektur-Compliance, Aufgegriffen und umgesetzt, Bewusst zurueckgestellt, Bridgr — Code Review Findings, code:python (# Aktuell: pauschal), F-01 — Hardcodierte Produktions-Credentials in config.json, F-02 — Generische Exception-Behandlung in `neo4j_utils.py`, F-03 — LLM-Client verwendet `urllib` statt `requests` (+22 more)

### Community 40 - "Community 40"
Cohesion: 0.07
Nodes (28): 10. Abfrage-Layer, 11. Anwendungskonfig, 12. Ausbau-Reihenfolge fuer unstrukturierte Formate, 13. Akzeptanzkriterien, 14. Getroffene Entscheidungen, 1. Ziel, 2. Gesamtarchitektur, 3. Inputs (+20 more)

### Community 41 - "Community 41"
Cohesion: 0.07
Nodes (26): 1. Abhaengigkeiten, 2. Streamlit starten, 3. Pipeline per CLI starten, Aktuelle UI-Funktionen, Aktueller Stand, BPMN-Transformer fuer grosse Modelle, code:text (BRIDGR/), code:json ({) (+18 more)

### Community 42 - "Community 42"
Cohesion: 0.10
Nodes (27): Bridgr, ABFRAGE-LAYER (Nutzung), Anwendung, CMDB-Export, Konfiguration, Delta Update, BPMN-Extraktion, generische Extraktion (+19 more)

### Community 43 - "Community 43"
Cohesion: 0.50
Nodes (3): Eingesetzte Software, Prozessbeschreibung: Lieferantenmanagement, Prozessschritte

### Community 50 - "Community 50"
Cohesion: 0.05
Nodes (38): 10. Abfrage-Layer, 11. Anwendungskonfig, 12. Akzeptanzkriterien, 13. Getroffene Entscheidungen, 1. Ziel, 2. Gesamtarchitektur, 3.1 Eingangsdateien, 3.2 Inbox-Prinzip (+30 more)

### Community 52 - "Community 52"
Cohesion: 0.06
Nodes (34): 10. Abfrage-Layer, 11. Anwendungskonfig, 12. Akzeptanzkriterien, 13. Getroffene Entscheidungen, 1. Ziel, 2. Gesamtarchitektur, 3.1 Eingangsdateien, 3.2 Inbox-Prinzip (+26 more)

### Community 53 - "Community 53"
Cohesion: 0.20
Nodes (28): bool, int, object, Path, str, _build_process_transform_text(), _build_transform_filename(), _build_transform_text() (+20 more)

### Community 54 - "Community 54"
Cohesion: 0.15
Nodes (13): code:block10 (You are a graphify extraction subagent. Read the files liste), code:bash ($(cat graphify-out/.graphify_python) -c "), code:bash ($(cat .graphify_python) -c "), code:bash ($(cat .graphify_python) -c "), code:bash ($(cat .graphify_python) -c "), code:bash ($(cat .graphify_python) -c "), code:bash ($(cat .graphify_python) -c "), code:block8 (spawn_agent(agent_type="worker", message="Your task is to pe) (+5 more)

### Community 55 - "Community 55"
Cohesion: 0.12
Nodes (40): Neo4jServiceUnavailableError, build_extractor_for_path(), list_bpmn_files(), resolve_cmdb_owner_assignments(), run_pipeline(), should_skip_file(), update_organization_knowledge(), update_organization_knowledge_from_cmdb() (+32 more)

### Community 56 - "Community 56"
Cohesion: 0.48
Nodes (5): validate_manual_application_name(), test_validate_manual_application_name_rejects_empty_value(), test_validate_manual_application_name_rejects_invalid_characters(), test_validate_manual_application_name_rejects_overlong_value(), test_validate_manual_application_name_returns_normalized_value()

### Community 57 - "Community 57"
Cohesion: 0.33
Nodes (6): code:bash ($(cat .graphify_python) -c "), code:bash ($(cat .graphify_python) -c "), code:bash (if [ ! -f graphify-out/.graphify_extract.json ]; then), code:bash ($(cat .graphify_python) -c "), code:bash ($(cat .graphify_python) -c "), For --update (incremental re-extraction)

### Community 58 - "Community 58"
Cohesion: 0.20
Nodes (27): AppConfig, AppConfig, append_chat_message(), build_neo4j_client_key(), clear_knowledge_base_and_refresh(), ensure_active_cmdb_selection(), ensure_config_session_defaults(), ensure_import_session_defaults() (+19 more)

### Community 59 - "Community 59"
Cohesion: 0.50
Nodes (4): code:bash ($(cat .graphify_python) -c "), code:bash ($(cat .graphify_python) -c "), code:bash ($(cat .graphify_python) -m graphify save-result --question "), For /graphify query

### Community 60 - "Community 60"
Cohesion: 0.50
Nodes (4): code:bash ($(cat .graphify_python) -c "), code:bash ($(cat .graphify_python) -c "), code:bash ($(cat .graphify_python) -m graphify save-result --question "), For /graphify path

### Community 61 - "Community 61"
Cohesion: 0.50
Nodes (4): code:bash ($(cat .graphify_python) -c "), code:bash ($(cat .graphify_python) -c "), code:bash ($(cat .graphify_python) -m graphify save-result --question "), For /graphify explain

### Community 62 - "Community 62"
Cohesion: 0.67
Nodes (3): code:bash ($(cat .graphify_python) -c "), code:block27 (Graph complete. Outputs in PATH_TO_DIR/graphify-out/), Step 9 - Save manifest, update cost tracker, clean up, and report

### Community 63 - "Community 63"
Cohesion: 0.67
Nodes (3): code:bash ($(cat .graphify_python) -c "), code:block4 (Corpus: X files · ~Y words), Step 2 - Detect files

### Community 64 - "Community 64"
Cohesion: 0.05
Nodes (38): 10. Abfrage-Layer, 11. Anwendungskonfig, 12. Akzeptanzkriterien, 13. Getroffene Entscheidungen, 1. Ziel, 2. Gesamtarchitektur, 3.1 Eingangsdateien, 3.2 Inbox-Prinzip (+30 more)

### Community 65 - "Community 65"
Cohesion: 0.14
Nodes (40): CmdbLoadError, CmdbValidationIssue, _collect_csv_shape_issues(), find_cmdb_row_by_label(), load_cmdb_relation_rows(), load_cmdb_rows(), load_normalized_cmdb(), normalize_cmdb_entities() (+32 more)

### Community 66 - "Community 66"
Cohesion: 0.05
Nodes (38): 10. Abfrage-Layer, 11. Anwendungskonfig, 12. Akzeptanzkriterien, 13. Getroffene Entscheidungen, 1. Ziel, 2. Gesamtarchitektur, 3.1 Eingangsdateien, 3.2 Inbox-Prinzip (+30 more)

### Community 67 - "Community 67"
Cohesion: 0.37
Nodes (37): ConfirmedLink, Neo4jClient, Neo4jConfig, build_manual_matches(), build_neo4j_client(), DocumentRunResult, PipelineRunResult, resolve_org_units() (+29 more)

### Community 68 - "Community 68"
Cohesion: 0.12
Nodes (28): AppConfig, ensure_import_session_defaults(), ensure_query_chat_defaults(), sync_config_session_defaults(), AppConfig, ensure_query_chat_defaults(), get_llm_status(), sync_config_session_defaults() (+20 more)

### Community 69 - "Community 69"
Cohesion: 0.06
Nodes (47): is_legacy_input_path(), normalize_path_value(), bool, Path, str, Normalize a path value for stable comparisons across slash styles., Return whether the given path still points to the pre-Input legacy folder., is_directory_writable() (+39 more)

### Community 70 - "Community 70"
Cohesion: 0.15
Nodes (12): 1. `skills/review.py::collect_review_items` — komplett ungetestet, 2. CMDB-Validierung — fehlende Fehlerpfade, 3. Graph-Schema-Validierung — fehlende Richtungs- und Label-Tests, 4. `skills/graph_writer.py` — fehlende Zweige, 5. `skills/identity.py` — Edge Cases, Ausgangslage, Beobachtungen ohne neue Tests, BRIDGR — Test Audit (External Review) (+4 more)

### Community 71 - "Community 71"
Cohesion: 0.14
Nodes (35): render_document_status_table(), render_duplicate_application_warnings(), render_latest_run_summary(), build_document_details(), build_document_status_rows(), build_duplicate_application_warnings(), build_review_rows(), _collect_document_scope() (+27 more)

### Community 72 - "Community 72"
Cohesion: 0.40
Nodes (4): archive_path, display_paths, run_mode, source_paths

### Community 73 - "Community 73"
Cohesion: 0.13
Nodes (19): ApplicationReference, apply_org_unit_mapping(), ApplicationReference, BpmnExtractor, bool, ExtractedProcess, int, OpenAICompatibleClient (+11 more)

### Community 74 - "Community 74"
Cohesion: 0.13
Nodes (14): 1. Information Architecture — kritisches Problem, 2. Tab 3 — Anwendungskonfig: zwei Welten in einem Tab, 3. Tab 2 — Link Editing: Redundanz und kognitive Überlastung, 4. Tab 4 — Organisation: Cramped Actions, 5. Sprachliche Konsistenz, 6. Kein Onboarding-Zustand, code:block1 (Konfigurieren → Importieren → Reviewen → Abfragen), code:block2 (Kommunikation | Link Editing | Anwendungskonfig | Organisati) (+6 more)

### Community 75 - "Community 75"
Cohesion: 0.29
Nodes (6): confirmed, disambiguation, org_unit_candidates, org_units, process_identity, rejected

### Community 76 - "Community 76"
Cohesion: 0.29
Nodes (6): confirmed, disambiguation, org_unit_candidates, org_units, process_identity, rejected

### Community 77 - "Community 77"
Cohesion: 0.29
Nodes (6): confirmed, disambiguation, org_unit_candidates, org_units, process_identity, rejected

### Community 78 - "Community 78"
Cohesion: 0.40
Nodes (4): documents, output_path, run_mode, used_output_fallback

### Community 79 - "Community 79"
Cohesion: 0.40
Nodes (4): documents, output_path, run_mode, used_output_fallback

### Community 80 - "Community 80"
Cohesion: 0.40
Nodes (4): documents, output_path, run_mode, used_output_fallback

### Community 85 - "Community 85"
Cohesion: 0.14
Nodes (18): TextExtractor, Path, str, Path, str, bool, ExtractedProcess, OpenAICompatibleClient (+10 more)

### Community 94 - "Community 94"
Cohesion: 0.14
Nodes (24): append_chat_message(), build_neo4j_client_key(), get_session_neo4j_client(), handle_query_clarification(), main(), render_query_chat_messages(), render_query_tab(), reset_session_neo4j_client() (+16 more)

### Community 95 - "Community 95"
Cohesion: 0.19
Nodes (23): load_last_import_context(), load_last_import_selection(), load_latest_run(), save_last_import_selection(), write_latest_run(), load_latest_run(), Any, Path (+15 more)

### Community 96 - "Community 96"
Cohesion: 0.24
Nodes (22): str, build_pipeline_progress_callback(), clear_pipeline_run_tracker(), clear_run_feedback(), create_pipeline_run_tracker(), fail_pipeline_run_tracker(), finish_pipeline_run_tracker(), format_duration() (+14 more)

### Community 97 - "Community 97"
Cohesion: 0.25
Nodes (19): build_cmdb_option_labels(), apply_pending_review_scope_defaults(), test_pending_review_scope_defaults_can_be_requested_and_applied(), test_filter_application_cmdb_rows_keeps_only_applications(), _filter_application_cmdb_rows(), AppConfig, str, render_document_details() (+11 more)

### Community 98 - "Community 98"
Cohesion: 0.21
Nodes (15): load_config(), resolve_env_backed_value(), load_config(), _load_env_file(), load_env_files(), build_argument_parser(), main(), run_pipeline() (+7 more)

### Community 99 - "Community 99"
Cohesion: 0.24
Nodes (14): is_directory_writable(), Return the absolute path to the configured CMDB file.      The returned path may, Return a writable output directory and whether a fallback was used.      Unlike, Return an absolute project path.      This helper resolves relative paths agains, resolve_input_cmdb_path(), resolve_project_path(), resolve_runtime_output_path(), save_config() (+6 more)

### Community 100 - "Community 100"
Cohesion: 0.36
Nodes (13): MatchResult, collect_review_items(), ExtractedProcess, MatchResult, _make_process(), ExtractedProcess, test_collect_review_items_excludes_rejected_match(), test_collect_review_items_excludes_strong_match_with_cmdb_id() (+5 more)

### Community 101 - "Community 101"
Cohesion: 0.42
Nodes (7): PdfExtractor, FakeLlmClient, MonkeyPatch, Path, str, test_pdf_extractor_reads_page_text(), test_pdf_extractor_rejects_documents_without_text()

### Community 102 - "Community 102"
Cohesion: 0.39
Nodes (6): FakeLlmClient, MonkeyPatch, Path, str, test_docx_extractor_reads_paragraphs_and_tables(), test_docx_extractor_rejects_documents_without_text()

### Community 103 - "Community 103"
Cohesion: 0.29
Nodes (7): render_document_details(), render_document_status_table(), render_duplicate_application_warnings(), render_knowledge_base_tools(), render_latest_run_summary(), render_review_items_table(), render_review_tab()

## Knowledge Gaps
- **607 isolated node(s):** `int`, `llm_base_url`, `llm_model`, `llm_api_key_env`, `llm_context_window` (+602 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **17 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `OpenAICompatibleClient` connect `Community 4` to `Community 96`, `Community 67`, `Community 68`, `Community 7`, `Community 73`, `Community 9`, `Community 85`, `Community 55`, `Community 58`, `Community 94`?**
  _High betweenness centrality (0.032) - this node is a cross-community bridge._
- **Why does `AppConfig` connect `Community 68` to `Community 96`, `Community 97`, `Community 98`, `Community 99`, `Community 67`, `Community 5`, `Community 69`, `Community 7`, `Community 4`, `Community 9`, `Community 2`, `Community 55`, `Community 58`, `Community 94`, `Community 95`?**
  _High betweenness centrality (0.029) - this node is a cross-community bridge._
- **Why does `BRIDGR` connect `Community 10` to `Community 98`, `Community 94`, `Community 55`?**
  _High betweenness centrality (0.021) - this node is a cross-community bridge._
- **Are the 68 inferred relationships involving `AppConfig` (e.g. with `AppConfig` and `str`) actually correct?**
  _`AppConfig` has 68 INFERRED edges - model-reasoned connections that need verification._
- **Are the 68 inferred relationships involving `OpenAICompatibleClient` (e.g. with `DocumentRunResult` and `PipelineRunResult`) actually correct?**
  _`OpenAICompatibleClient` has 68 INFERRED edges - model-reasoned connections that need verification._
- **Are the 67 inferred relationships involving `ExtractedProcess` (e.g. with `DocumentRunResult` and `PipelineRunResult`) actually correct?**
  _`ExtractedProcess` has 67 INFERRED edges - model-reasoned connections that need verification._
- **Are the 51 inferred relationships involving `GraphWriter` (e.g. with `DocumentRunResult` and `PipelineRunResult`) actually correct?**
  _`GraphWriter` has 51 INFERRED edges - model-reasoned connections that need verification._
# Graph Report - BRIDGR  (2026-05-28)

## Corpus Check
- 75 files · ~40,419 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 1303 nodes · 3963 edges · 69 communities (54 shown, 15 thin omitted)
- Extraction: 75% EXTRACTED · 25% INFERRED · 0% AMBIGUOUS · INFERRED: 994 edges (avg confidence: 0.51)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `d4626ca4`
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
- [[_COMMUNITY_Community 71|Community 71]]
- [[_COMMUNITY_Community 72|Community 72]]

## God Nodes (most connected - your core abstractions)
1. `OpenAICompatibleClient` - 78 edges
2. `ExtractedProcess` - 75 edges
3. `AppConfig` - 71 edges
4. `str` - 60 edges
5. `TextExtractor` - 59 edges
6. `BpmnExtractor` - 58 edges
7. `GraphWriter` - 57 edges
8. `MatchResult` - 56 edges
9. `OpenAICompatibleClient` - 54 edges
10. `run_pipeline()` - 52 edges

## Surprising Connections (you probably didn't know these)
- `AppConfig` --uses--> `AppConfig`  [INFERRED]
  debug_utils.py → app_config.py
- `str` --uses--> `AppConfig`  [INFERRED]
  debug_utils.py → app_config.py
- `Microsoft Excel` --semantically_similar_to--> `SAP WM`  [INFERRED] [semantically similar]
  graphify-out/converted/Prozess_Lieferantenmanagement_59c1777d.md → Input/Prozess_Bestellabwicklung.txt
- `DocuSign` --semantically_similar_to--> `SAP SD`  [INFERRED] [semantically similar]
  graphify-out/converted/Prozess_Lieferantenmanagement_59c1777d.md → Input/Prozess_Bestellabwicklung.txt
- `AppConfig` --uses--> `BpmnTransformError`  [INFERRED]
  app.py → bpmn_transformer.py

## Communities (69 total, 15 thin omitted)

### Community 0 - "Community 0"
Cohesion: 0.10
Nodes (31): Any, _extract_return_aliases(), _has_match_after_return_without_transition(), Neo4jAuthenticationError, _strip_cypher_strings_and_comments(), _translate_neo4j_exception(), _validate_query_structure(), validate_read_only_cypher() (+23 more)

### Community 1 - "Community 1"
Cohesion: 0.11
Nodes (35): append_chat_message(), Return the absolute path to the configured CMDB file.      The returned path may, Return an absolute project path.      This helper resolves relative paths agains, resolve_input_cmdb_path(), resolve_project_path(), save_config(), ensure_config_session_defaults(), handle_query_clarification() (+27 more)

### Community 2 - "Community 2"
Cohesion: 0.07
Nodes (124): ExtractedProcess, MatchResult, Graph Writer, ConfirmedLink, LlmClientConfig, Neo4jClient, Neo4jConfig, Neo4jConnectionError (+116 more)

### Community 3 - "Community 3"
Cohesion: 0.04
Nodes (44): 10. Betrieb, 11. Akzeptanzkriterien (v1 / PoC), 12. Differenzierung, 13. Offene Punkte, 14. Getroffene Entscheidungen, 1. Ziel, 2. Gesamtarchitektur, 3. Inputs (+36 more)

### Community 4 - "Community 4"
Cohesion: 0.09
Nodes (38): ApplicationReference, _extract_json_object(), LlmClientError, OpenAICompatibleClient, _parse_json_content(), Exception, _extract_json_object(), LlmClientConfig (+30 more)

### Community 5 - "Community 5"
Cohesion: 0.09
Nodes (37): is_directory_writable(), is_legacy_input_path(), normalize_path_value(), bool, Path, str, Return a writable output directory and whether a fallback was used.      Unlike, Normalize a path value for stable comparisons across slash styles. (+29 more)

### Community 6 - "Community 6"
Cohesion: 0.13
Nodes (35): OrgUnitCandidate, OrgUnitEntry, RejectedLink, ConfirmedLink, float, confirmed, disambiguation, org_unit_candidates (+27 more)

### Community 7 - "Community 7"
Cohesion: 0.10
Nodes (27): Bridgr, ABFRAGE-LAYER (Nutzung), Anwendung, CMDB-Export, Konfiguration, Delta Update, BPMN-Extraktion, generische Extraktion (+19 more)

### Community 8 - "Community 8"
Cohesion: 0.06
Nodes (30): 10. Abfrage-Layer, 11. Anwendungskonfig, 12. Ausbau-Reihenfolge fuer unstrukturierte Formate, 13. Akzeptanzkriterien, 14. Getroffene Entscheidungen, 1. Ziel, 2. Gesamtarchitektur, 3. Inputs (+22 more)

### Community 9 - "Community 9"
Cohesion: 0.10
Nodes (38): build_query_schema_reference(), answer_question(), build_natural_language_answer(), _extract_application_name_from_row(), find_application_ambiguity_options(), generate_cypher_from_question(), resolve_application_clarification(), sanitize_cypher_response() (+30 more)

### Community 10 - "Community 10"
Cohesion: 0.08
Nodes (28): cmdb_filename, cmdb_name_column, cmdb_uuid_column, debug_mode, fuzzy_threshold, input_path, last_run_mode, llm_api_key_env (+20 more)

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
Cohesion: 0.33
Nodes (5): extract_bpmn_process_ids(), str, Return all BPMN process ids found in the given XML text., identity.py ist ein Minimal-Stub, test_extract_bpmn_process_ids_returns_all_process_ids()

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
Cohesion: 0.40
Nodes (4): documents, output_path, run_mode, used_output_fallback

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
Cohesion: 0.22
Nodes (23): build_neo4j_client_key(), get_session_neo4j_client(), bool, float, int, Neo4jClient, Path, BpmnTransformError (+15 more)

### Community 43 - "Community 43"
Cohesion: 0.50
Nodes (3): Eingesetzte Software, Prozessbeschreibung: Lieferantenmanagement, Prozessschritte

### Community 50 - "Community 50"
Cohesion: 0.15
Nodes (29): render_document_status_table(), render_duplicate_application_warnings(), render_document_status_table(), render_duplicate_application_warnings(), build_document_details(), build_document_status_rows(), build_duplicate_application_warnings(), build_review_rows() (+21 more)

### Community 52 - "Community 52"
Cohesion: 0.25
Nodes (21): str, build_pipeline_progress_callback(), clear_pipeline_run_tracker(), clear_run_feedback(), create_pipeline_run_tracker(), fail_pipeline_run_tracker(), finish_pipeline_run_tracker(), format_duration() (+13 more)

### Community 53 - "Community 53"
Cohesion: 0.20
Nodes (28): bool, int, object, Path, str, _build_process_transform_text(), _build_transform_filename(), _build_transform_text() (+20 more)

### Community 54 - "Community 54"
Cohesion: 0.15
Nodes (13): code:block10 (You are a graphify extraction subagent. Read the files liste), code:bash ($(cat graphify-out/.graphify_python) -c "), code:bash ($(cat .graphify_python) -c "), code:bash ($(cat .graphify_python) -c "), code:bash ($(cat .graphify_python) -c "), code:bash ($(cat .graphify_python) -c "), code:bash ($(cat .graphify_python) -c "), code:block8 (spawn_agent(agent_type="worker", message="Your task is to pe) (+5 more)

### Community 55 - "Community 55"
Cohesion: 0.11
Nodes (52): clear_knowledge_base_and_refresh(), render_document_details(), render_manual_link_form(), render_review_actions(), render_review_item_actions(), clear_knowledge_base_and_refresh(), render_manual_link_form(), render_organization_tab() (+44 more)

### Community 56 - "Community 56"
Cohesion: 0.31
Nodes (11): ensure_active_cmdb_selection(), render_import_section(), list_cmdb_files(), list_process_files(), sanitize_uploaded_name(), save_uploaded_file(), Path, test_list_cmdb_files_returns_csv_files() (+3 more)

### Community 57 - "Community 57"
Cohesion: 0.33
Nodes (6): code:bash ($(cat .graphify_python) -c "), code:bash ($(cat .graphify_python) -c "), code:bash (if [ ! -f graphify-out/.graphify_extract.json ]; then), code:bash ($(cat .graphify_python) -c "), code:bash ($(cat .graphify_python) -c "), For --update (incremental re-extraction)

### Community 58 - "Community 58"
Cohesion: 0.12
Nodes (48): AppConfig, ensure_import_session_defaults(), ensure_query_chat_defaults(), AppConfig, reset_session_neo4j_client(), sync_config_session_defaults(), AppConfig, build_neo4j_client_key() (+40 more)

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
Cohesion: 0.36
Nodes (7): DuplicateApplicationLlmClient, FakeLlmClient, Path, str, test_bpmn_extractor_prefers_modeled_application_name_and_deduplicates_variants(), test_bpmn_extractor_rejects_invalid_xml(), test_bpmn_extractor_returns_domain_model()

### Community 65 - "Community 65"
Cohesion: 0.33
Nodes (8): FakeLlmClient, Path, str, test_text_extractor_prefers_explicit_process_id_from_document_text(), test_text_extractor_reads_lane_labels_from_bpmn_transform_text_as_roles(), test_text_extractor_rejects_invalid_payload(), test_text_extractor_returns_domain_model(), test_text_extractor_uses_payload_process_id_when_present()

### Community 66 - "Community 66"
Cohesion: 0.47
Nodes (8): load_config(), resolve_env_backed_value(), load_config(), Path, test_load_config_keeps_explicit_local_neo4j_values_even_if_they_match_defaults(), test_load_config_keeps_explicit_neo4j_config_values(), test_load_config_prefers_neo4j_env_over_local_defaults(), test_load_config_uses_neo4j_env_fallbacks()

### Community 71 - "Community 71"
Cohesion: 0.23
Nodes (18): persist_latest_run_refresh(), persist_org_candidate_mapping_refresh(), persist_single_document_refresh(), reconstruct_extracted_process(), reconstruct_match_result(), rerun_single_document_from_artifact(), compute_file_hash(), load_last_import_selection() (+10 more)

## Knowledge Gaps
- **398 isolated node(s):** `int`, `llm_base_url`, `llm_model`, `llm_api_key_env`, `llm_context_window` (+393 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **15 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `OpenAICompatibleClient` connect `Community 4` to `Community 1`, `Community 2`, `Community 9`, `Community 42`, `Community 52`, `Community 58`?**
  _High betweenness centrality (0.040) - this node is a cross-community bridge._
- **Why does `transform_bpmn_for_import()` connect `Community 53` to `Community 1`, `Community 42`, `Community 52`?**
  _High betweenness centrality (0.033) - this node is a cross-community bridge._
- **Why does `OpenAICompatibleClient` connect `Community 4` to `Community 1`, `Community 2`, `Community 9`, `Community 42`, `Community 52`, `Community 58`?**
  _High betweenness centrality (0.020) - this node is a cross-community bridge._
- **Are the 54 inferred relationships involving `OpenAICompatibleClient` (e.g. with `AppConfig` and `str`) actually correct?**
  _`OpenAICompatibleClient` has 54 INFERRED edges - model-reasoned connections that need verification._
- **Are the 57 inferred relationships involving `ExtractedProcess` (e.g. with `AppConfig` and `str`) actually correct?**
  _`ExtractedProcess` has 57 INFERRED edges - model-reasoned connections that need verification._
- **Are the 32 inferred relationships involving `AppConfig` (e.g. with `AppConfig` and `str`) actually correct?**
  _`AppConfig` has 32 INFERRED edges - model-reasoned connections that need verification._
- **Are the 24 inferred relationships involving `str` (e.g. with `AppConfig` and `BpmnTransformError`) actually correct?**
  _`str` has 24 INFERRED edges - model-reasoned connections that need verification._
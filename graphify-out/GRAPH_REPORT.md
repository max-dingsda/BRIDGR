# Graph Report - BRIDGR  (2026-05-28)

## Corpus Check
- 88 files · ~51,216 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 1581 nodes · 5105 edges · 70 communities (56 shown, 14 thin omitted)
- Extraction: 76% EXTRACTED · 24% INFERRED · 0% AMBIGUOUS · INFERRED: 1248 edges (avg confidence: 0.52)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `1bba4b95`
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
- [[_COMMUNITY_Community 69|Community 69]]
- [[_COMMUNITY_Community 72|Community 72]]

## God Nodes (most connected - your core abstractions)
1. `AppConfig` - 112 edges
2. `OpenAICompatibleClient` - 96 edges
3. `ExtractedProcess` - 86 edges
4. `GraphWriter` - 80 edges
5. `MatchResult` - 67 edges
6. `LlmClientConfig` - 63 edges
7. `Neo4jClient` - 63 edges
8. `run_pipeline()` - 63 edges
9. `TextExtractor` - 60 edges
10. `str` - 60 edges

## Surprising Connections (you probably didn't know these)
- `AppConfig` --uses--> `AppConfig`  [INFERRED]
  services/import_service.py → app_config.py
- `Path` --uses--> `AppConfig`  [INFERRED]
  tests/test_import_service.py → app_config.py
- `test_graph_writer_removes_existing_process_application_links_before_rewrite()` --calls--> `Graph Writer`  [EXTRACTED]
  tests/test_graph_writer.py → Specs/Bridgr_Architektur_v09.md
- `test_graph_writer_only_writes_strong_or_confirmed_matches()` --calls--> `Graph Writer`  [EXTRACTED]
  tests/test_graph_writer.py → Specs/Bridgr_Architektur_v09.md
- `Microsoft Excel` --semantically_similar_to--> `SAP WM`  [INFERRED] [semantically similar]
  graphify-out/converted/Prozess_Lieferantenmanagement_59c1777d.md → Input/Prozess_Bestellabwicklung.txt

## Communities (70 total, 14 thin omitted)

### Community 0 - "Community 0"
Cohesion: 0.09
Nodes (40): Any, _extract_return_aliases(), _has_match_after_return_without_transition(), Neo4jAuthenticationError, Neo4jExecutionError, Neo4jQuerySyntaxError, _strip_cypher_strings_and_comments(), _translate_neo4j_exception() (+32 more)

### Community 1 - "Community 1"
Cohesion: 0.06
Nodes (30): 10. Abfrage-Layer, 11. Anwendungskonfig, 12. Akzeptanzkriterien, 13. Getroffene Entscheidungen, 1. Ziel, 2. Gesamtarchitektur, 3. Inputs, 4. Scope v0.14 (+22 more)

### Community 2 - "Community 2"
Cohesion: 0.08
Nodes (119): Graph Writer, ConfirmedLink, LlmClientConfig, Neo4jClient, Neo4jConfig, Neo4jConnectionError, Neo4jServiceUnavailableError, build_extractor_for_path() (+111 more)

### Community 3 - "Community 3"
Cohesion: 0.04
Nodes (44): 10. Betrieb, 11. Akzeptanzkriterien (v1 / PoC), 12. Differenzierung, 13. Offene Punkte, 14. Getroffene Entscheidungen, 1. Ziel, 2. Gesamtarchitektur, 3. Inputs (+36 more)

### Community 4 - "Community 4"
Cohesion: 0.10
Nodes (34): _extract_json_object(), LlmClientError, OpenAICompatibleClient, _parse_json_content(), Exception, _extract_json_object(), LlmClientConfig, LlmClientError (+26 more)

### Community 5 - "Community 5"
Cohesion: 0.07
Nodes (45): is_directory_writable(), is_legacy_input_path(), normalize_path_value(), bool, Path, str, Return a writable output directory and whether a fallback was used.      Unlike, Normalize a path value for stable comparisons across slash styles. (+37 more)

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
Cohesion: 0.08
Nodes (48): build_query_schema_reference(), answer_question(), build_natural_language_answer(), _extract_application_name_from_row(), find_application_ambiguity_options(), generate_cypher_from_question(), resolve_application_clarification(), sanitize_cypher_response() (+40 more)

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
Cohesion: 0.29
Nodes (6): documents, import_archive_path, import_archived_files, output_path, run_mode, used_output_fallback

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
Cohesion: 0.11
Nodes (50): build_neo4j_client_key(), AppConfig, ensure_import_session_defaults(), get_session_neo4j_client(), AppConfig, reset_session_neo4j_client(), sync_config_session_defaults(), AppConfig (+42 more)

### Community 43 - "Community 43"
Cohesion: 0.50
Nodes (3): Eingesetzte Software, Prozessbeschreibung: Lieferantenmanagement, Prozessschritte

### Community 50 - "Community 50"
Cohesion: 0.13
Nodes (30): append_chat_message(), Return the absolute path to the configured CMDB file.      The returned path may, Return an absolute project path.      This helper resolves relative paths agains, resolve_input_cmdb_path(), resolve_project_path(), ensure_query_chat_defaults(), handle_query_clarification(), main() (+22 more)

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
Nodes (59): clear_knowledge_base_and_refresh(), render_document_details(), render_manual_link_form(), render_review_actions(), render_review_item_actions(), clear_knowledge_base_and_refresh(), Return the absolute path to the configured CMDB file.      The returned path may, Return the absolute path to the configured CMDB file.      The returned path may (+51 more)

### Community 56 - "Community 56"
Cohesion: 0.20
Nodes (31): normalize_run_mode(), build_neo4j_client_key(), clear_pipeline_run_tracker(), clear_run_feedback(), ensure_active_cmdb_selection(), ensure_config_session_defaults(), ensure_import_session_defaults(), finish_pipeline_run_tracker() (+23 more)

### Community 57 - "Community 57"
Cohesion: 0.33
Nodes (6): code:bash ($(cat .graphify_python) -c "), code:bash ($(cat .graphify_python) -c "), code:bash (if [ ! -f graphify-out/.graphify_extract.json ]; then), code:bash ($(cat .graphify_python) -c "), code:bash ($(cat .graphify_python) -c "), For --update (incremental re-extraction)

### Community 58 - "Community 58"
Cohesion: 0.19
Nodes (27): bool, Path, str, build_pipeline_progress_callback(), clear_pipeline_run_tracker(), clear_run_feedback(), create_pipeline_run_tracker(), fail_pipeline_run_tracker() (+19 more)

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
Nodes (91): ExtractedProcess, float, int, MatchResult, Neo4jClient, ApplicationReference, persist_latest_run_refresh(), persist_org_candidate_mapping_refresh() (+83 more)

### Community 65 - "Community 65"
Cohesion: 0.07
Nodes (72): render_document_status_table(), render_duplicate_application_warnings(), build_cmdb_option_labels(), CmdbLoadError, find_cmdb_row_by_label(), load_cmdb_relation_rows(), load_cmdb_rows(), load_normalized_cmdb() (+64 more)

### Community 66 - "Community 66"
Cohesion: 0.05
Nodes (38): 10. Abfrage-Layer, 11. Anwendungskonfig, 12. Akzeptanzkriterien, 13. Getroffene Entscheidungen, 1. Ziel, 2. Gesamtarchitektur, 3.1 Eingangsdateien, 3.2 Inbox-Prinzip (+30 more)

### Community 67 - "Community 67"
Cohesion: 0.14
Nodes (22): save_config(), ensure_active_cmdb_selection(), ensure_config_session_defaults(), render_config_tab(), render_import_section(), render_path_picker_controls(), update_config_session_defaults(), render_path_picker_controls() (+14 more)

### Community 69 - "Community 69"
Cohesion: 0.26
Nodes (13): load_config(), load_config(), _load_env_file(), load_env_files(), build_argument_parser(), main(), Path, test_load_config_keeps_explicit_local_neo4j_values_even_if_they_match_defaults() (+5 more)

### Community 72 - "Community 72"
Cohesion: 0.40
Nodes (4): archive_path, display_paths, run_mode, source_paths

## Knowledge Gaps
- **485 isolated node(s):** `int`, `llm_base_url`, `llm_model`, `llm_api_key_env`, `llm_context_window` (+480 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **14 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `OpenAICompatibleClient` connect `Community 4` to `Community 64`, `Community 2`, `Community 67`, `Community 9`, `Community 42`, `Community 50`, `Community 56`, `Community 58`?**
  _High betweenness centrality (0.040) - this node is a cross-community bridge._
- **Why does `TextExtractor` connect `Community 2` to `Community 64`, `Community 4`?**
  _High betweenness centrality (0.031) - this node is a cross-community bridge._
- **Why does `BRIDGR` connect `Community 10` to `Community 50`, `Community 2`, `Community 69`?**
  _High betweenness centrality (0.030) - this node is a cross-community bridge._
- **Are the 59 inferred relationships involving `AppConfig` (e.g. with `AppConfig` and `str`) actually correct?**
  _`AppConfig` has 59 INFERRED edges - model-reasoned connections that need verification._
- **Are the 66 inferred relationships involving `OpenAICompatibleClient` (e.g. with `DocumentRunResult` and `PipelineRunResult`) actually correct?**
  _`OpenAICompatibleClient` has 66 INFERRED edges - model-reasoned connections that need verification._
- **Are the 66 inferred relationships involving `ExtractedProcess` (e.g. with `DocumentRunResult` and `PipelineRunResult`) actually correct?**
  _`ExtractedProcess` has 66 INFERRED edges - model-reasoned connections that need verification._
- **Are the 47 inferred relationships involving `GraphWriter` (e.g. with `DocumentRunResult` and `PipelineRunResult`) actually correct?**
  _`GraphWriter` has 47 INFERRED edges - model-reasoned connections that need verification._
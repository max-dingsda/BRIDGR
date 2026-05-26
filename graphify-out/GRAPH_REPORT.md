# Graph Report - BRIDGR  (2026-05-26)

## Corpus Check
- 78 files · ~94,099 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 1109 nodes · 2605 edges · 57 communities (43 shown, 14 thin omitted)
- Extraction: 84% EXTRACTED · 16% INFERRED · 0% AMBIGUOUS · INFERRED: 426 edges (avg confidence: 0.52)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `8fa6ea7a`
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
- [[_COMMUNITY_Community 56|Community 56]]
- [[_COMMUNITY_Community 57|Community 57]]

## God Nodes (most connected - your core abstractions)
1. `OpenAICompatibleClient` - 54 edges
2. `run_pipeline()` - 48 edges
3. `AppConfig` - 43 edges
4. `ExtractedProcess` - 39 edges
5. `BpmnExtractor` - 39 edges
6. `AppConfig` - 38 edges
7. `str` - 36 edges
8. `DocumentRunResult` - 36 edges
9. `PipelineRunResult` - 35 edges
10. `TextExtractor` - 34 edges

## Surprising Connections (you probably didn't know these)
- `run_pipeline()` --calls--> `Graph Writer`  [EXTRACTED]
  pipeline.py → Specs/Bridgr_Architektur_v09.md
- `test_run_document_builds_matches_and_review_items()` --calls--> `Graph Writer`  [EXTRACTED]
  tests/test_pipeline.py → Specs/Bridgr_Architektur_v09.md
- `Microsoft Excel` --semantically_similar_to--> `SAP WM`  [INFERRED] [semantically similar]
  graphify-out/converted/Prozess_Lieferantenmanagement_59c1777d.md → Input/Prozess_Bestellabwicklung.txt
- `DocuSign` --semantically_similar_to--> `SAP SD`  [INFERRED] [semantically similar]
  graphify-out/converted/Prozess_Lieferantenmanagement_59c1777d.md → Input/Prozess_Bestellabwicklung.txt
- `AppConfig` --uses--> `LlmClientConfig`  [INFERRED]
  app.py → llm_client.py

## Communities (57 total, 14 thin omitted)

### Community 0 - "Community 0"
Cohesion: 0.07
Nodes (96): Any, build_neo4j_client_key(), AppConfig, ensure_import_session_defaults(), ensure_query_chat_defaults(), get_session_neo4j_client(), bool, float (+88 more)

### Community 1 - "Community 1"
Cohesion: 0.10
Nodes (52): clear_knowledge_base_and_refresh(), render_document_details(), render_manual_link_form(), render_review_actions(), render_review_item_actions(), clear_knowledge_base_and_refresh(), render_manual_link_form(), render_review_actions() (+44 more)

### Community 2 - "Community 2"
Cohesion: 0.06
Nodes (75): ApplicationReference, Graph Writer, ApplicationReference, ExtractedProcess, Extractor, BpmnExtractor, BpmnExtractorError, DocxExtractor (+67 more)

### Community 3 - "Community 3"
Cohesion: 0.04
Nodes (44): 10. Betrieb, 11. Akzeptanzkriterien (v1 / PoC), 12. Differenzierung, 13. Offene Punkte, 14. Getroffene Entscheidungen, 1. Ziel, 2. Gesamtarchitektur, 3. Inputs (+36 more)

### Community 4 - "Community 4"
Cohesion: 0.14
Nodes (19): Exception, _extract_json_object(), LlmClientConfig, LLM-Client verwendet urllib statt requests, build_client(), FakeResponse, FakeSession, Exception (+11 more)

### Community 5 - "Community 5"
Cohesion: 0.10
Nodes (27): Bridgr, ABFRAGE-LAYER (Nutzung), Anwendung, CMDB-Export, Konfiguration, Delta Update, BPMN-Extraktion, generische Extraktion (+19 more)

### Community 6 - "Community 6"
Cohesion: 0.17
Nodes (30): ConfirmedLink, float, ConfirmedLink, confirmed, disambiguation, process_identity, rejected, RejectedLink (+22 more)

### Community 7 - "Community 7"
Cohesion: 0.43
Nodes (6): load_cmdb_rows(), CMDB-Datei ohne Fehlerbehandlung geladen, Path, test_load_cmdb_rows_raises_for_missing_file(), test_load_cmdb_rows_raises_for_missing_required_columns(), test_load_cmdb_rows_reads_valid_csv()

### Community 8 - "Community 8"
Cohesion: 0.20
Nodes (19): render_document_status_table(), render_duplicate_application_warnings(), render_knowledge_base_tools(), render_latest_run_summary(), render_review_items_table(), render_review_tab(), sample_run(), test_build_document_details_includes_error_and_process_context() (+11 more)

### Community 9 - "Community 9"
Cohesion: 0.09
Nodes (40): append_chat_message(), handle_query_clarification(), render_query_chat_messages(), render_query_tab(), run_query_chat_turn(), build_query_schema_reference(), answer_question(), build_natural_language_answer() (+32 more)

### Community 10 - "Community 10"
Cohesion: 0.08
Nodes (22): cmdb_filename, cmdb_name_column, cmdb_uuid_column, debug_mode, fuzzy_threshold, input_path, last_run_mode, llm_api_key_env (+14 more)

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
Cohesion: 0.05
Nodes (43): code:block10 (You are a graphify extraction subagent. Read the files liste), code:bash ($(cat graphify-out/.graphify_python) -c "), code:bash ($(cat .graphify_python) -c "), code:bash ($(cat .graphify_python) -c "), code:bash ($(cat .graphify_python) -c "), code:bash (mkdir -p graphify-out), code:bash ($(cat .graphify_python) -c "), code:bash ($(cat .graphify_python) -c ") (+35 more)

### Community 35 - "Community 35"
Cohesion: 0.05
Nodes (42): 10. Betrieb, 11. Akzeptanzkriterien (v1 / PoC), 12. Differenzierung, 13. Offene Punkte, 1. Ziel, 2. Gesamtarchitektur, 3. Inputs, 4. MVP-Scope (v1) (+34 more)

### Community 36 - "Community 36"
Cohesion: 0.06
Nodes (34): code:block1 (/graphify                                             # full), code:bash ($(cat .graphify_python) -c "), code:bash ($(cat .graphify_python) -c "), code:bash (if [ ! -f graphify-out/.graphify_extract.json ]; then), code:bash ($(cat .graphify_python) -c "), code:bash ($(cat .graphify_python) -c "), code:bash ($(cat .graphify_python) -c "), code:bash ($(cat .graphify_python) -c ") (+26 more)

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
Cohesion: 0.08
Nodes (25): 1. Abhaengigkeiten, 2. Streamlit starten, 3. Pipeline per CLI starten, Aktuelle UI-Funktionen, Aktueller Stand, BPMN-Transformer fuer grosse Modelle, code:text (BRIDGR/), code:json ({) (+17 more)

### Community 42 - "Community 42"
Cohesion: 0.19
Nodes (20): is_directory_writable(), Return the absolute path to the configured CMDB file.      The returned path may, Return a writable output directory and whether a fallback was used.      Unlike, Return an absolute project path.      This helper resolves relative paths agains, resolve_input_cmdb_path(), resolve_project_path(), resolve_runtime_output_path(), save_config() (+12 more)

### Community 43 - "Community 43"
Cohesion: 0.50
Nodes (3): Eingesetzte Software, Prozessbeschreibung: Lieferantenmanagement, Prozessschritte

### Community 50 - "Community 50"
Cohesion: 0.16
Nodes (23): append_chat_message(), ensure_active_cmdb_selection(), ensure_config_session_defaults(), handle_query_clarification(), main(), render_config_tab(), render_query_chat_messages(), render_query_tab() (+15 more)

### Community 52 - "Community 52"
Cohesion: 0.10
Nodes (30): is_legacy_input_path(), normalize_path_value(), bool, Path, str, Normalize a path value for stable comparisons across slash styles., Return whether the given path still points to the pre-Input legacy folder., is_directory_writable() (+22 more)

### Community 53 - "Community 53"
Cohesion: 0.20
Nodes (27): bool, int, Path, str, _build_process_transform_text(), _build_transform_filename(), _build_transform_text(), _extract_application_names() (+19 more)

### Community 54 - "Community 54"
Cohesion: 0.48
Nodes (5): validate_manual_application_name(), test_validate_manual_application_name_rejects_empty_value(), test_validate_manual_application_name_rejects_invalid_characters(), test_validate_manual_application_name_rejects_overlong_value(), test_validate_manual_application_name_returns_normalized_value()

### Community 56 - "Community 56"
Cohesion: 0.24
Nodes (14): load_config(), resolve_env_backed_value(), load_config(), _load_env_file(), load_env_files(), build_argument_parser(), main(), Path (+6 more)

### Community 57 - "Community 57"
Cohesion: 0.70
Nodes (4): render_path_picker_controls(), pick_directory(), pick_file(), _safe_initial_dir()

## Knowledge Gaps
- **368 isolated node(s):** `nodes`, `edges`, `input_tokens`, `output_tokens`, `code` (+363 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **14 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `OpenAICompatibleClient` connect `Community 2` to `Community 0`, `Community 9`, `Community 50`, `Community 4`?**
  _High betweenness centrality (0.047) - this node is a cross-community bridge._
- **Why does `run_pipeline()` connect `Community 1` to `Community 0`, `Community 2`, `Community 4`, `Community 7`, `Community 8`, `Community 42`, `Community 50`, `Community 52`, `Community 56`?**
  _High betweenness centrality (0.020) - this node is a cross-community bridge._
- **Why does `BRIDGR` connect `Community 10` to `Community 56`, `Community 50`, `Community 2`?**
  _High betweenness centrality (0.018) - this node is a cross-community bridge._
- **Are the 36 inferred relationships involving `OpenAICompatibleClient` (e.g. with `AppConfig` and `str`) actually correct?**
  _`OpenAICompatibleClient` has 36 INFERRED edges - model-reasoned connections that need verification._
- **Are the 3 inferred relationships involving `run_pipeline()` (e.g. with `.write_payload()` and `.close()`) actually correct?**
  _`run_pipeline()` has 3 INFERRED edges - model-reasoned connections that need verification._
- **Are the 12 inferred relationships involving `AppConfig` (e.g. with `AppConfig` and `str`) actually correct?**
  _`AppConfig` has 12 INFERRED edges - model-reasoned connections that need verification._
- **Are the 29 inferred relationships involving `ExtractedProcess` (e.g. with `DocumentRunResult` and `PipelineRunResult`) actually correct?**
  _`ExtractedProcess` has 29 INFERRED edges - model-reasoned connections that need verification._
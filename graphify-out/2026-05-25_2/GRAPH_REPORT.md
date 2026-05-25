# Graph Report - .  (2026-05-25)

## Corpus Check
- cluster-only mode — file stats not available

## Summary
- 491 nodes · 1295 edges · 30 communities (21 shown, 9 thin omitted)
- Extraction: 81% EXTRACTED · 19% INFERRED · 0% AMBIGUOUS · INFERRED: 241 edges (avg confidence: 0.52)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `b0f19419`
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

## God Nodes (most connected - your core abstractions)
1. `OpenAICompatibleClient` - 39 edges
2. `BpmnExtractor` - 39 edges
3. `ExtractedProcess` - 36 edges
4. `run_pipeline()` - 35 edges
5. `TextExtractor` - 33 edges
6. `Bridgr` - 28 edges
7. `DocumentRunResult` - 26 edges
8. `PipelineRunResult` - 25 edges
9. `TextExtractorError` - 24 edges
10. `MatchResult` - 23 edges

## Surprising Connections (you probably didn't know these)
- `run_pipeline()` --calls--> `Graph Writer`  [EXTRACTED]
  pipeline.py → Specs/Bridgr_Architektur_v09.md
- `test_run_document_builds_matches_and_review_items()` --calls--> `Graph Writer`  [EXTRACTED]
  tests/test_pipeline.py → Specs/Bridgr_Architektur_v09.md
- `Microsoft Excel` --semantically_similar_to--> `SAP WM`  [INFERRED] [semantically similar]
  graphify-out/converted/Prozess_Lieferantenmanagement_59c1777d.md → Input/Prozess_Bestellabwicklung.txt
- `DocuSign` --semantically_similar_to--> `SAP SD`  [INFERRED] [semantically similar]
  graphify-out/converted/Prozess_Lieferantenmanagement_59c1777d.md → Input/Prozess_Bestellabwicklung.txt
- `render_config_tab()` --calls--> `float`  [INFERRED]
  app.py → skills/match.py

## Communities (30 total, 9 thin omitted)

### Community 0 - "Community 0"
Cohesion: 0.10
Nodes (36): ApplicationReference, Graph Writer, ApplicationReference, ExtractedProcess, BpmnExtractor, BpmnExtractorError, Neo4jClient, bool (+28 more)

### Community 1 - "Community 1"
Cohesion: 0.09
Nodes (52): append_chat_message(), clear_knowledge_base_and_refresh(), handle_query_clarification(), main(), render_document_details(), render_document_status_table(), render_duplicate_application_warnings(), render_knowledge_base_tools() (+44 more)

### Community 2 - "Community 2"
Cohesion: 0.08
Nodes (50): build_neo4j_client_key(), is_directory_writable(), is_legacy_input_path(), normalize_path_value(), Return the absolute path to the configured CMDB file.      The returned path may, Return a writable output directory and whether a fallback was used.      Unlike, Normalize a path value for stable comparisons across slash styles., Return whether the given path still points to the pre-Input legacy folder. (+42 more)

### Community 3 - "Community 3"
Cohesion: 0.14
Nodes (27): DocxExtractor, PdfExtractor, PdfExtractorError, TextExtractor, TextExtractorError, Path, str, Path (+19 more)

### Community 4 - "Community 4"
Cohesion: 0.19
Nodes (19): Exception, _extract_json_object(), LlmClientConfig, LlmClientError, OpenAICompatibleClient, build_client(), FakeResponse, FakeSession (+11 more)

### Community 5 - "Community 5"
Cohesion: 0.12
Nodes (26): save_config(), ensure_active_cmdb_selection(), ensure_config_session_defaults(), ensure_import_session_defaults(), ensure_query_chat_defaults(), get_session_neo4j_client(), render_config_tab(), render_import_section() (+18 more)

### Community 6 - "Community 6"
Cohesion: 0.19
Nodes (25): ConfirmedLink, float, disambiguation, process_identity, rejected, RejectedLink, RejectedLink, build_fuzzy_candidates() (+17 more)

### Community 7 - "Community 7"
Cohesion: 0.10
Nodes (27): Bridgr, ABFRAGE-LAYER (Nutzung), Anwendung, CMDB-Export, Konfiguration, Delta Update, BPMN-Extraktion, generische Extraktion (+19 more)

### Community 8 - "Community 8"
Cohesion: 0.18
Nodes (18): Neo4jAuthenticationError, Neo4jClient, Neo4jConnectionError, Neo4jExecutionError, Neo4jQueryError, Neo4jQuerySyntaxError, QueryValidationError, _strip_cypher_strings_and_comments() (+10 more)

### Community 9 - "Community 9"
Cohesion: 0.17
Nodes (20): answer_question(), build_natural_language_answer(), find_application_ambiguity_options(), generate_cypher_from_question(), resolve_application_clarification(), sanitize_cypher_response(), should_request_application_clarification(), FakeLlmClient (+12 more)

### Community 10 - "Community 10"
Cohesion: 0.09
Nodes (20): cmdb_filename, cmdb_name_column, cmdb_uuid_column, fuzzy_threshold, input_path, last_run_mode, llm_api_key_env, llm_base_url (+12 more)

### Community 11 - "Community 11"
Cohesion: 0.22
Nodes (11): load_config(), resolve_env_backed_value(), _load_env_file(), build_argument_parser(), main(), Path, test_load_config_keeps_explicit_neo4j_config_values(), test_load_config_prefers_neo4j_env_over_local_defaults() (+3 more)

### Community 12 - "Community 12"
Cohesion: 0.15
Nodes (12): files, code, document, image, paper, video, graphifyignore_patterns, needs_graph (+4 more)

### Community 13 - "Community 13"
Cohesion: 0.54
Nodes (6): CmdbLoadError, load_cmdb_rows(), Path, test_load_cmdb_rows_raises_for_missing_file(), test_load_cmdb_rows_raises_for_missing_required_columns(), test_load_cmdb_rows_reads_valid_csv()

### Community 14 - "Community 14"
Cohesion: 0.47
Nodes (6): DocuSign, Microsoft Excel, SAP SRM, SAP FI, SAP SD, SAP WM

### Community 15 - "Community 15"
Cohesion: 0.33
Nodes (5): edges, hyperedges, input_tokens, nodes, output_tokens

### Community 16 - "Community 16"
Cohesion: 0.33
Nodes (5): edges, hyperedges, input_tokens, nodes, output_tokens

### Community 17 - "Community 17"
Cohesion: 0.40
Nodes (4): extract_bpmn_process_ids(), str, Return all BPMN process ids found in the given XML text., test_extract_bpmn_process_ids_returns_all_process_ids()

### Community 18 - "Community 18"
Cohesion: 0.40
Nodes (4): edges, input_tokens, nodes, output_tokens

### Community 19 - "Community 19"
Cohesion: 0.40
Nodes (4): documents, output_path, run_mode, used_output_fallback

## Knowledge Gaps
- **72 isolated node(s):** `nodes`, `edges`, `input_tokens`, `output_tokens`, `code` (+67 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **9 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `OpenAICompatibleClient` connect `Community 4` to `Community 0`, `Community 1`, `Community 2`, `Community 3`, `Community 9`?**
  _High betweenness centrality (0.115) - this node is a cross-community bridge._
- **Why does `BRIDGR` connect `Community 10` to `Community 1`, `Community 2`, `Community 11`?**
  _High betweenness centrality (0.074) - this node is a cross-community bridge._
- **Why does `Bridgr` connect `Community 7` to `Community 0`, `Community 1`?**
  _High betweenness centrality (0.069) - this node is a cross-community bridge._
- **Are the 24 inferred relationships involving `OpenAICompatibleClient` (e.g. with `DocumentRunResult` and `PipelineRunResult`) actually correct?**
  _`OpenAICompatibleClient` has 24 INFERRED edges - model-reasoned connections that need verification._
- **Are the 18 inferred relationships involving `BpmnExtractor` (e.g. with `OpenAICompatibleClient` and `DocumentRunResult`) actually correct?**
  _`BpmnExtractor` has 18 INFERRED edges - model-reasoned connections that need verification._
- **Are the 27 inferred relationships involving `ExtractedProcess` (e.g. with `DocumentRunResult` and `PipelineRunResult`) actually correct?**
  _`ExtractedProcess` has 27 INFERRED edges - model-reasoned connections that need verification._
- **Are the 2 inferred relationships involving `run_pipeline()` (e.g. with `.close()` and `.write_payload()`) actually correct?**
  _`run_pipeline()` has 2 INFERRED edges - model-reasoned connections that need verification._
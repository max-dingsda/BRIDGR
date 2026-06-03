# Graph Report - F:\workspace\BRIDGR  (2026-06-03)

## Corpus Check
- cluster-only mode — file stats not available

## Summary
- 1224 nodes · 4098 edges · 62 communities (46 shown, 16 thin omitted)
- Extraction: 80% EXTRACTED · 20% INFERRED · 0% AMBIGUOUS · INFERRED: 840 edges (avg confidence: 0.54)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `bf875c63`
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

## God Nodes (most connected - your core abstractions)
1. `AppConfig` - 174 edges
2. `KnowledgeBase` - 121 edges
3. `OpenAICompatibleClient LLM Client` - 102 edges
4. `GraphWriter` - 92 edges
5. `ExtractedProcess` - 75 edges
6. `BPMN Extractor` - 58 edges
7. `Text Extractor` - 58 edges
8. `MatchResult` - 54 edges
9. `Organization Service` - 52 edges
10. `Neo4jClient` - 47 edges

## Surprising Connections (you probably didn't know these)
- `Initial Lauf` --references--> `KnowledgeBase`  [EXTRACTED]
  Specs/Bridgr_Architektur_v09.md → services/organization_service.py
- `Full Update` --references--> `KnowledgeBase`  [EXTRACTED]
  Specs/Bridgr_Architektur_v09.md → services/organization_service.py
- `Delta Update` --references--> `KnowledgeBase`  [EXTRACTED]
  Specs/Bridgr_Architektur_v09.md → services/organization_service.py
- `Typ-Inkonsistenz zwischen match.py und knowledge_base.py` --references--> `KnowledgeBase`  [EXTRACTED]
  Specs/review_findings.md → services/organization_service.py
- `query_service module` --implements--> `Concept: Conversation History for Context`  [INFERRED]
  services/query_service.py → Specs/Bridgr_Architektur_v19.md

## Import Cycles
- None detected.

## Communities (62 total, 16 thin omitted)

### Community 0 - "Community 0"
Cohesion: 0.06
Nodes (95): ConfirmedLink, OrgUnitEntry, Neo4jClient, Neo4jServiceUnavailableError, apply_org_unit_mapping(), build_extractor_for_path(), build_manual_matches(), DocumentRunResult (+87 more)

### Community 1 - "Community 1"
Cohesion: 0.05
Nodes (80): ApplicationReference, CmdbEntity, CmdbRelation, NormalizedCmdb, CmdbEntity Dataclass, CmdbRelation Dataclass, NormalizedCmdb Dataclass, CmdbEntity (+72 more)

### Community 2 - "Community 2"
Cohesion: 0.07
Nodes (94): resolve_input_cmdb_path Function, resolve_project_path Function, bool, accept_org_unit_candidate_as_new(), add_org_unit(), clear_knowledge_base_sections(), confirm_link(), is_explicit_role() (+86 more)

### Community 3 - "Community 3"
Cohesion: 0.10
Nodes (50): Fuzzy Matching, float, _add_pending_candidate(), ArchiMateElement, ArchiMateImportResult, ArchiMateRelation, _default_mapping(), _import_to_neo4j() (+42 more)

### Community 4 - "Community 4"
Cohesion: 0.10
Nodes (49): build_cmdb_option_labels(), build_document_details(), build_document_status_rows(), build_duplicate_application_warnings(), build_review_rows(), _collect_document_scope(), deduplicate_documents(), filter_documents() (+41 more)

### Community 5 - "Community 5"
Cohesion: 0.08
Nodes (38): Alias Service, lookup_alias_matches(), sync_knowledge_base_aliases(), App Entry Point (main), ArgumentParser, load_config(), build_argument_parser(), build_summary() (+30 more)

### Community 6 - "Community 6"
Cohesion: 0.14
Nodes (43): LlmClientConfig, LlmClientError, _extract_return_aliases(), _has_match_after_return_without_transition(), Neo4jAuthenticationError, Neo4jConfig, Neo4jConnectionError, Neo4jExecutionError (+35 more)

### Community 7 - "Community 7"
Cohesion: 0.13
Nodes (41): CmdbLoadError, CmdbValidationIssue, _collect_csv_shape_issues(), find_cmdb_row_by_label(), load_cmdb_relation_rows(), load_cmdb_rows(), load_normalized_cmdb(), normalize_entity_type() (+33 more)

### Community 8 - "Community 8"
Cohesion: 0.10
Nodes (33): _extract_variable_labels(), RelationshipPattern, _resolve_labels(), _validate_labels(), _validate_properties(), validate_query_schema(), _validate_relationship_patterns(), _validate_relationship_types() (+25 more)

### Community 9 - "Community 9"
Cohesion: 0.10
Nodes (37): BpmnTransformError Exception, transform_bpmn_for_import Function, _csv_has_columns(), describe_cmdb_file(), list_cmdb_entity_files(), list_cmdb_files(), list_cmdb_relation_files(), sanitize_uploaded_name() (+29 more)

### Community 10 - "Community 10"
Cohesion: 0.14
Nodes (34): main(), Runtime Service, Pipeline Run Tracker (in-memory), run_pipeline_with_live_feedback(), append_chat_message(), apply_pending_review_scope_defaults(), clear_pipeline_run_tracker(), clear_run_feedback() (+26 more)

### Community 11 - "Community 11"
Cohesion: 0.15
Nodes (28): Return an absolute project path.      This helper resolves relative paths agains, resolve_project_path(), load_last_import_context(), load_last_import_selection(), load_latest_run(), save_last_import_selection(), write_latest_run(), Import Service (+20 more)

### Community 12 - "Community 12"
Cohesion: 0.10
Nodes (28): elements, export, import, Anwendung, OrgEinheit, Prozess, Rolle, Schnittstelle (+20 more)

### Community 13 - "Community 13"
Cohesion: 0.07
Nodes (27): chat_mode, cmdb_entity_type_column, cmdb_filename, cmdb_multivalue_separator, cmdb_name_column, cmdb_owner_name_column, cmdb_relation_source_column, cmdb_relation_target_column (+19 more)

### Community 14 - "Community 14"
Cohesion: 0.17
Nodes (23): ArchiMateExportResult, _build_archimate_export(), export_graph_as_archimate(), _normalize_rel_type(), AppConfig, Neo4jClient, str, Ensure relationship type uses the schema-correct short name (no 'Relationship' s (+15 more)

### Community 15 - "Community 15"
Cohesion: 0.21
Nodes (25): bool, int, object, Path, str, _build_process_transform_text(), _build_transform_filename(), _extract_application_names() (+17 more)

### Community 16 - "Community 16"
Cohesion: 0.15
Nodes (24): AppConfig, write_debug_log(), str, get_llm_status(), Inkonsistente Pfadauflösung, test_ensure_import_session_defaults_uses_config_mode(), test_get_llm_status_reports_endpoint_error(), test_get_llm_status_reports_missing_model() (+16 more)

### Community 17 - "Community 17"
Cohesion: 0.10
Nodes (26): Bridgr, ABFRAGE-LAYER (Nutzung), Anwendung, CMDB-Export, Konfiguration, Delta Update, BPMN-Extraktion, generische Extraktion (+18 more)

### Community 18 - "Community 18"
Cohesion: 0.14
Nodes (24): execute_cypher Tool Schema (LLM tool call), _run_tool_use_turn(), _build_llm_history(), _extract_cypher_from_response(), _format_query_result(), _make_tool_call(), str, test_build_llm_history_returns_empty_for_no_messages() (+16 more)

### Community 19 - "Community 19"
Cohesion: 0.21
Nodes (22): RejectedLink, RejectedLink, build_fuzzy_candidates(), classify_match_confidence(), compute_containment_score(), is_application_rejected(), is_candidate_rejected(), match_application() (+14 more)

### Community 20 - "Community 20"
Cohesion: 0.15
Nodes (22): bool, Path, str, resolve_runtime_output_path Function, is_directory_writable(), is_legacy_input_path(), normalize_path_value(), normalize_run_mode() (+14 more)

### Community 21 - "Community 21"
Cohesion: 0.31
Nodes (19): build_client(), FakeResponse, FakeSession, MonkeyPatch, OpenAICompatibleClient, test_generate_json_extracts_json_object_from_markdown_wrapped_response(), test_generate_json_logs_requests_and_responses(), test_generate_json_raises_after_exhausting_repair_attempts() (+11 more)

### Community 22 - "Community 22"
Cohesion: 0.23
Nodes (6): _extract_json_object(), _parse_json_content(), Any, str, LLM-Client verwendet urllib statt requests, test_extract_json_object_handles_nested_json_without_regex()

### Community 23 - "Community 23"
Cohesion: 0.20
Nodes (15): resolve_input_cmdb_relations_path(), CMDB Service, persist_cmdb_sync(), sync_cmdb_to_neo4j(), CmdbSyncResult, AppConfig, str, resolve_cmdb_owner_assignments() (+7 more)

### Community 24 - "Community 24"
Cohesion: 0.15
Nodes (18): App Config Module, BPMN Transformer Module, CMDB Module, UX Issue: Import Buried Behind Two Clicks, UX Issue: Review Tab Shows Same Data Twice, UX Issue: Tab Order Inverted vs Workflow, UI: Config Tab, Import Utils Module (+10 more)

### Community 25 - "Community 25"
Cohesion: 0.25
Nodes (14): pick_directory(), pick_file(), _safe_initial_dir(), runtime_service module, ensure_active_cmdb_selection(), ensure_config_session_defaults(), update_config_session_defaults(), test_ensure_active_cmdb_selection_clears_missing_relation_selection() (+6 more)

### Community 26 - "Community 26"
Cohesion: 0.17
Nodes (13): BPMN Extraction Prompt, Generic Extraction Prompt, Fuzzy-Matching-Entscheidung, Prozess-Namens-Matching, BRIDGR README, Neo4j Python Driver, Pandas, PyPDF (+5 more)

### Community 27 - "Community 27"
Cohesion: 0.24
Nodes (11): QUERY_NODE_SCHEMA (Neo4j Node Labels), QUERY_RELATIONSHIP_PATTERNS (Neo4j Relationship Patterns), validate_query_schema Function, load_knowledge_base Function, migrate_kb_to_neo4j CLI Entry, sync_org_units Function (KB to Neo4j), Neo4jClient Class, Neo4jConfig Dataclass (+3 more)

### Community 28 - "Community 28"
Cohesion: 0.24
Nodes (9): extract_bpmn_process_ids (identity), Identity Skill (BPMN process ID extraction), str, Return all BPMN process ids found in the given XML text., identity.py ist ein Minimal-Stub, Test Suite: Identity (BPMN Process IDs), test_extract_bpmn_process_ids_raises_for_malformed_xml(), test_extract_bpmn_process_ids_returns_all_process_ids() (+1 more)

### Community 29 - "Community 29"
Cohesion: 0.27
Nodes (10): sync_knowledge_base_aliases (alias_service), ConfirmedLink TypedDict, KnowledgeBase Dataclass, OrgUnitCandidate TypedDict, confirm_link Function, reject_link Function, upsert_org_unit_candidate (knowledge_base), Test Suite: Alias Service (+2 more)

### Community 30 - "Community 30"
Cohesion: 0.25
Nodes (9): Concept: Deterministic Alias Enrichment on Empty Results, Concept: Conversation History for Context, Concept: execute_cypher Tool, Concept: graph_schema.py as Canonical Schema Source, Finding: Follow-up Questions Misinterpreted by LLM, Graph Schema Module, Chat System Prompt, query_service module (+1 more)

### Community 31 - "Community 31"
Cohesion: 0.22
Nodes (9): save_knowledge_base Function, DocumentRunResult Dataclass, PipelineRunResult Dataclass, run_document Function (per-file processing), run_pipeline Function (main orchestrator), ImportState Dataclass, compute_file_hash Function (SHA-256), load_import_state Function (+1 more)

### Community 32 - "Community 32"
Cohesion: 0.29
Nodes (8): AppConfig Dataclass, load_config Function, config.json Runtime Configuration, write_debug_log Function, LlmClientConfig Dataclass, LlmClientError (llm_client), Test Suite: App Config Env Fallbacks, Test Suite: LLM Client

### Community 33 - "Community 33"
Cohesion: 0.36
Nodes (8): Concept: Dual-Mode Chat (tool-use / prompt-only), Concept: EA Chatbot Vision (natural language IT landscape), Concept: Inbox Principle for Input/, Concept: KB-First Matching (KB -> Fuzzy -> LLM Fallback), Concept: LLM as Orchestrator, Concept: Two-Layer Architecture (Pipeline + Query), Pipeline Module, Bridgr Architecture v19

### Community 34 - "Community 34"
Cohesion: 0.36
Nodes (6): str, Query Layer Module, sanitize_cypher_response Function, test_sanitize_cypher_response_returns_plain_query_unchanged(), test_sanitize_cypher_response_strips_plain_fence(), test_sanitize_cypher_response_strips_surrounding_whitespace()

### Community 35 - "Community 35"
Cohesion: 0.29
Nodes (6): documents, import_archive_path, import_archived_files, output_path, run_mode, used_output_fallback

### Community 36 - "Community 36"
Cohesion: 0.40
Nodes (5): Pipeline Run Tracker (app.py), Session & Connection Management (app.py), ApplicationReference (extract_base), Neo4jConnectionError (neo4j_utils), Test Suite: App UI State

### Community 37 - "Community 37"
Cohesion: 0.60
Nodes (5): Concept: Read-Only Cypher Validation, Finding: LLM Generates Multiple MATCH Statements Without WITH, Finding: LLM Generates UNION with Mismatched Aliases, Finding: LLM Uses Non-Schema Relationship HOSTET, Old Findings (Historical Bug Log)

### Community 38 - "Community 38"
Cohesion: 0.60
Nodes (5): Concept: External Test Review to Catch Self-Written Test Blind Spots, Skill: Extract Base, Review Skill, Test Audit Report, Test: Review (collect_review_items)

### Community 39 - "Community 39"
Cohesion: 0.40
Nodes (4): archive_path, display_paths, run_mode, source_paths

### Community 40 - "Community 40"
Cohesion: 0.50
Nodes (4): is_legacy_input_path (app_config), normalize_run_mode (app_config), save_config Function, Test Suite: App Config

### Community 41 - "Community 41"
Cohesion: 0.50
Nodes (4): build_import_completion_message (import_service), load_last_import_context (run_artifacts), write_latest_run Function, Test Suite: Import Service

### Community 42 - "Community 42"
Cohesion: 0.50
Nodes (4): match_application (skills/match), match_application_candidates (skills/match), normalize_name_for_matching (skills/match), Test Suite: Match Application

### Community 44 - "Community 44"
Cohesion: 0.67
Nodes (3): CONFIDENCE_STRONG Constant, MATCH_SOURCE Constants, build_review_rows Function (UI review table)

## Knowledge Gaps
- **173 isolated node(s):** `int`, `llm_base_url`, `llm_model`, `llm_api_key_env`, `llm_context_window` (+168 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **16 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `AppConfig` connect `Community 16` to `Community 0`, `Community 1`, `Community 2`, `Community 3`, `Community 4`, `Community 5`, `Community 6`, `Community 7`, `Community 10`, `Community 11`, `Community 14`, `Community 15`, `Community 20`, `Community 23`, `Community 25`?**
  _High betweenness centrality (0.266) - this node is a cross-community bridge._
- **Why does `OpenAICompatibleClient LLM Client` connect `Community 6` to `Community 32`, `Community 1`, `Community 0`, `Community 10`, `Community 16`, `Community 18`, `Community 21`, `Community 22`, `Community 25`, `Community 31`?**
  _High betweenness centrality (0.131) - this node is a cross-community bridge._
- **Why does `KnowledgeBase` connect `Community 0` to `Community 1`, `Community 2`, `Community 5`, `Community 6`, `Community 7`, `Community 16`, `Community 17`, `Community 19`, `Community 23`?**
  _High betweenness centrality (0.100) - this node is a cross-community bridge._
- **Are the 86 inferred relationships involving `AppConfig` (e.g. with `CmdbLoadError` and `LlmClientConfig`) actually correct?**
  _`AppConfig` has 86 INFERRED edges - model-reasoned connections that need verification._
- **Are the 52 inferred relationships involving `KnowledgeBase` (e.g. with `AppConfig` and `DocumentRunResult`) actually correct?**
  _`KnowledgeBase` has 52 INFERRED edges - model-reasoned connections that need verification._
- **Are the 65 inferred relationships involving `OpenAICompatibleClient LLM Client` (e.g. with `AppConfig` and `ApplicationReference`) actually correct?**
  _`OpenAICompatibleClient LLM Client` has 65 INFERRED edges - model-reasoned connections that need verification._
- **Are the 46 inferred relationships involving `GraphWriter` (e.g. with `AppConfig` and `DocumentRunResult`) actually correct?**
  _`GraphWriter` has 46 INFERRED edges - model-reasoned connections that need verification._
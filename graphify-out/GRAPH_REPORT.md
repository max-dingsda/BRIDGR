# Graph Report - f:/workspace/BRIDGR  (2026-06-01)

## Corpus Check
- 107 files · ~102,727 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 1142 nodes · 3665 edges · 78 communities (43 shown, 35 thin omitted)
- Extraction: 76% EXTRACTED · 23% INFERRED · 0% AMBIGUOUS · INFERRED: 861 edges (avg confidence: 0.53)
- Token cost: 60,500 input · 13,300 output

## Community Hubs (Navigation)
- [[_COMMUNITY_AppConfig & Config IO|AppConfig & Config I/O]]
- [[_COMMUNITY_Knowledge Base Operations|Knowledge Base Operations]]
- [[_COMMUNITY_App Entry & UI Modules|App Entry & UI Modules]]
- [[_COMMUNITY_Alias Service & Chat Query|Alias Service & Chat Query]]
- [[_COMMUNITY_Config Form & UI Run View|Config Form & UI Run View]]
- [[_COMMUNITY_Graph Schema & Validation|Graph Schema & Validation]]
- [[_COMMUNITY_LLM Client Core|LLM Client Core]]
- [[_COMMUNITY_CMDB Data Model|CMDB Data Model]]
- [[_COMMUNITY_CMDB Validation|CMDB Validation]]
- [[_COMMUNITY_Neo4j Client|Neo4j Client]]
- [[_COMMUNITY_BPMN Extraction|BPMN Extraction]]
- [[_COMMUNITY_Query Service (Chat Loop)|Query Service (Chat Loop)]]
- [[_COMMUNITY_Architecture Concepts (Specs)|Architecture Concepts (Specs)]]
- [[_COMMUNITY_BPMN Transformer|BPMN Transformer]]
- [[_COMMUNITY_Text & PDF Extractors|Text & PDF Extractors]]
- [[_COMMUNITY_Runtime Configuration Keys|Runtime Configuration Keys]]
- [[_COMMUNITY_Run Artifacts & State|Run Artifacts & State]]
- [[_COMMUNITY_App Entrypoint & CLI|App Entrypoint & CLI]]
- [[_COMMUNITY_Match & Fuzzy Scoring|Match & Fuzzy Scoring]]
- [[_COMMUNITY_Pipeline & Extractor Factory|Pipeline & Extractor Factory]]
- [[_COMMUNITY_Import Utils (CMDB files)|Import Utils (CMDB files)]]
- [[_COMMUNITY_DOCX Extractor|DOCX Extractor]]
- [[_COMMUNITY_Graph Schema + KB Loading|Graph Schema + KB Loading]]
- [[_COMMUNITY_PDF Extractor Tests|PDF Extractor Tests]]
- [[_COMMUNITY_AppConfig Dataclass|AppConfig Dataclass]]
- [[_COMMUNITY_Identity (BPMN Process IDs)|Identity (BPMN Process IDs)]]
- [[_COMMUNITY_Debug Logging & Artifacts|Debug Logging & Artifacts]]
- [[_COMMUNITY_BPMN Transform + CMDB Utils|BPMN Transform + CMDB Utils]]
- [[_COMMUNITY_Extract Base + Extractor Types|Extract Base + Extractor Types]]
- [[_COMMUNITY_Query Layer (sanitize)|Query Layer (sanitize)]]
- [[_COMMUNITY_CMDB Load & Normalize|CMDB Load & Normalize]]
- [[_COMMUNITY_CMDBGraph Write Payloads|CMDB/Graph Write Payloads]]
- [[_COMMUNITY_Knowledge Base JSON Structure|Knowledge Base JSON Structure]]
- [[_COMMUNITY_Latest Run Artifact|Latest Run Artifact]]
- [[_COMMUNITY_LLM Client Public API|LLM Client Public API]]
- [[_COMMUNITY_Import Service & Finalization|Import Service & Finalization]]
- [[_COMMUNITY_Last Import Selection|Last Import Selection]]
- [[_COMMUNITY_Old Prompts & Early Specs|Old Prompts & Early Specs]]
- [[_COMMUNITY_Mid-Version Architecture Specs|Mid-Version Architecture Specs]]
- [[_COMMUNITY_Match Skill Tests|Match Skill Tests]]
- [[_COMMUNITY_Codex Hooks|Codex Hooks]]
- [[_COMMUNITY_Constants & Review UI|Constants & Review UI]]
- [[_COMMUNITY_VSCode Settings|VSCode Settings]]
- [[_COMMUNITY_Import State Artifact|Import State Artifact]]
- [[_COMMUNITY_Query Layer Tests|Query Layer Tests]]
- [[_COMMUNITY_Extract Package Init|Extract Package Init]]
- [[_COMMUNITY_Skills Package Init|Skills Package Init]]
- [[_COMMUNITY_Identity Tests|Identity Tests]]
- [[_COMMUNITY_Document Status Constants|Document Status Constants]]
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

## God Nodes (most connected - your core abstractions)
1. `AppConfig` - 112 edges
2. `OpenAICompatibleClient` - 77 edges
3. `KnowledgeBase` - 76 edges
4. `ExtractedProcess` - 76 edges
5. `GraphWriter` - 71 edges
6. `MatchResult` - 56 edges
7. `TextExtractor` - 55 edges
8. `BpmnExtractor` - 54 edges
9. `Neo4jClient` - 49 edges
10. `LlmClientConfig` - 47 edges

## Surprising Connections (you probably didn't know these)
- `query_service module` --implements--> `Concept: Conversation History for Context`  [INFERRED]
  services/query_service.py → Specs/Bridgr_Architektur_v19.md
- `Concept: External Test Review to Catch Self-Written Test Blind Spots` --rationale_for--> `Test: Review (collect_review_items)`  [INFERRED]
  Specs/test_audit.md → tests/test_review.py
- `AppConfig` --uses--> `AppConfig`  [INFERRED]
  services/import_service.py → app_config.py
- `Path` --uses--> `AppConfig`  [INFERRED]
  tests/test_import_service.py → app_config.py
- `App Entry Point (main)` --references--> `AppConfig Dataclass`  [INFERRED]
  app.py → app_config.py

## Import Cycles
- None detected.

## Communities (78 total, 35 thin omitted)

### Community 0 - "AppConfig & Config I/O"
Cohesion: 0.06
Nodes (104): bool, Path, str, AppConfig, is_directory_writable(), is_legacy_input_path(), normalize_path_value(), normalize_run_mode() (+96 more)

### Community 1 - "Knowledge Base Operations"
Cohesion: 0.07
Nodes (83): accept_org_unit_candidate_as_new(), add_org_unit(), clear_knowledge_base_sections(), confirm_link(), KnowledgeBase, load_knowledge_base(), map_org_unit_candidate(), normalize_org_unit_name() (+75 more)

### Community 2 - "App Entry & UI Modules"
Cohesion: 0.05
Nodes (63): App Config Module, Pipeline Run Tracker (app.py), Session & Connection Management (app.py), BPMN Transformer Module, CMDB Module, Concept: Deterministic Alias Enrichment on Empty Results, Concept: Conversation History for Context, Concept: Dual-Mode Chat (tool-use / prompt-only) (+55 more)

### Community 3 - "Alias Service & Chat Query"
Cohesion: 0.06
Nodes (56): lookup_alias_matches(), sync_knowledge_base_aliases(), sync_knowledge_base_aliases (alias_service), execute_cypher Tool Schema (LLM tool call), persist_cmdb_sync(), sync_cmdb_to_neo4j(), ApplicationReference (dataclass), ExtractedProcess (dataclass) (+48 more)

### Community 4 - "Config Form & UI Run View"
Cohesion: 0.09
Nodes (54): Return the absolute path to the configured CMDB file.      The returned path may, resolve_input_cmdb_path(), build_cmdb_option_labels(), build_document_details(), build_document_status_rows(), build_duplicate_application_warnings(), build_review_rows(), _collect_document_scope() (+46 more)

### Community 5 - "Graph Schema & Validation"
Cohesion: 0.07
Nodes (50): build_query_schema_reference(), _extract_variable_labels(), RelationshipPattern, _resolve_labels(), _validate_labels(), _validate_properties(), validate_query_schema(), _validate_relationship_patterns() (+42 more)

### Community 6 - "LLM Client Core"
Cohesion: 0.13
Nodes (31): _extract_json_object(), LlmClientError, OpenAICompatibleClient, _parse_json_content(), Any, str, Neo4jClient, LLM-Client verwendet urllib statt requests (+23 more)

### Community 7 - "CMDB Data Model"
Cohesion: 0.15
Nodes (34): CmdbEntity, CmdbRelation, NormalizedCmdb, CmdbEntity, CmdbRelation, ExtractedProcess, NormalizedCmdb, ExtractedProcess (+26 more)

### Community 8 - "CMDB Validation"
Cohesion: 0.15
Nodes (38): CmdbLoadError, CmdbValidationIssue, _collect_csv_shape_issues(), find_cmdb_row_by_label(), load_cmdb_relation_rows(), load_cmdb_rows(), load_normalized_cmdb(), normalize_cmdb_entities() (+30 more)

### Community 9 - "Neo4j Client"
Cohesion: 0.33
Nodes (36): ConfirmedLink, Neo4jClient, Neo4jConfig, Neo4jConnectionError, apply_org_unit_mapping(), build_manual_matches(), build_neo4j_client(), DocumentRunResult (+28 more)

### Community 10 - "BPMN Extraction"
Cohesion: 0.12
Nodes (19): ApplicationReference, ApplicationReference, BpmnExtractor, bool, ExtractedProcess, int, OpenAICompatibleClient, Path (+11 more)

### Community 11 - "Query Service (Chat Loop)"
Cohesion: 0.13
Nodes (34): QueryValidationError, _build_chat_system_prompt(), _build_llm_history(), _collect_alias_hints(), _extract_cypher_from_response(), _format_query_result(), AppConfig, Exception (+26 more)

### Community 12 - "Architecture Concepts (Specs)"
Cohesion: 0.11
Nodes (29): Bridgr, ABFRAGE-LAYER (Nutzung), Anwendung, CMDB-Export, Konfiguration, Delta Update, BPMN-Extraktion, generische Extraktion (+21 more)

### Community 13 - "BPMN Transformer"
Cohesion: 0.19
Nodes (27): bool, int, object, Path, str, BpmnTransformError, _build_process_transform_text(), _build_transform_filename() (+19 more)

### Community 14 - "Text & PDF Extractors"
Cohesion: 0.17
Nodes (15): TextExtractor, Path, str, bool, ExtractedProcess, Path, str, FakeLlmClient (+7 more)

### Community 15 - "Runtime Configuration Keys"
Cohesion: 0.07
Nodes (27): chat_mode, cmdb_entity_type_column, cmdb_filename, cmdb_multivalue_separator, cmdb_name_column, cmdb_owner_name_column, cmdb_relation_source_column, cmdb_relation_target_column (+19 more)

### Community 16 - "Run Artifacts & State"
Cohesion: 0.18
Nodes (24): compute_file_hash(), load_last_import_context(), load_last_import_selection(), load_latest_run(), save_import_state(), save_last_import_selection(), write_latest_run(), Any (+16 more)

### Community 17 - "App Entrypoint & CLI"
Cohesion: 0.15
Nodes (19): App Entry Point (main), ArgumentParser, load_config(), build_argument_parser(), build_summary(), main(), sync_org_units(), _load_env_file() (+11 more)

### Community 18 - "Match & Fuzzy Scoring"
Cohesion: 0.22
Nodes (22): RejectedLink, RejectedLink, build_fuzzy_candidates(), classify_match_confidence(), compute_containment_score(), is_application_rejected(), is_candidate_rejected(), match_application() (+14 more)

### Community 19 - "Pipeline & Extractor Factory"
Cohesion: 0.19
Nodes (21): Neo4jServiceUnavailableError, build_extractor_for_path(), list_bpmn_files(), resolve_cmdb_owner_assignments(), update_organization_knowledge_from_cmdb(), FakeLlmClient, Path, str (+13 more)

### Community 20 - "Import Utils (CMDB files)"
Cohesion: 0.23
Nodes (20): _csv_has_columns(), describe_cmdb_file(), list_cmdb_entity_files(), list_cmdb_files(), list_cmdb_relation_files(), list_process_files(), sanitize_uploaded_name(), save_uploaded_file() (+12 more)

### Community 21 - "DOCX Extractor"
Cohesion: 0.28
Nodes (9): DocxExtractor, Path, str, FakeLlmClient, MonkeyPatch, Path, str, test_docx_extractor_reads_paragraphs_and_tables() (+1 more)

### Community 22 - "Graph Schema + KB Loading"
Cohesion: 0.21
Nodes (12): QUERY_NODE_SCHEMA (Neo4j Node Labels), QUERY_RELATIONSHIP_PATTERNS (Neo4j Relationship Patterns), validate_query_schema Function, load_knowledge_base Function, migrate_kb_to_neo4j CLI Entry, sync_org_units Function (KB to Neo4j), Neo4jClient Class, Neo4jConfig Dataclass (+4 more)

### Community 23 - "PDF Extractor Tests"
Cohesion: 0.42
Nodes (7): PdfExtractor, FakeLlmClient, MonkeyPatch, Path, str, test_pdf_extractor_reads_page_text(), test_pdf_extractor_rejects_documents_without_text()

### Community 24 - "AppConfig Dataclass"
Cohesion: 0.22
Nodes (10): AppConfig Dataclass, is_legacy_input_path (app_config), load_config Function, normalize_run_mode (app_config), resolve_input_cmdb_path Function, resolve_project_path Function, save_config Function, config.json Runtime Configuration (+2 more)

### Community 25 - "Identity (BPMN Process IDs)"
Cohesion: 0.27
Nodes (8): Identity Skill (BPMN process ID extraction), extract_bpmn_process_ids(), str, Return all BPMN process ids found in the given XML text., identity.py ist ein Minimal-Stub, test_extract_bpmn_process_ids_raises_for_malformed_xml(), test_extract_bpmn_process_ids_returns_all_process_ids(), test_extract_bpmn_process_ids_returns_empty_list_when_no_processes()

### Community 26 - "Debug Logging & Artifacts"
Cohesion: 0.25
Nodes (9): resolve_runtime_output_path Function, write_debug_log Function, save_knowledge_base Function, DocumentRunResult Dataclass, PipelineRunResult Dataclass, run_pipeline Function (main orchestrator), ImportState Dataclass, load_import_state Function (+1 more)

### Community 27 - "BPMN Transform + CMDB Utils"
Cohesion: 0.22
Nodes (9): BpmnTransformError Exception, transform_bpmn_for_import Function, describe_cmdb_file (import_utils), list_cmdb_files Function, list_process_files Function, sanitize_uploaded_name (import_utils), save_uploaded_file (import_utils), Test Suite: BPMN Transformer (+1 more)

### Community 28 - "Extract Base + Extractor Types"
Cohesion: 0.25
Nodes (9): ExtractedProcess (extract_base), BpmnExtractor (extract_bpmn), DocxExtractor (extract_docx), PdfExtractor (extract_pdf), TextExtractor (extract_txt), Test Suite: Extract BPMN, Test Suite: Extract DOCX, Test Suite: Extract PDF (+1 more)

### Community 29 - "Query Layer (sanitize)"
Cohesion: 0.39
Nodes (6): sanitize_cypher_response(), str, test_sanitize_cypher_response_returns_plain_query_unchanged(), test_sanitize_cypher_response_strips_cypher_fence(), test_sanitize_cypher_response_strips_plain_fence(), test_sanitize_cypher_response_strips_surrounding_whitespace()

### Community 30 - "CMDB Load & Normalize"
Cohesion: 0.38
Nodes (7): load_cmdb_rows Function, load_normalized_cmdb Function, normalize_cmdb_entities Function, normalize_cmdb_relations Function, validate_cmdb_entity_file (cmdb), validate_cmdb_relation_file (cmdb), Test Suite: CMDB Loading and Normalization

### Community 31 - "CMDB/Graph Write Payloads"
Cohesion: 0.48
Nodes (7): CmdbEntity Dataclass, CmdbRelation Dataclass, NormalizedCmdb Dataclass, GraphWritePayload, GraphWriter, MatchResult (skills/match), Test Suite: Graph Writer

### Community 32 - "Knowledge Base JSON Structure"
Cohesion: 0.29
Nodes (6): confirmed, disambiguation, org_unit_candidates, org_units, process_identity, rejected

### Community 33 - "Latest Run Artifact"
Cohesion: 0.29
Nodes (6): documents, import_archive_path, import_archived_files, output_path, run_mode, used_output_fallback

### Community 34 - "LLM Client Public API"
Cohesion: 0.40
Nodes (6): LlmClientConfig Dataclass, LlmClientError (llm_client), OpenAICompatibleClient LLM Client, generate_json Method (LLM JSON extraction), generate_with_tools Method (LLM tool use), Test Suite: LLM Client

### Community 35 - "Import Service & Finalization"
Cohesion: 0.40
Nodes (5): build_import_completion_message (import_service), finalize_import_artifacts (import_service), load_last_import_context (run_artifacts), write_latest_run Function, Test Suite: Import Service

### Community 36 - "Last Import Selection"
Cohesion: 0.40
Nodes (4): archive_path, display_paths, run_mode, source_paths

### Community 37 - "Old Prompts & Early Specs"
Cohesion: 0.60
Nodes (5): Fuzzy-Matching-Entscheidung, Prozess-Namens-Matching, Bridgr Architektur v0.5, Bridgr Architektur v0.6, Bridgr Architektur v0.7

### Community 38 - "Mid-Version Architecture Specs"
Cohesion: 0.40
Nodes (5): Bridgr Architektur v0.13, Bridgr Architektur v0.14, Bridgr Architektur v0.15, Bridgr Architektur v0.16, Bridgr Architektur v0.17

### Community 39 - "Match Skill Tests"
Cohesion: 0.50
Nodes (4): match_application (skills/match), match_application_candidates (skills/match), normalize_name_for_matching (skills/match), Test Suite: Match Application

### Community 41 - "Constants & Review UI"
Cohesion: 0.67
Nodes (3): CONFIDENCE_STRONG Constant, MATCH_SOURCE Constants, build_review_rows Function (UI review table)

## Ambiguous Edges - Review These
- `Prozess-Namens-Matching` → `Bridgr Architektur v0.5`  [AMBIGUOUS]
  Specs/Bridgr_Architektur_v05.md · relation: conceptually_related_to

## Knowledge Gaps
- **180 isolated node(s):** `int`, `llm_base_url`, `llm_model`, `llm_api_key_env`, `llm_context_window` (+175 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **35 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **What is the exact relationship between `Prozess-Namens-Matching` and `Bridgr Architektur v0.5`?**
  _Edge tagged AMBIGUOUS (relation: conceptually_related_to) - confidence is low._
- **Why does `AppConfig` connect `AppConfig & Config I/O` to `Knowledge Base Operations`, `Config Form & UI Run View`, `LLM Client Core`, `CMDB Data Model`, `Neo4j Client`, `Query Service (Chat Loop)`, `Run Artifacts & State`, `App Entrypoint & CLI`, `Pipeline & Extractor Factory`?**
  _High betweenness centrality (0.127) - this node is a cross-community bridge._
- **Why does `runtime_service module` connect `App Entry & UI Modules` to `AppConfig & Config I/O`, `Knowledge Base Operations`, `Query Service (Chat Loop)`, `Config Form & UI Run View`?**
  _High betweenness centrality (0.108) - this node is a cross-community bridge._
- **Why does `Test Suite: App UI State` connect `App Entry & UI Modules` to `AppConfig Dataclass`, `Alias Service & Chat Query`?**
  _High betweenness centrality (0.093) - this node is a cross-community bridge._
- **Are the 55 inferred relationships involving `AppConfig` (e.g. with `DocumentRunResult` and `PipelineRunResult`) actually correct?**
  _`AppConfig` has 55 INFERRED edges - model-reasoned connections that need verification._
- **Are the 50 inferred relationships involving `OpenAICompatibleClient` (e.g. with `ApplicationReference` and `DocumentRunResult`) actually correct?**
  _`OpenAICompatibleClient` has 50 INFERRED edges - model-reasoned connections that need verification._
- **Are the 36 inferred relationships involving `KnowledgeBase` (e.g. with `DocumentRunResult` and `PipelineRunResult`) actually correct?**
  _`KnowledgeBase` has 36 INFERRED edges - model-reasoned connections that need verification._
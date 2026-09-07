```markdown
# Bridgr

**EA Knowledge Graph with Decision, Consolidation, and Security Layer** | As of: August 2026 | v0.29

---

## 1. Objective

BRIDGR combines process documentation, CMDB exports, and ArchiMate models into a unified enterprise architecture knowledge graph, making it analyzable through a natural language web interface.

Core question:
Which IT components support which business processes, and how confidently do we know this?

### 1.1 Vision Goal: Full-fledged EA Chatbot

The `Communication` tab is not just a query editor but a full-fledged enterprise architecture chatbot. Users ask natural language questions about processes, applications, responsibilities, risks, goals, and dependencies. BRIDGR answers these questions based on the knowledge graph, not from general world knowledge.

This vision goal is the benchmark for all design decisions in the query layer.

### 1.2 Architectural Guidelines

- Neo4j is the canonical runtime source for the EA graph and for persisted decisions.
- The import path remains sequential, traceable, and idempotent.
- Domain graph, review/correction logic, and UI orchestration remain cleanly separated.
- Uncertain information is explicitly modeled as uncertain or treated as open review cases.
- Manual corrections must be specifically reversible.

---

## 2. Overall Architecture

BRIDGR consists of four logically separated layers:

1. **Import and Extraction Layer**
   Process documents, CMDB files, and ArchiMate files are read, analyzed, and converted into structured intermediate objects.

2. **Write and Consolidation Layer**
   The `GraphWriter` and associated services write the domain graph into Neo4j, perform identity resolution, and maintain persistent review decisions.

3. **Decision and Correction Layer**
   User decisions such as confirmation, rejection, manual assignment, withdrawal, and duplicate merging are modeled as separate operational metadata, allowing them to be traceable and selectively reversible.

4. **Query and UI Layer**
   Streamlit renders the work interface. An LLM acts as an orchestrator in the chat for read-only Cypher queries on the domain graph.

### 2.1 Main Data Flow

```text
Process Documents / CMDB / ArchiMate
        |
        v
Extraction / Normalization / Matching
        |
        v
Review Artifacts + Domain Decisions
        |
        v
Neo4j Domain Graph + Neo4j Decision Graph
        |
        v
Streamlit UI + Chat Layer
```

### 2.2 Canonical Sources

- **Neo4j Domain Graph**
  contains domain objects and relationships relevant for analysis, chat, and export.
- **Neo4j Decision Graph**
  contains operational correction and audit objects for manual decisions.
- **`archimate_mapping.json`**
  contains all configurable ArchiMate mappings.
- **`Output/latest_run.json`**
  is a UI artifact for review and transparency, not the canonical source of truth.

---

## 3. Inputs and File Flow

### 3.1 Input Files

- Process documents as BPMN, TXT, DOCX, or PDF
- Transformed BPMN-TXT files from large XML models
- CMDB export files as CSV, one file per object type (applications, servers, interfaces)
- ArchiMate models in Exchange Format 3.0 or 3.1 as `.xml` or `.archimate`

### 3.2 Inbox Principle

`Input/` is the working inbox for new files. Processed process files do not remain there permanently.

### 3.3 Archiving

Processed process files are moved to `data/input_archive/<timestamp>/` after a successful run.

### 3.4 Run Modes

- `full`: all process files in `Input/`
- `partial`: only explicitly selected files

CMDB synchronization and ArchiMate import/export are triggered separately.

---

## 4. Scope

| Area | In Scope | Out of Scope |
| --- | --- | --- |
| Input Formats | BPMN, TXT, DOCX, PDF, CSV-CMDB (per object type), ArchiMate 3.0/3.1 | other Office/CMDB formats |
| UI | Streamlit with 6 tabs (Communication, Import, Assignments, Organization, EA Model, Configuration) | standalone CLI review |
| Chat | LLM orchestration with tool use and prompt-only fallback | agent orchestration |
| Graph | Neo4j as domain and decision graph | alternative graph backend |
| Review | manual assignment, rejection, withdrawal, merge | external ticketing |
| ArchiMate | import, export, mapping configuration, candidate review | views/viewpoints |
| Consolidation | merge for `OrgUnit` and `Prozess`, later expandable | generic merge of any labels |

---

## 5. Domain Model

### 5.1 Domain Nodes

#### Process

Business process from process documents or ArchiMate. Domain primary identity from `process_id`, if available. Additionally, `archimate_id` may exist.

#### Application

CMDB application or ArchiMate application object. Domain primary identity is `cmdb_id`, if available.

#### Interface

Separately managed integration or handover point.

#### Server

Physical or virtual infrastructure node with `server_type`.

#### OrgUnit

Real organizational unit. Created through manual maintenance, confirmed candidates, CMDB owner resolution, or ArchiMate import.

#### Role

Process participant at the process level, typically from BPMN lanes. A role is not an OrgUnit and does not imply responsibility.

#### Alias

Deterministic alternative designation for `Application` or `OrgUnit`. Used for identity resolution in pipeline and chat.

#### Stakeholder

Interest group or party from the motivation layer.

#### Capability

Strategic or operational capability.

#### Resource

Utilized resource.

#### Goal

Explicitly modeled goal, outcome, meaning, or value.

#### Requirement

Normative requirement, constraint, or principle.

#### Context

External influencing factor or assessment.

#### Risk

Explicitly modeled risk.

#### Data Object

Data or information object.

#### Infrastructure

Technological infrastructure below the application layer.

#### Rejection

Persistent rejection mark for an extracted designation in a specific process. It serves to suppress repeated suggestions.

#### OrgCandidate

Internal operational node for an unresolved OrgUnit/role mention from process import or CMDB sync (`status`: `open`, `mapped`, or `rejected`; `mapped_org_unit` when `mapped`). Replaces the former `org_unit_candidates` section of the knowledge base file since the complete replacement of `kb.json` (Finding #15). Like `ManualDecision` and `Rejection`, it is deliberately not part of the query schema for the chat layer.

### 5.2 Domain Relationships

```text
(:Application)-[:SERVES]->(:Process)
(:Application)-[:MAY_SERVE]->(:Process)
(:Role)-[:PARTICIPATES_IN]->(:Process)
(:OrgUnit)-[:CAN_ASSUME]->(:Role)
(:OrgUnit)-[:RESPONSIBLE_FOR]->(:Process|:Application|:Interface|:Server|:Infrastructure)
(:Process)-[:FOLLOWS]->(:Process)
(:Application)-[:USES_INTERFACE]->(:Interface)
(:Application|:Interface)-[:RUNS_ON]->(:Server)
(:Alias)-[:MAY_REFER_TO]->(:Application|:OrgUnit)
(:Risk)-[:AFFECTS]->(...)
(:Capability|:Application)-[:MITIGATES]->(:Risk)
(:Capability|:Requirement)-[:REALIZES]->(...)
(:Process|:Application)-[:REQUIRES]->(:Resource)
(:Process|:Application)-[:SUPPORTS]->(:Goal|:Capability)
(:Process|:Application)-[:PROCESSES]->(:DataObject)
(:Application)-[:RUNS_ON]->(:Infrastructure)
(:Context|:Requirement)-[:INFLUENCES]->(...)
(:Stakeholder|:OrgUnit)-[:CONNECTED_TO]->(...)
```

### 5.3 Important Properties

#### On `:SERVES`

- `confidence`
- `source`
- `raw_name`

#### On `:MAY_SERVE`

- `score`

#### On ArchiMate-imported Nodes

- `archimate_id`
- `archimate_source`
- `archimate_type`

#### On ArchiMate-imported Relationships

- `archimate_rel_type`

#### On `:Role`

- `role_only`

---

## 6. Application Layers and Modules

```text
bridgr/
├── core/          # Configuration, LLM Client, Neo4j, Query Schema
├── processing/    # Pipeline, CMDB, Import Helpers, Run Artifacts
├── prompts/       # Extraction and Chat Prompts
├── skills/        # GraphWriter, Matching, Extraction
├── services/      # UI-side Orchestration
├── ui/            # Streamlit Tabs
├── data/          # archimate_mapping.json, Archive
├── Input/
├── Output/
├── config.json
├── app.py
└── main.py
```

### 6.1 Main Responsibilities

- `processing/pipeline.py`
  orchestrates document run, matching, and write payloads
- `skills/graph_writer.py`
  encapsulates domain write access to Neo4j
- `services/review_service.py`
  encapsulates review actions for application assignments
- `services/organization_service.py`
  encapsulates org, owner, and role maintenance
- `services/query_service.py`
  builds the dynamic chat system prompt and executes the dialogue turn
- `services/archimate_import_service.py` / `services/archimate_export_service.py`
  encapsulate ArchiMate import and export

---

## 7. Import Logic

### 7.1 Process Documents

Each process document goes through this chain:

1. File type-specific text extraction
2. LLM extraction or BPMN structural extraction
3. Matching against CMDB and confirmed decisions
4. Creation of review artifacts
5. Building a `GraphWritePayload`
6. Writing to Neo4j

### 7.2 Matching Order

1. Confirmed decisions from Neo4j
2. Rejected decisions from Neo4j
3. Alias resolution
4. Fuzzy matching
5. Open / manual clarification

### 7.3 Confidence Model

- `strong`
  confirmed or securely matched, written as `SERVES` or `RESPONSIBLE_FOR`
- `weak`
  application candidate requiring review, written as `MAY_SERVE`; uncertain CMDB owners are managed as `OrgCandidate` (no direct edge write path)
- `open`
  no match, only review artifact

### 7.4 Re-import Behavior

- Domain import edges are deterministically updated per process or per CMDB sync
- Persistent manual decisions must be retained across re-imports
- Confirmed or manually created assignments must not be lost due to the mere disappearance of a raw term in the source document

### 7.5 CMDB Import Format

#### 7.5.1 Input Model

CMDB data is read as one CSV file per object type:

- One file for applications
- One file for servers
- One file for interfaces

Each file contains only entries of a single type. The mapping of file names to object types is explicitly configured in `config.json` under `cmdb_type_files`. If an entry for a type is missing, that type is skipped during sync.

Example configuration:

```json
"cmdb_type_files": {
  "application": "Applications.csv",
  "server": "Servers.csv",
  "interface": "Interfaces.csv"
}
```

#### 7.5.2 Relationships in Type Files

Relationships between objects are stored as columns in the source object's source file. Multiple target IDs are separated by the configured multi-value separator (default: `|`, configurable via `cmdb_multivalue_separator` in `config.json`).

In the application file, typically:

- `runs_on`: semicolon or pipe-separated list of server IDs (configurable: `cmdb_runs_on_column`)
- `uses_interfaces`: semicolon or pipe-separated list of interface IDs (configurable: `cmdb_uses_interfaces_column`)

Server and interface files do not contain relationship columns.

Example application file:

```csv
id;name;owner_name;runs_on;uses_interfaces
APP-001;SAP S/4HANA FI;Accounting;SRV-001;IF-001|IF-015
```

#### 7.5.3 Common Mandatory Columns

All type files share the same configurable column names for ID, name, and owner (`cmdb_uuid_column`, `cmdb_name_column`, `cmdb_owner_name_column`). Only server files additionally use `cmdb_server_type_column`.

#### 7.5.4 Internal Data Model

The loader creates a `NormalizedCmdb` object from all type files together with:

- `entities`: list of all `CmdbEntity` objects of all types
- `relations`: list of all `CmdbRelation` objects from the relationship columns

The `GraphWriter` remains unchanged and only knows the `NormalizedCmdb` interface.

#### 7.5.5 Supported CMDB Format

Only configured type files are supported. Empty or missing `cmdb_type_files` means no CMDB import. The former mixed entities file plus separate relations file is no longer supported, by user decision on 7 September 2026. Obsolete configuration fields are discarded with a warning to configure type files.

---

## 8. Matching, Review, and Persistence

### 8.1 Confirming a Weak Application Candidate

When confirming a `MAY_SERVE` edge:

1. The weak edge is deleted
2. A strong `SERVES` edge is written
3. `raw_name` is set on the `SERVES` edge
4. If the term differs, an `Alias` is written on the application
5. The display in `latest_run.json` is specifically updated

### 8.2 Rejecting an Application Candidate

When rejecting:

1. The `MAY_SERVE` edge is deleted
2. A `(:Rejection)` node is written
3. The term is not suggested again in future runs

### 8.3 Manual Assignment of an Application

In manual assignment in the review tab:

1. A strong `SERVES` edge is written directly
2. The decision remains persistent across re-imports
3. The decision must be specifically reversible later

### 8.4 Owner and Role Assignments

- `RESPONSIBLE_FOR` for processes and CMDB targets is only written explicitly or through exact owner resolution
- `CAN_ASSUME` only arises through user action

---

## 9. Graph Writer

### 9.1 Role

`GraphWriter` is the only domain write component for Neo4j. It:

- normalizes identities
- writes process, CMDB, and review edges
- encapsulates promote/reject operations
- loads persistent decisions for re-imports
- performs limited cross-source identity resolution

### 9.2 Idempotency

All regular write paths are designed for repeated execution:

- `MERGE` for nodes and stable domain relationships
- process-related deletion and reconstruction for volatile import edges
- retention of persistent manual decisions across re-imports

### 9.3 Cross-Source Identity Resolution

Targeted enrichments already exist today instead of blind duplicate creation:

- BPMN/document process on existing process without `process_id`
- CMDB application on existing ArchiMate application without `cmdb_id`
- case-insensitive canonization for `OrgUnit`

### 9.4 Decision and Correction Support

Manual decisions, merge and selective undo are implemented. Merge audit payloads are
versioned and preserve complete local before/after states. Unsafe historical payloads
are rejected rather than reconstructed with missing properties. Larger cross-source
identity and provenance redesigns remain future work.

---

## 10. Decision and Correction Layer

### 10.1 Objective

Users must be able to traceably, selectively, and safely reverse manual interventions. At the same time, domain duplicates from different sources must be specifically consolidatable.

### 10.2 Basic Principle

The domain graph remains separate from the decision graph.

- The **domain graph** contains objects like `Process`, `Application`, `OrgUnit`, `Alias`.
- The **decision graph** contains operational metadata for manual interventions.

### 10.3 Decision Nodes

New internal node type:

```text
(:ManualDecision)
```

Mandatory attributes:

- `decision_id`
- `decision_type`
- `status`
- `created_at`
- `payload_json`

Optional attributes:

- `supersedes_decision_id`
- `reverted_at`
- `notes`

### 10.4 Implemented Implementation Status (Current State)

`ManualDecision` is persisted as an isolated node without edges to the affected domain objects. The assignment of affected objects (process, application, OrgUnit, role, etc.) is done exclusively through the `payload_json` field, which contains the relevant IDs and names as a JSON string.

Reversals (`decision_revert`) also reference the original decision via `supersedes_decision_id` in the payload, not via a graph edge.

The reversal logic parses the payload in memory and issues ad-hoc Cypher statements to undo the original graph changes.

### 10.4a Future Perspective: Explicit Operational Relationships

Architecturally planned but not currently implemented are explicit edges:

```text
(:ManualDecision)-[:AFFECTS]->(:Process)
(:ManualDecision)-[:AFFECTS]->(:Application)
(:ManualDecision)-[:AFFECTS]->(:OrgUnit)
(:ManualDecision)-[:AFFECTS]->(:Role)
(:ManualDecision)-[:CREATED_ALIAS]->(:Alias)
(:ManualDecision)-[:SUPERSEDES]->(:ManualDecision)
```

These edges would represent purely operational metadata and not domain EA relationships. A migration to this is possible once the payload variant is no longer sufficient (e.g., for complex auditing requirements).

### 10.5 Decision Types

Planned `decision_type` values:

- `manual_link`
- `confirmed_candidate_link`
- `manual_process_owner_assignment`
- `manual_role_assignment`
- `candidate_owner_confirmation`
- `entity_merge`
- `decision_revert`

### 10.6 Visibility in the Chat Layer

`ManualDecision` and associated operational relationships are **not part of the released query schema**.

Consequences:

- `core/graph_schema.py` remains allowlist-based
- `build_query_schema_reference()` does not include `ManualDecision`
- the dynamically generated system prompt does not mention these nodes
- the LLM cannot query the decision graph either intentionally or accidentally

The chat only answers domain questions based on the domain graph.

### 10.7 Undo of Manual Decisions

Each manual action with domain impact creates exactly one `ManualDecision` node. A reversal:

1. references the original decision
2. removes only the graph changes specifically caused by this decision
3. updates dependent UI artifacts specifically
4. leaves a persistent audit trail itself

Current implementation status:

- Reversal is implemented for `manual_link`, `confirmed_candidate_link`, `manual_process_owner_assignment`, and `manual_role_assignment`.
- The reversal currently works payload-based and sets the original decision node to `status = reverted`.
- Additionally, a new `ManualDecision` of type `decision_revert` is written.
- The reversal entry serves as an audit trail and is not treated as a new active domain decision.

### 10.8 Reversal-Safe Cases

In scope for the first expansion stage:

- manual `SERVES` link
- confirmed `MAY_SERVE` link
- manual process owner assignment
- manual role assignment

### 10.9 Distinction from Global Restoration

Selective undo remains limited to the effects of individual manual decisions. The global restoration of the overall state is a separate backup function according to Chapter 12 and is not modeled via `ManualDecision`.

---

## 11. Consolidation Layer for Duplicates

### 11.1 Objective

BRIDGR must be able to merge domain duplicates, even if no manual error caused the state.

Typical cases:

- `OrgUnit`: different spellings or manually incorrectly created units
- `Process`: identical process from TXT and BPMN under slightly different names
- later optionally `Application`

### 11.2 Mergeable Labels

First expansion stage:

- `OrgUnit`
- `Process`

### 11.3 Merge Objectives

A merge should:

1. consolidate a source node into a target node
2. transfer all relevant relationships to the target node
3. avoid duplicate relationships
4. preserve the source designation as an alias on the target
5. delete the source node
6. document the merge as `ManualDecision`

### 11.4 Alias Continuation

For each merge:

- The source designation is continued as an alias of the target node, provided it is not identical to the target name after normalization.
- This ensures that the term from the source documents remains available for future re-imports and chat resolution.

Without this alias continuation, the same raw term would lead to a duplicate again on the next import.

### 11.5 Relationship Transfer

During the merge, incoming and outgoing relationships of the source node are transferred to the target node, as long as the type is domain-allowed for the affected label.

### 11.6 Relationship Deduplication

Relationship transfer is never blind.

Rule:

- If a similar relationship with an identical counterpart and direction already exists at the target, no second edge is created.
- If both relationships carry properties, a conflict-free consolidation rule applies:
  - confirmed/strong information wins over weak
  - existing IDs and ArchiMate metadata are retained
  - redundant duplicates are discarded

### 11.7 Merge of `OrgUnit`

Domain relationships to consider:

- outgoing: `RESPONSIBLE_FOR`, `CAN_ASSUME`, `CONNECTED_TO`
- incoming via alias: `(:Alias)-[:MAY_REFER_TO]->(:OrgUnit)`
- operational metadata from `ManualDecision`

Current implementation status:

- The backend merge for `OrgUnit` is implemented.
- Incoming and outgoing relationships with supported domain types, including alias edges, are transferred; unsupported types abort the merge before data is discarded.
- Relationships are deduplicated by type, endpoints and direction. Property consolidation follows §11.6: stronger evidence wins, while existing target IDs and ArchiMate metadata are retained.

### 11.8 Merge of `Process`

Domain relationships to consider:

- incoming: `SERVES`, `MAY_SERVE`, `PARTICIPATES_IN`, `RESPONSIBLE_FOR`, `REALIZES`, `SUPPORTS`, `REQUIRES`, `PROCESSES`, `AFFECTS`, `INFLUENCES`
- outgoing: `FOLLOWS`, `SUPPORTS`, `REQUIRES`, `PROCESSES`
- additional consolidation of `process_id`, `archimate_id`, `archimate_type`

Current implementation status:

- The backend merge for `Process` is implemented.
- Existing similar relationships at the target are not duplicated.
- The source name is continued as an alias of the target process.
- Undo uses the complete typed before/after state in the version 2 merge payload and stable technical identities. It restores the recorded state only if the current state still matches the recorded post-merge state; incomplete legacy payloads and later conflicting changes are rejected.

### 11.9 Merge Precheck

Before each merge, the UI shows:

- Source and target object
- Source hints
- Number of incoming/outgoing relationships
- Potential conflicts
- Alias that would be created

Only then can the merge be explicitly confirmed.

Current implementation status:

- Merge areas for `OrgUnit` and `Process` exist in the UI.
- The precheck already shows source/target object, number of incoming and outgoing edges, duplicates at the target, alias transfer, and detected property conflicts.
- Additionally, a compact impact summary is displayed (edges to be transferred, edges not to be duplicated, behavior in case of conflicts).
- Further refinements of the visualization are possible but are no longer a functional requirement for the first expansion stage.

---

## 12. Backup and Restoration Layer

### 12.1 Objective

Before each write operation with domain relevance, a complete, restorable state of the BRIDGR graph must be available. This ensures that faulty imports, faulty CMDB imports, and unexpected merge effects can be undone even if they are not covered by a single `ManualDecision`.

Snapshots are a v1 safety net. They do not replace the targeted undo of manual decisions or the idempotency of the import logic.

### 12.2 Trigger and Lock Rule

A snapshot is automatically created immediately before the first graph write operation for:

- Process import (`run_pipeline`), including the CMDB reconciliation contained therein
- Explicit CMDB synchronization
- Merge of `OrgUnit` or `Process`

A failed or unverifiable snapshot is a hard gate: The triggering write operation is not started, and the UI displays a comprehensible error with the technical detail in the debug log. Pure chat queries, prechecks, review lists, and targeted undo do not generate a snapshot.

### 12.3 Logical Snapshot Format

A snapshot is an application-managed, logical export and not a dependent Neo4j server or file system backup. It contains in a consistent read state:

- All domain nodes and relationships
- Internal operational metadata (`ManualDecision`, `Rejection`, `OrgCandidate`, and alias projections)
- Node labels, properties, relationship types, and relationship properties
- A manifest file with snapshot ID, timestamp, trigger, operation, graph object counters, source/configuration hints, and integrity checksum

Relationship endpoints are referenced via domain-stable keys or the internal node mapping contained in the snapshot; transient Neo4j element IDs are not a restore contract. Access data, LLM secrets, and the input files themselves are not stored in the snapshot.

### 12.4 Storage, Retention, and Integrity

Snapshots are stored under the active runtime output path, `<output_path>/snapshots/<snapshot-id>/`, and consist of at least the graph export and the manifest. A snapshot is only considered usable after successful completeness and checksum verification.

The number of retained, valid snapshots is configurable via `snapshot_retention_count` and defaults to `10`. Older snapshots are only removed after successful creation of a new, verified snapshot. A failed snapshot does not change the existing stock.

### 12.5 Restoration

Restoration is available in the `Configuration` tab. The UI shows at least snapshot ID, timestamp, trigger, and object counter before explicit confirmation.

Restoration is only allowed with explicitly configured, dedicated BRIDGR Neo4j database. It replaces its entire content; foreign application data must therefore not reside in this database.

The process is:

1. Secure the current state as a snapshot before restoration
2. Validate the target snapshot against the manifest and checksum
3. Atomically reset the BRIDGR graph to the snapshot state
4. Verify the result based on the object counters stored in the manifest
5. Log the restoration as an internal operational operation

If the restoration fails, the immediately preceding pre-restore snapshot remains available. Snapshot operations are neither visible in the chat nor part of the released query schema.

### 12.6 UI and Traceability

The configuration tab shows the last snapshots with status, timestamp, trigger, object counters, and available storage location. Users can only restore validated snapshots. Each creation, cleanup, and restoration is logged with sufficient context in the debug log.

### 12.7 Non-Goals

- No replacement for regular infrastructure backups of Neo4j or the host system
- No restoration of external source files, LLM configuration, or secrets
- No partial restoration of individual domain objects in v1
- No automatic restoration without explicit user confirmation

### 12.8 Implementation Status

The backup and restoration layer is implemented in `services/snapshot_service.py`. It uses `Neo4jClient.execute_write_batch()` for transactional restoration, writes the logical export under `<output_path>/snapshots/`, and is called as a hard gate in pipeline, explicit CMDB sync, and merge. The configuration tab shows valid and invalid snapshots and only allows restoration after confirmation.

---

## 13. Query Layer

### 13.1 Architectural Principle

The LLM is the orchestrator for domain graph queries. It generates read-only Cypher based on a dynamically composed but allowlist-based schema.

### 13.2 Dynamic System Prompt

`services/query_service.py` builds the chat prompt from:

- `prompts/chat_system.md`
- Query protocol (`tool-use` or `prompt-only`)
- `build_archimate_mapping_reference()`
- `build_query_schema_reference()`

The schema is not database introspective but is built from `core/graph_schema.py`. This allows internal node types like `ManualDecision` to be kept outside the chat schema without contortions.

After the domain answer call, the completed answer passes through a second LLM call that is
limited to language editing. This editor receives the latest natural-language user question,
the answer draft, and protected business-object names and identifiers derived from the query
result. It improves spelling, grammar, and accidental language mixing in the language of the
user question without changing facts, numbers, uncertainty markers, Markdown, or protected
names. Established business slang may remain. If this call fails or returns no text, the domain
answer draft is returned unchanged.

The UI locale controls catalogued UI text only. Free content such as chat messages, user input,
and domain-object names is never localized through word-by-word replacement after the LLM call,
so that the language of the user question remains authoritative.

### 13.3 Query Security

- Only read-only Cypher
- Validator checks labels, relationships, directions, and properties
- `CONNECTED_TO` is allowed as an exception without label pair restriction
- Internal nodes like `Rejection`, `ManualDecision`, and `OrgCandidate` are not released

### 13.4 Alias Usage in Chat

Alias nodes support:

- Deterministic resolution of alternative terms
- Fallback for empty hits
- Robustness against different spellings and merge consequences

### 13.5 Uncertainty in Chat

The chat may distinguish between confirmed facts and unconfirmed candidates:

- `SERVES` / `RESPONSIBLE_FOR` = confirmed facts
- `MAY_SERVE` = unconfirmed candidates

Decision metadata itself is not a chat subject.

---

## 14. UI Architecture

### 14.1 Tab `Communication`

- Chat with history
- LLM orchestration
- Technical error translation into plain text

### 14.2 Tab `Import`

- Process import from the inbox `Input/` in `full` or `partial` mode
- Optional BPMN transformation before import
- CMDB synchronization to Neo4j
- Archiving of processed process files

### 14.3 Tab `Assignments`

- Review of open and weak application assignments
- Confirm, reject, manual assignment
- Reversal of the last manual decisions made
- Merge management for `Process`

### 14.4 Tab `Configuration`

- Paths
- CMDB type file mapping (`cmdb_type_files`): one file per object type
- CMDB column mapping (ID, name, owner, server type, relationship columns)
- Multi-value separator for CMDB relationship columns (`cmdb_multivalue_separator`)
- Import/matching settings
- LLM and Neo4j configuration
- Backup management: display validated snapshots and trigger restoration after explicit confirmation

### 14.5 Tab `Organization`

- Maintenance of OrgEinheiten
- Candidate mapping
- Process owner assignment
- Role assignment
- Merge management for `OrgUnit`

### 14.6 Tab `EA Model`

- ArchiMate mapping
- ArchiMate import
- ArchiMate export
- Review of open ArchiMate candidates

### 14.7 Correction Layer

Additional operation areas:

- `Last Manual Changes`
- `Undo Decision`
- `Consolidate Objects`
- Merge precheck with conflict display

Current implementation status:

- `Last Manual Changes` and `Undo Decision` are present in the `Assignments` tab.
- `Consolidate Objects` is available for `Process` in the `Assignments` tab and for `OrgUnit` in the `Organization` tab.
- The merge precheck already shows domain-relevant effects and conflicts.
- Only possible later UX refinements or expansion to other object types remain open.

---

## 15. Configuration

### 15.1 `config.json`

Central runtime configuration for:

- Paths
- LLM
- Neo4j
- Matching thresholds
- CMDB configuration:
  - `cmdb_type_files`: Mapping of object type (`application`, `server`, `interface`) to file names
  - `cmdb_uuid_column`, `cmdb_name_column`, `cmdb_owner_name_column`, `cmdb_server_type_column`: common columns of all type files
  - `cmdb_runs_on_column`: Column name for server IDs in the application file (default: `runs_on`)
  - `cmdb_uses_interfaces_column`: Column name for interface IDs in the application file (default: `uses_interfaces`)
  - `cmdb_multivalue_separator`: Separator for multi-values (default: `|`)
- Chat mode
- Backup:
  - `snapshot_retention_count`: Number of valid, application-managed graph snapshots to retain (default: `10`)

### 15.2 `archimate_mapping.json`

Contains:

- `elements.import`
- `elements.ignore`
- `elements.export`
- `relationships.import`
- `relationships.export`
- `relationships.bridgr_relation`
- `pending_candidates`

### 15.3 Configuration Principle

Organization-specific mapping knowledge belongs in JSON configuration, not in the code.

---

## 16. ArchiMate Integration

### 16.1 Import

The import:

- Automatically recognizes 3.0 and 3.1 via the root namespace
- Maps element types via `archimate_mapping.json`
- Performs exact identity enrichment or fuzzy candidate formation
- Writes relationships only with configured `bridgr_relation`
- Logs skipped types and relationships

### 16.2 Export

The export:

- Exports the complete BRIDGR graph
- Uses original ArchiMate types for imported nodes/relationships
- Uses configured canonical types for BRIDGR-native nodes/relationships
- Performs a type precheck for untyped nodes before export

### 16.3 ArchiMate and Consolidation

Merge and alias decisions must be designed so that:

- ArchiMate imports do not split already consolidated domain objects again
- Source designations are retained as aliases
- `archimate_id` and `archimate_type` are consciously consolidated in case of conflicts

---

## 17. UML Diagrams

### 17.1 Component Diagram

Shows the logical components and their dependencies.

![BRIDGR Component Diagram](BRIDGR_Komponentendiagramm.png)

### 17.2 Class Model

Shows the central concrete classes and the module-based functional boundaries, divided into configuration, processing & skills, and services and ArchiMate integration.

![BRIDGR Class Model](BRIDGR_Klassenmodell.png)

### 17.3 Sequence Diagrams

Shows the main processes as sequence diagrams.

![Sequence 1 – Document Import Pipeline](BRIDGR_Sequenzdiagramme_001.png)

![Sequence 2 – Natural Language Graph Query](BRIDGR_Sequenzdiagramme_002.png)

![Sequence 3 – CMDB Synchronization](BRIDGR_Sequenzdiagramme_003.png)

![Sequence 4 – Review, Merge, and Undo](BRIDGR_Sequenzdiagramme_004.png)

---

## 18. Non-functional Requirements

### 18.1 Traceability

All manual interventions must be auditable.

### 18.2 Idempotency

Repeated imports must not create uncontrolled duplicates.

### 18.3 Low Side Effects

UI actions should specifically update only the affected processes, candidates, or nodes.

### 18.4 Separation of Domain and Operational Metadata

The chat may only see the domain graph. Operational metadata remains internal.

### 18.5 Restorability

Every v1 write operation that can change a global graph state requires a validated snapshot before it begins. The snapshot must not contain secrets, and a restoration must be explicitly confirmed before execution.

---

### 18.6 Stabilization contracts (review R1–R7, 2026-09-07)

- Confirmations and rejections use `process_id`; `process` is the display-name projection. Manual and confirmed `SERVES` links survive renaming and removal of the extracted raw term. Historical name-only rejections are bound only when exactly one process matches. Invalid persisted decisions stop rematching explicitly; resolve the affected data before retrying. No guessed migration is performed.
- All BRIDGR writers use a database-wide singleton lock (`__BridgrWriteLock`) across sessions/processes. Snapshot export and the protected operation share that lock. Each process update, CMDB sync, ArchiMate import, manual decision plus audit, merge, undo plus audit, and restore is transactional. LLM extraction precedes write transactions. Direct writes outside BRIDGR do not participate in this protocol and must be paused during protected operations; database/lock-session failure is an operational failure, not a distributed fencing guarantee.
- `latest_run.json` and import state are staged as `__BridgrArtifact` records in the domain transaction, then atomically published after commit. Failed publication remains replayable and reports that the graph is saved. Unrelated operations remain available if an old artifact is unwritable. Import checkpoints distinguish `in_progress` from `complete`; an interrupted batch can retain already committed documents. Archive moves are post-commit and journaled before the first move. The Import tab can retry pending archive work without reimporting or creating duplicate audit events. Failed source documents are retained in the inbox.
- Merge decisions use payload version 2: complete typed node/relationship properties before and after, plus stable `__bridgr_id` identities with a unique constraint on `__BridgrIdentity`. This auxiliary label is not a domain type. Undo checks the affected graph against the recorded after-state; later changes or missing endpoints block reversal. Historical payloads without a full before-state are not undone automatically. Target properties win ties; stronger manual/confirmed relationship evidence wins conflicts while target provenance identifiers are retained. Full conflicting originals remain in the before-state for undo. Unsupported source relationship types block merge before any data is discarded.
- Organization alias resolution retains all distinct targets. Exact canonical names take precedence; one alias target resolves, multiple targets remain ambiguous and require review. Neither candidate order nor database row order chooses an owner.
- Relative configuration/data paths are always rooted at the repository directory, independent of current working directory or target existence. Absolute paths remain supported. CMDB import supports type files only; empty `cmdb_type_files` means no CMDB in process import, and explicit CMDB sync reports missing configuration. Legacy entity/relation-file configuration is discarded with a warning and has no fallback.
- Chat uses a separate `neo4j_chat_user` / `neo4j_chat_password` (environment fallbacks `NEO4J_CHAT_USERNAME` / `NEO4J_CHAT_PASSWORD`) and an explicit database. The account must differ from the writer and have read-only grants. The current privilege check requires Neo4j Enterprise (`SHOW USER PRIVILEGES`); Community is not supported for secured chat. There is no writer fallback. The reader/PUBLIC baseline can include normal procedure/function execution or load grants, but the chat grammar permits neither procedure calls, external loading, nor custom functions. Boosted execution, write and administration grants are rejected.
- The chat parser allows explicitly typed fixed-length graph patterns, approved scalar properties/functions, filters, aggregation, `WITH`, and aligned `UNION` branches. Dynamic properties, whole graph objects/maps, unlabeled new nodes, subqueries, procedure calls, and variable-length paths are rejected. Every prompt example is exercised against the real read-only boundary. Queries and privilege checks have a 15-second database timeout; results exceeding 500 rows or 100,000 serialized characters are rejected rather than silently truncated. These are application visibility controls in addition to database write protection, not physical separation of internal graph data.
- UI locale selects catalogued interface text. Chat prose follows the most recent user message; business names remain source data. Broader provenance, `FOLLOWS` replacement semantics, and answer-polishing invariants remain deferred under decision D1.


## 19. Acceptance Criteria

1. Correct information from the source data can be queried via the web interface.
2. Mappings are maintainable via the web interface.
3. Information on processes, applications, interfaces, servers, goals, and risks can be retrieved.
4. The pipeline runs stably through a complete import cycle.
5. TXT, DOCX, and PDF follow the same semantic extraction schema.
6. Large BPMN/XML files can be processed via the transformation path.
7. `Input/` remains free of processed process files after a successful run.
8. Processed process files are traceably archived.
9. The chat layer queries facts about the IT landscape only after a prior graph query.
10. Weak candidates are explicitly modeled as unconfirmed in the graph.
11. Rejections for application designations are persisted in Neo4j.
12. Confirmed and manual application links survive re-imports.
13. OrgEinheiten are canonized case-insensitively.
14. `ManualDecision` is not included in the released query schema.
15. Undo of a manual assignment removes only the effects specifically created by this decision.
16. A merge of `OrgUnit` continues the source name as an alias of the target object.
17. A merge of `Process` can consolidate duplicates from different sources.
18. Similar relationships are not duplicated during the merge.
19. The merge is only executable after precheck and explicit user confirmation.
20. ArchiMate import and export remain functional despite the correction layer.
21. CMDB data can be imported as one CSV file per object type, with relationships as multi-value columns.
22. The CMDB multi-value separator is configurable for common CMDB export formats.
23. CMDB data is loaded exclusively from configured type files; there is no legacy fallback.
24. A complete, validated snapshot is created before process import, explicit CMDB synchronization, and merge.
25. If snapshot creation fails, the triggering write operation is not executed, and a traceable error is displayed.
26. A snapshot includes the domain graph and internal operational metadata, but no access data or secrets.
27. Restoring a validated snapshot restores the stored BRIDGR graph state and is verified based on the object counters.
28. A pre-restore snapshot is created before each restoration; restoration requires explicit user confirmation.

---

## 20. Architectural Decisions Made

| Decision | Chosen | Rejected | Reason |
| --- | --- | --- | --- |
| Canonical Domain Storage | Neo4j | File-based source of truth | Query, review, and chat capability |
| Persistence of Manual Corrections | Internal decision graph in Neo4j | Global snapshots as a replacement for undo | Selective reversal of individual decisions remains fast and domain-precise |
| Backup before Global Write Operations | Application-managed logical graph snapshots | Exclusively manual Neo4j backups | Restorability is directly available in the BRIDGR workflow without requiring server administration |
| Visibility of the Correction Layer in Chat | Hidden | Released in the query schema | Separates domain dialogue from operational metadata |
| Merge Strategy | Label-specific (`OrgUnit`, `Process`) | Generic merge of any nodes | Lower risk, domain-controllable |
| Alias Continuation after Merge | Mandatory | Discard source name | Prevents the recurrence of the same duplicate on re-import |
| Deduplication during Merge | Check before each edge creation | Blind transfer | Prevents the merge itself from creating new clutter |
| Domain Graph vs. Decision Graph | Separate | One overloaded graph | Clearer responsibilities and safer chat layer |
| Final Language Editing in Chat | Separate fact-preserving LLM polish call after the domain answer | UI locale as response language or word-by-word UI post-processing of free text | The response language follows the user question, protected object names remain stable, and the UI cannot corrupt LLM output |
| CMDB Import Format | One CSV file per object type with relationship columns | Mixed entities file + separate relations file | Matches real CMDB export structures (e.g., ServiceNow, Jira Asset Management); configurable multi-value separator supports common formats |

---

## 21. Known Limitations

- The described decision and correction layer is architecturally defined but not yet fully implemented.
- `ManualDecision` is currently stored without explicit `AFFECTS`, `CREATED_ALIAS`, or `SUPERSEDES` edges; the assignment is currently payload-based.
- Merge workflows for `Application` are deliberately not part of the first expansion stage.
- A generic merge for additional labels beyond `OrgUnit` and `Process` is not yet part of the current expansion stage.
- UML diagrams in the repository may be ahead or behind the described state and are not the canonical reference before updating.
- CMDB import requires configured type files; the legacy format has been removed.

---

BRIDGR | Architecture v0.29 | As of August 2026
```

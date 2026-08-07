```markdown
# User Guide BRIDGR

## 1. Purpose of the Application

BRIDGR connects process documents with data from a CMDB and builds a knowledge graph from it. The goal is to make business processes, applications, interfaces, servers, and organizational responsibilities visible together.

For users, this means:

- Process documents can be read and evaluated.
- CMDB data can be linked with the processes.
- Unclear assignments can be manually checked and decided.
- Existing information can then be queried in natural language.

The guiding question of the application is:

> Which IT components support which business processes, and how confidently do we know that?

---

## 2. Who is BRIDGR for?

This guide is intended for users without development knowledge and without prior knowledge of BRIDGR.

It is particularly suitable for:

- Enterprise Architecture teams
- Departments with process responsibility
- IT architecture, IT operations, or CMDB responsible persons
- Users who should review import runs and approve open assignments

---

## 3. Prerequisites

Before the first use, the following prerequisites should be met:

- BRIDGR is locally installed and startable.
- The required Python packages from `requirements.txt` or for a complete local development and test environment from `requirements-dev.txt` are installed.
- A Neo4j system is accessible.
- An LLM endpoint with OpenAI-compatible API is accessible.
- The required access data is available.
- Process files and CMDB files are prepared professionally.

### 3.1 Required Data

BRIDGR works with the following inputs:

- Process documents as `.bpmn`, `.txt`, `.docx`, or `.pdf`
- Optionally large BPMN/XML files for pre-transformation
- CMDB files as `.csv`, one file per object type (applications, servers, interfaces)
- Optionally ArchiMate file as `.xml` or `.archimate`

### 3.2 Required Technical Information

Before setup, you should have this information ready:

- URL of the LLM endpoint
- Model name of the LLM
- Name of the environment variable for the API key
- Neo4j URL
- Neo4j user
- Neo4j password
- Neo4j database name

### 3.3 Important Folders

- `Input/`: Input folder for new process and CMDB files
- `Output/`: Output data and run artifacts
- `data/input_archive/`: Archive of already processed process files

Important:

- `Input/` is an inbox, not a permanent archive.
- After successful import, processed process files are removed from `Input/` and archived.

---

## 4. Initial Setup

### 4.1 Start Application

BRIDGR is started locally as a Streamlit application.

Typical start:

```powershell
streamlit run app.py
```

The interface then opens in the browser.

In the app header at the top right, there is an optional dark mode switch. The choice applies only to the current session and is reset when the application is restarted.

Next to it is a role dropdown (`User`, `Expert`, `Architect`, `Configurator`). It displays only the relevant tabs for the selected role and serves solely for clarity — it is not access control, each role is freely selectable at any time. As with the dark mode switch, the choice applies only to the current session.

- `User` (default at start): only `Communication`
- `Expert`: `Communication`, `Import`, `Assignments`, `Organization`
- `Architect`: like `Expert`, additionally `EA Model`
- `Configurator`: `Communication`, `Configuration`

If you miss steps in a tab in this guide, first check whether the currently selected role even displays this tab.

If BRIDGR is not yet operational locally, the dependencies must be installed beforehand, for example:

```powershell
python -m pip install -r requirements.txt
```

For a complete local development and test environment:

```powershell
python -m pip install -r requirements-dev.txt
```

### 4.2 Basic Configuration in BRIDGR

Open the `Configuration` tab (far right) and enter the technical settings there.

Recommended order:

1. Configure LLM
2. Configure Neo4j
3. Check input and output paths
4. Specify CMDB files
5. Test connections
6. Only then perform the first import

### 4.3 Prepare Files

Place your files in the input folder before the first import:

- Process files in `Input/`
- CMDB files (applications, servers, interfaces) also in `Input/`

If very large BPMN/XML files are used, it is advisable to reduce them via BPMN transformation before the actual import.

---

## 5. Recommended Workflow

Even if the tabs are displayed in a different order, the typical workflow is:

1. `Configuration`: check technical settings
2. `Import`: import process files and synchronize CMDB
3. `Assignments`: check open application assignments
4. `Organization`: clarify organizational candidates, process owners, and roles
5. `Assignments > Data Maintenance`: undo last manual changes if necessary and consolidate process duplicates; consolidate duplicates of organizational units in the `Organization` tab
6. `EA Model`: optionally maintain ArchiMate mapping and import/export ArchiMate
7. `Communication`: ask questions to the built knowledge graph

---

## 6. Tab `Communication`

### 6.1 Purpose

In this tab, you ask questions in natural language about the existing knowledge graph.

Examples:

- Which applications support process X?
- Which servers are connected to application Y?
- Which organizational unit is responsible for application Z?
- Which applications might be relevant for process X (not yet confirmed)?

Note on candidates: BRIDGR distinguishes between confirmed application links and weak candidates (not yet decided in the review tab). If you ask about possible or unconfirmed assignments, BRIDGR explicitly marks the answer as "possible candidate" or "not confirmed". Confirmed information is output without this note.

### 6.2 Area and Elements

#### `New Conversation`

Resets the current conversation history and starts a new chat context.

#### Chat Input `Question to the Knowledge Graph`

Here you enter your question in normal language.

#### Chat Responses

Immediately after submitting a question, your input and a processing spinner appear directly in the conversation history — this makes it clear at all times that BRIDGR is processing the request. The system's response follows as soon as processing is complete.

Possible additional content:

- Tabular results
- Technical Cypher query under `Technical Details`
- CSV export of a result

#### Button `Export as CSV`

Appears with tabular hits and exports the visible result as a CSV file.

### 6.3 Important Notes

- Without a configured LLM, the chat cannot be used.
- Without Neo4j access data, the chat cannot execute graph queries.
- If no hits are found, it does not automatically mean that no data exists; it can also be due to inconsistent designations.

---

## 7. Tab `Import`

Here you start the process import to Neo4j and the CMDB synchronization.

### Field `Import Mode`

Values:

- `full`: processes all process files in the input path
- `partial`: processes only the explicitly selected files

### Field `Files for Partial Import`

Appears only in `partial` mode. Here you select the process files to be imported.

### Field `BPMN for Transformation`

Selection of large BPMN/XML files to be reduced before the actual import.

### Button `Transform BPMN`

Generates more compact transform files from the selected BPMN/XML files. This is helpful for very large or complex BPMN models.

### Button `Start Pipeline`

Starts the actual process import to Neo4j.

Process files are analyzed, matched with the CMDB, and results are saved as run artifacts. Before the first change, BRIDGR automatically creates a validated snapshot of the entire knowledge graph. If this fails, the import is not started.

### Table `Current Input Path`

Shows the currently found process files in the input path.

### Fields `Applications`, `Servers`, `Interfaces`

Assigns a CSV file from the input folder to each CMDB object type. Relationships (e.g., which server hosts an application) are included as columns in the application file and are automatically read during synchronization.

### Button `Adopt Type Files`

Saves the currently selected type files as active configuration.

### Button `Synchronize CMDB to Neo4j`

Transfers the selected CMDB data to Neo4j.

Additionally, the last saved run in `Output/latest_run.json` is re-evaluated with the current CMDB. This can automatically remove open or weak assignments in the `Assignments` tab if the updated CMDB now provides a strong hit. Before this synchronization, BRIDGR also automatically creates a validated graph snapshot.

### Tables for `CMDB-...Structure Errors`

Show problems in the CSV structure, such as missing columns or incomplete rows.

---

## 8. Tab `Assignments`

### 8.1 Purpose

Here you check open or uncertain application assignments from the last import run. No new import is started in this tab.

### 8.2 Section `Scope`

#### Radio Option `Only Last Import`

Shows only files from the last imported run.

#### Radio Option `Select Files Manually`

Allows targeted selection of individual files from already existing run artifacts.

Important consequence:

If you select only 1 of 10 files here, the display in this tab only refers to this selected file or file set. You only hide the remaining files; their review cases are neither deleted nor automatically decided. Open assignments of the unselected files therefore remain and must be checked separately later.

#### Field `Files for Review`

Multiselect for the manual selection of process files to be checked.

### 8.3 Field `Status Filter`

Filters the displayed documents by status. For example, you can only display problematic or open cases.

### 8.4 Area `Document Status`

Tabular overview of the documents in the current filter.

Typical information:

- File status
- Recognized processes
- Error cases

### 8.5 Area `Open Assignments`

#### Sorting

Above the table, you can sort the entries either **by process** (default) or **by application identifier** using the sorting switch. Sorting by application identifier makes it easier to recognize cases where the same term appears in multiple processes and refers to the same CMDB application.

Here you see per review case:

- Checkbox (for multiple selection)
- `Process`
- `Application in Process`
- `Application in CMDB`
- `Evaluation`

For each case, the following actions are available:

#### Button `Confirm`

Accepts the proposed assignment as correct.

**Batch Confirmation:** If you mark multiple rows with a checkbox and all marked entries have the same application identifier (normalized) and the same CMDB target, clicking `Confirm` in one of the marked rows confirms all marked entries at once. Rows without a mark are not affected.

In case of an invalid multiple selection (different identifiers or different CMDB targets), all action buttons of the marked rows are deactivated, and a red banner explains the reason. Unmarked rows remain individually operable.

#### Button `Reject`

Rejects the proposed assignment.

#### Popover `Create Manually`

Opens a manual selection with an alphabetically sorted CMDB list.

Included:

- Field `CMDB Target`: alphabetically sorted selection of a CMDB entry
- Button `Save`: saves the manually chosen assignment

### 8.6 Area `Document Details`

Shows technical and professional details per document.

May include:

- Process name
- Process ID
- Recognized organizational unit
- Predecessor process
- File hash
- Review items

#### Expander `Technical Details`

Shows raw data from the extraction:

- Raw applications
- Applications
- Assignments

### 8.7 When to Use This Tab

Use this tab always after an import when BRIDGR was not confident enough to automatically release an application assignment.

### 8.8 Area `Data Maintenance`

At the end of the tab, the `Data Maintenance` area bundles two cross-tab maintenance functions: the consolidation of process duplicates and the reversal of manual changes.

### 8.9 Section `Consolidate Processes`

This area is for merging professional process duplicates.

Typical use case:

- The same process was imported from different sources with slightly different names.
- A process is available once as a text/BPMN import and once from another model.

Fields:

- `Process Source`: the process to be resolved
- `Process Target`: the process to remain

Before the actual merge, BRIDGR also shows a precheck with relationship hints, duplicate check, and a compact impact summary.

#### Button `Execute Process Merge`

Merges the selected source process into the target process.

This happens:

- Application relationships, role participations, owner relationships, and process follow-up edges are transferred to the target.
- Already existing similar relationships are not created twice.
- The name of the source is continued as an alias of the target process.

Important:

- A process merge can be undone via `Last Manual Changes`.

### 8.10 Section `Last Manual Changes`

Here you see the last executed manual decisions with professional context.

Typical contents:

- Type of change
- Time
- Affected process, application, or organizational unit
- For process owners, the process name and the assigned owner

Important:

- Older decisions may still contain technical identifiers if they were made before the UI extension.
- Newer process owner assignments are displayed with a human-readable process name.

#### Button `Undo`

Reverses a supported manual decision.

Currently supported:

- Manually created application assignment
- Confirmed application candidate
- Manual process owner assignment
- Manual role assignment

The undo process itself generates an internal proof in the system again. Merge decisions can also be undone in the current version via this list. Undos are considered professionally completed and no longer appear as new active manual decisions.

---

## 9. Tab `Organization`

### 9.1 Purpose

Here you manage organizational units, open organizational candidates, process owners, and role relationships.

### 9.2 Section `Organizational Units`

Shows all known organizational units. The list is loaded from Neo4j and therefore also contains organizational units that were created through an ArchiMate import (from `BusinessActor` elements) without an additional step being necessary.

Manually created organizational units in this tab also appear in the list but must be transferred to Neo4j via the synchronization button to be effective in the graph.

#### Button `Synchronize Organization to Neo4j`

Writes manually maintained organizational units to Neo4j.

Important:

You must always perform this step if you have made organizational changes in this tab that should be effective in the graph. This includes, in particular, new organizational units, candidate decisions, process owner assignments, and role assignments. Without synchronization, changes are professionally recorded but not yet fully effective in Neo4j.

#### Button `Manage Processes`

Opens an edit view for the respective organizational unit.

Contained:

- Field `Responsible Processes`: Multiselect of all processes
- Button `Save`: saves the process assignment

#### Form `New Organizational Unit`

Field:

- `New Organizational Unit`

Button:

- `Add Organizational Unit`

### 9.3 Section `Candidates`

Shows open organizational candidates that have arisen from documents or CMDB data.

Typically displayed for each candidate:

- Affected processes
- Affected roles
- Sources

Input fields and buttons:

- `Existing Organizational Unit`: selection of an existing OU
- `Assign`: maps the candidate to an existing OU
- `Adopt as New Organizational Unit`: text field for the target name
- `Adopt`: creates a new OU or adopts the candidate
- `Reject`: discards the candidate

### 9.4 Section `Proposed Process Owners`

Shows proposals for process owners from the extraction.

Input field:

- `Confirm Organizational Unit`

Buttons:

- `Confirm`
- `Reject`

With `Confirm`, the proposed process owner is adopted.

### 9.5 Section `Processes Without Owner`

Here you see processes that have not yet been assigned an organizational unit as an owner.

#### Batch Assignment

Fields:

- `Assign Multiple Processes Simultaneously`
- `Common Owner`

Button:

- `Batch Assign`

#### Individual Assignment per Process

Field:

- `Assign Owner`

Button:

- `Assign`

### 9.6 Section `Unassigned Roles`

Shows roles from process models that have not yet been assigned to an organizational unit.

Fields and buttons:

- `Existing Organizational Unit`
- `Assign`
- `Create as New Organizational Unit`
- `Create & Assign`
- `Role`

Meaning of `Role`:

This marks that a term is deliberately only a process role and should not represent an organizational unit.

### 9.7 Section `Already Decided Candidates`

Shows a history of already processed organizational candidates.

Typical columns:

- Candidate
- Status
- Mapped to
- Last seen

### 9.8 Section `Consolidate Organizational Units`

This area is for merging professional duplicates in organizational units.

Typical use case:

- The same unit was imported from different sources with different names.
- A previous misassignment should be permanently corrected.

Fields:

- `Source`: the organizational unit to be resolved
- `Target`: the organizational unit to remain

Before the actual merge, BRIDGR shows a precheck with:

- Number of incoming and outgoing relationships of the source
- Note on already existing similar relationships at the target
- Alias adoption of the source name
- Compact note on the professional effects of the merge

#### Button `Execute Merge`

Merges the selected source organizational unit into the target organizational unit.

This happens:

- Existing professional relationships are transferred to the target.
- Already existing similar relationships are not created twice.
- The name of the source is continued as an alias of the target.
- The source organizational unit then disappears from the professional view.

Important:

- This function applies only to organizational units. Process duplicates are consolidated in the `Assignments` tab in the `Data Maintenance` area.

---

## 10. Tab `EA Model`

### 10.1 Purpose

This tab is responsible for ArchiMate-related functions:

- Maintain mapping between BRIDGR and ArchiMate
- Import ArchiMate files
- Export the complete BRIDGR graph as an ArchiMate file

### 10.2 Section `Configure Mapping`

#### Expander `Elements`

For each BRIDGR label, there are two selection fields:

- `Import: ArchiMate Type`
- `Export: ArchiMate Type`

This determines:

- Which ArchiMate type is assigned to which BRIDGR label during import
- Which ArchiMate type is generated for this BRIDGR label during export

#### Checkbox `Edit Relationship Mapping`

Enables editing of relationship mappings.

#### Expander `Relationships`

Available per label pair:

- `Import: Accepted AM Types`
- `Export: AM Type`
- `BRIDGR Relation` — determines which edge type is written in Neo4j

Important: All three fields must be consistently maintained. If the BRIDGR relation for a label pair is missing, relationships of this type are silently skipped during import, even if the ArchiMate type is in the import list.

#### Button `Save Mapping`

Saves the ArchiMate mapping permanently.

### 10.3 Section `Open Assignments`

Appears only if there are unclear ArchiMate candidates.

Buttons per candidate:

- `✓`: Confirm candidate
- `✗`: Reject candidate

### 10.4 Section `Import`

#### Field `Upload ArchiMate File (.xml or .archimate)`

File upload for an ArchiMate file.

#### Button `Import`

Starts the ArchiMate import.

After a successful import, BRIDGR shows, among other things:

- Imported elements
- Generated candidates
- Skipped elements
- Imported relationships
- Skipped relationships

### 10.5 Section `Export`

#### Button `Export as ArchiMate`

Exports the complete BRIDGR graph as an ArchiMate file.

Important:

- The export always includes the entire graph.
- Partial exports are not provided in the current version.

---

## 11. Tab `Configuration`

This tab bundles all technical settings. The process import itself is started in the `Import` tab.

### Section `Select Paths`

Buttons:

- `Select Input Folder`
- `Select Output Folder`

These buttons open file selection or folder dialogs.

### Section `LLM`

Additional help:

- The preset buttons `OpenAI` and `Ollama` can directly prefill typical standard values.
- The field `API Key (Environment Variable)` expects the name of the environment variable with the key, not the secret key value itself. For OpenAI, `OPENAI_API_KEY` is typically meant.

Fields:

- `LLM Endpoint`: URL of the OpenAI-compatible LLM service
- `LLM Model`: Name of the model used
- `API Key (Environment Variable)`: Name of the environment variable with the API key
- `Context Window`: Number of context messages for the chat
- `LLM Timeout (Seconds)`: Maximum wait time for LLM responses
- `Chat Mode`: Selection between `prompt-only` and `tool-use`

Note on `Chat Mode`:

- `prompt-only` is the more compatible fallback for simple or local models.
- `tool-use` uses formal function calling and requires backend support.

### Section `Neo4j`

Fields:

- `Neo4j URL`
- `Neo4j User`
- `Neo4j Password`
- `Neo4j Database`

These fields control the connection to the graph database.

### Section `File Paths`

Fields:

- `Input Path`
- `Output Path`

#### Section `CMDB Column Mapping — Relationship Columns (Type File Format)`

Configures which columns in the application file contain the relationships to servers and interfaces:

- `Column 'runs on'` — Column names for server IDs (default: `runs_on`)
- `Column 'uses interfaces'` — Column names for interface IDs (default: `uses_interfaces`)
- `Multi-value Separator` — Separator for multiple target IDs in a cell (default: `|`)

### Section `CMDB Column Mapping — Entities`

Fields:

- `ID Column`
- `Name Column`
- `Type Column`
- `Server Type Column`
- `Owner Column`

These fields must match the column names of your CMDB CSV files.

Note on file format: BRIDGR automatically detects the delimiter of the CSV files. Both comma (`,`) and semicolon (`;`) are supported.

#### Section `CMDB Column Mapping — Relations (Legacy Format)`

Applies only if the older two-file format is still used.

Fields:

- `Source ID Column`
- `Relation Type Column`
- `Target ID Column`

#### Section `Import & Matching`

Fields:

- `Fuzzy Threshold`: determines how tolerant BRIDGR is with fuzzy name similarities
- `Default Import Mode`: default value for `full` or `partial`
- `Debug Mode`: writes additional diagnostic data

#### Section `Backup and Restore`

- `Retention Snapshots`: Number of valid graph snapshots that BRIDGR retains (default: `10`). A snapshot is automatically created before process import, CMDB synchronization, and merge.
- The table shows the time, trigger, operation, and number of saved nodes and relationships. Invalid snapshots cannot be restored.
- For a restore, select a valid snapshot, confirm the full restoration of the BRIDGR graph, and click `Restore Snapshot`.

Before the restoration, BRIDGR additionally creates a pre-restore snapshot. This allows even an accidentally chosen restoration to be undone. The restoration replaces the entire content of the configured Neo4j database; use only a dedicated BRIDGR database for this and enter its name in the `Neo4j Database` field.

#### Button `Save Configuration`

Saves all changes in the configuration.

#### Button `Recheck Neo4j Connection`

Checks if the graph database is reachable with the current information.

#### Button `Update Models`

Queries the models available at the LLM endpoint.

#### Button `Recheck LLM Connection`

Checks the connection to the LLM and the model availability.

#### Area `Current Configuration`

Shows the currently effective configuration as JSON.

---

## 12. Typical Usage Scenarios

### 12.1 First Import

1. Set up LLM and Neo4j in the `Configuration` tab
2. Place process files and CMDB files (applications, servers, interfaces) in `Input/`
3. In the `Import` tab, assign the CMDB type files to the object types and save with `Adopt Type Files`
4. If necessary, `Synchronize CMDB to Neo4j`
5. `Start Pipeline`
6. Then check `Assignments` and `Organization`

Note:
If you expand or correct a CMDB later, step 4 may already be sufficient to reassess existing open assignments from the last run. A new process import is not necessarily required for this.

### 12.2 Clean Up Open Assignments

1. Open the `Assignments` tab
2. Set scope and status filter
3. Confirm, reject, or manually create open cases
4. Then open the `Organization` tab and clarify open organizational questions
5. If necessary, check last manual changes in the `Data Maintenance` area of the `Assignments` tab or consolidate processes; consolidate organizational units in the `Organization` tab

### 12.3 Ask Questions to the Graph

1. Ensure that data has already been imported
2. Open the `Communication` tab
3. Enter the question in natural language
4. Export results as CSV if necessary

---

## 13. Common Problems

### No Chat Response Possible

Possible causes:

- No LLM model configured
- Neo4j access data missing
- Connections are not reachable

### No Meaningful Import

Possible causes:

- Files are not in the correct input path
- CMDB column mapping does not match the CSV
- LLM is not reachable
- BPMN file is very large and should be transformed first

### No or Few Hits in Review

Possible causes:

- There were already strong automatic assignments
- The process file was not successfully processed
- Status filter or file filter restricts the view

---

## 14. Short Version for New Users

If you are using BRIDGR for the first time, this procedure is usually sufficient:

1. Open `Configuration`
2. Enter LLM and Neo4j
3. Place files in `Input/`
4. Start the pipeline in the `Import` tab
5. Check open cases in `Assignments`
6. Clarify responsibilities in `Organization`
7. Ask questions to the graph in the `Communication` tab

This allows you to use BRIDGR productively without development knowledge.
```
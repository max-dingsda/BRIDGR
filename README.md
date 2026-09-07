# BRIDGR

BRIDGR is an enterprise-architecture assistant and knowledge graph. It brings
process documents, CMDB exports, and ArchiMate models together and makes the
result available through a controlled natural-language chat interface.

Users do not need to create BPMN or ArchiMate models themselves. BRIDGR can
import existing process descriptions and architecture models, then connects them
with CMDB data. An LLM extracts and queries information; BRIDGR validates the
resulting graph operations and never permits the LLM to write directly to Neo4j.

German documentation is available in [DE_README.md](DE_README.md). The detailed
architecture and user guide are available in German as
[DE_Bridgr_Architektur_v29.md](Specs/DE_Bridgr_Architektur_v29.md) and
[DE_Benutzeranleitung_BRIDGR.md](Specs/DE_Benutzeranleitung_BRIDGR.md).

## How BRIDGR works

```text
Process document (BPMN, TXT, DOCX, PDF)
        |
        v
Text extraction
        |
        v
LLM extraction of processes, roles, organizational candidates, and applications
        |
        v
CMDB matching and review of uncertain matches
        |
        v
Neo4j enterprise-architecture knowledge graph
        |
        v
Streamlit workspace and conversational query interface
```

Matching follows a predictable order: confirmed decisions, rejections, aliases,
fuzzy candidates, and finally manual review. Strong matches are written to the
graph; uncertain matches stay reviewable until a user confirms or rejects them.

## Canonical graph schema

BRIDGR uses an English canonical Neo4j schema. Labels include `Process`,
`Application`, `Interface`, `Server`, `OrgUnit`, and `Role`; relationships include
`SERVES`, `MAY_SERVE`, `RESPONSIBLE_FOR`, `PARTICIPATES_IN`, `CAN_ASSUME`,
`FOLLOWS`, `USES_INTERFACE`, and `RUNS_ON`.

Business names are source data. For example, `(:Process {name: "Rechnungseingang"})`
and `(:Process {name: "Incoming Invoice"})` are equally valid. BRIDGR does not
translate source names or invent a normalized business vocabulary.

This schema is a breaking change. Use an empty dedicated Neo4j database for this
release; legacy graph data and snapshots are intentionally not migrated.

## Workspace

The Streamlit workspace provides six tabs:

- Chat: question the knowledge graph in natural language.
- Import: process documents, transform large BPMN files, and synchronize CMDB data.
- Mappings: review uncertain application matches and maintain decisions.
- Organization: resolve organization candidates, responsibilities, roles, and duplicates.
- EA Model: import and export ArchiMate Exchange Format models.
- Configuration: configure LLM, Neo4j, paths, matching behavior, snapshots, and the default UI language.

The UI is available in German and English. The language switch controls catalogued
UI text. Chat replies follow the language of the user's question; object names and
the graph schema remain unchanged.

## Configuration

Copy the distributed configuration template and adapt it for your environment:

```powershell
Copy-Item config.example.json config.json
streamlit run app.py
```

`config.json` is local and not versioned. Important settings include the
OpenAI-compatible LLM endpoint and model, Neo4j connection details, input and
output paths, CMDB column mapping, the fuzzy-match threshold, chat mode,
snapshot retention, and `ui_locale` (`de` or `en`).

CMDB data is normally supplied as one CSV file per type:

```json
"cmdb_type_files": {
  "application": "cmdb_applications.csv",
  "server": "cmdb_servers.csv",
  "interface": "cmdb_interfaces.csv"
}
```

The application file can declare `runs_on` server IDs and `uses_interfaces`
interface IDs. Column names and the multi-value delimiter are configurable.

## Inputs and outputs

- `Input/` is the working inbox for process documents and active CMDB files.
- Process documents successfully handled by the pipeline move to `data/input_archive/`.
- `Output/` contains the current run state, review artifact, debug log, and snapshots.

Snapshots protect write operations such as imports, CMDB synchronization, and
merges. Snapshot restoration replaces the complete configured database and is
therefore restricted to an explicitly configured dedicated BRIDGR database.

## Running tests

```powershell
conda run -n BRIDGR python -m pytest -q
```

## Contributing

BRIDGR is actively developed. Please describe defects and proposals in an issue,
and run the test suite before submitting a pull request.

## Review stabilization (2026-09-07)

Chat requires Neo4j Enterprise and a dedicated read-only account configured with
`neo4j_chat_user` / `neo4j_chat_password` (or `NEO4J_CHAT_USERNAME` /
`NEO4J_CHAT_PASSWORD`). Writer credentials are never used as a chat fallback.
Relative paths always refer to the repository root. Only CMDB type files are supported.

Real database regressions create and remove an isolated temporary database:

```powershell
$env:BRIDGR_RUN_NEO4J_TESTS = '1'
conda run -n BRIDGR python -m pytest -q
```

Opt into configured live-LLM acceptance separately with `BRIDGR_RUN_LLM_TESTS=1`.
This uses synthetic data in the disposable database. A skipped integration test
is not evidence that database guarantees passed.

For the optional Playwright smoke test, start the local app and set
`BRIDGR_RUN_BROWSER_TESTS=1` and `BRIDGR_BROWSER_URL` to its local URL.
The test uses installed Edge (`BRIDGR_BROWSER_CHANNEL=msedge` by default),
changes only session-local views, and does not save configuration or mutate domain data.

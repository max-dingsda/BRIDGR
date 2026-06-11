# BRIDGR — Lessons Learned

This file documents recurring pitfalls and their prevention strategies encountered during development.
It is a reference for developers and project owners, not an agent instruction file.

---

- **Neo4j config overridden by env vars:** UI config values were partially re-overwritten
  by `NEO4J_*` env vars because form fields rendered with empty `value` and only a `placeholder`.
  On save, fields could land empty in `config.json` and be refilled from `.env`.
  *Prevention:* Always write the currently active value into the field state in Streamlit forms
  for persistent config. Env fallbacks must not decouple display from saved semantics.

- **Invalid Cypher from local models:** Several local models produced formally valid-looking
  but Neo4j-illegal Cypher queries for aggregations and follow-up questions —
  multi-statement queries, inconsistent `UNION` returns, or unfiltered broad result sets.
  *Prevention:* Always constrain query generation with a tight schema whitelist from the
  real write model, explicit Cypher structure rules, and local pre-validation.

- **Timeouts on large BPMN/XML files:** Large enterprise BPMNs caused timeouts or
  invalid JSON in the local LLM path due to too much XML noise.
  *Prevention:* Reduce large enterprise BPMNs via a parse-based transformer to compact,
  semantically relevant import texts before the LLM run.

- **UI actions triggering full pipeline reruns:** Review confirmations or KB resets could
  accidentally restart the full pipeline on all input, causing unnecessary LLM calls.
  *Prevention:* UI actions with local business scope must not trigger a full pipeline run.
  Instead, update only `latest_run`/affected documents and execute only necessary Neo4j writes.

- **Neo4j write path diagnosed as ineffective (false negative):** Write paths were assumed
  ineffective locally, but data had been written correctly — to a different database instance
  than the one being inspected.
  *Prevention:* For any "nothing arrived in Neo4j" diagnosis, first verify that BRIDGR and
  Neo4j Browser/Desktop point to the same instance and `neo4j_database` name.

- **Idea requests turned into direct implementation too early:** A request for an idea or
  approach can be exploratory even when a concrete implementation seems straightforward.
  Implementing immediately removes the user's chance to refine the direction first.
  *Prevention:* If the user explicitly asks for an idea, an approach, or a proposal, answer
  with the solution outline first and wait for confirmation or adjustments before editing code.

- **Raw technical query errors are not user guidance:** Local query validation and Neo4j errors
  can be precise for developers while still being opaque to end users.
  *Prevention:* Translate technical query failures into short, human-understandable wording in
  the UI, while preserving the raw details only in debug logs or technical views.

- **Curated alternative names need deterministic handling:** Short forms or colloquial names such
  as `Sales` versus `Sales Department` should not be left to free LLM guessing after a failed query.
  *Prevention:* Project curated aliases into Neo4j and resolve them deterministically in code with
  explicit ambiguity handling.

- **Unstructured extraction can collapse multiple org/role mentions into one comma-separated value:**
  Local or remote models may return entries such as `Buchhaltung, Controlling` as a single string
  for `rolle` or `org_einheit_kandidaten` even when the source text lists separate bullet points.
  *Prevention:* Normalize multi-value role and org-candidate fields deterministically after LLM
  extraction for all unstructured text-based extractors (`txt`, `docx`, `pdf`) instead of relying
  on prompt compliance alone.

- **Local model upgrades can break JSON extraction despite better chat quality:** Upgrading from
  `gemma4:12b` to `gemma4:26b` improved conversational quality but caused catastrophic failures in
  the extraction pipeline: the larger model entered token-repetition loops (repeated keys, ASCII
  sequences, Cyrillic characters) when Ollama's `response_format: json_object` grammar constraint
  was active. Prompt simplification and temperature tuning did not resolve it. Root causes: (1) the
  26b model runs partially on CPU due to VRAM limits, causing instability; (2) larger models are
  not necessarily better instruction followers for schema-constrained tasks; (3) Ollama's GBNF
  grammar constraint interacts poorly with some model/quantization combinations.
  *Prevention:* After any model change, run a full import before considering the upgrade stable.
  For structured extraction, prefer models known for instruction-following quality over raw size.
  Validated working model for both chat and extraction on RTX 5060 Ti 16 GB: `qwen2.5:14b` (Q4_K_M,
  ~9 GB VRAM, 93% GPU utilization, zero retries on full import).
  *Open:* `json_temperature` in `LlmClientConfig` (default 0.1) is not yet exposed in `config.json`.

- **Prompt fixes cannot compensate indefinitely for an unsuitable chat model:** For broad EA
  questions such as risks, complexity, or governance gaps, two targeted prompt iterations improved
  behavior, but some local models still failed the basic assistant contract: unfinished answers,
  leaked internal work notes or draft queries, pseudo-analysis without executed graph evidence, or
  unnecessary refusal despite clear default indicators. This is a model suitability problem, not an
  endlessly solvable prompt-tuning problem.
  *Prevention:* Use prompt work to correct genuine instruction gaps, but stop after a small number
  of focused iterations and classify models explicitly as suitable, conditionally suitable, or
  unsuitable for the EA chat role. Keep prompts optimized for robust models instead of bloating them
  to rescue weak ones. Models that repeatedly violate the tool/answer contract for abstract EA
  questions should be excluded from future chat-model evaluations for this use case.

- **Suspicious chat answers can originate from stale graph residues, not current code behavior:**
  A follow-up answer to an ownerless-process query returned technical names such as `t1 -> t2`,
  which initially looked like a model or query-layer failure. Direct Neo4j inspection showed these
  were old `(:Prozess {placeholder: true})` nodes without `prozess_id`, linked via `FOLGT_AUF` to
  a real process. After clearing the database and re-running a full import, the placeholder nodes
  were not reproduced; the current code produced only proper business process names. Root cause:
  stale database state can survive across iterations and mimic active import defects.
  *Prevention:* Before changing code for suspicious graph-query results, first verify whether the
  anomaly survives a clean database reset plus full reimport. Inspect `placeholder` flags and
  technical name patterns (for example `->`) directly in Neo4j before treating the issue as a
  current pipeline bug.

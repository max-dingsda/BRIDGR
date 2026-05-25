# Bridgr — Code Review Findings
**Stand:** 2026-05-25  
**Reviewer:** Claude Code (automated review)  
**Branch:** main (389e655)

---

## Kritische Findings (sofort handeln)

### F-01 — Hardcodierte Produktions-Credentials in config.json
**Datei:** `config.json`  
**Schweregrad:** 🔴 KRITISCH

`config.json` enthält plaintext Neo4j-Aura-Credentials (URL, User, Passwort, Datenbankname). Die Datei liegt im Repository und ist damit für jeden mit Lesezugriff sichtbar.

**Empfehlung:**
1. Credentials sofort aus `config.json` entfernen und rotieren
2. Nur Platzhalter als Default (`""`) eintragen
3. Echte Werte nur via `.env` oder Umgebungsvariablen setzen
4. `config.json` mit echten Werten via `.gitignore` ausschließen — oder besser: Werte nie in diese Datei schreiben (bereits durch `resolve_env_backed_value()` in `app_config.py` vorbereitet)

---

## High-Severity Findings

### F-02 — Generische Exception-Behandlung in `neo4j_utils.py`
**Datei:** [neo4j_utils.py](../neo4j_utils.py)  
**Schweregrad:** 🟠 HIGH

`_execute()` fängt alle Exceptions als `Neo4jConnectionError` — Verbindungsfehler, Auth-Fehler und Syntax-Fehler werden damit gleichbehandelt. Das erschwert die Fehleranalyse erheblich.

```python
# Aktuell: pauschal
except Exception as exc:
    raise Neo4jConnectionError(str(exc)) from exc
```

**Empfehlung:** Unterscheidung nach `DriverError`, `ClientError`, `CypherSyntaxError` aus `neo4j.exceptions`.

---

### F-03 — LLM-Client verwendet `urllib` statt `requests`
**Datei:** [llm_client.py](../llm_client.py)  
**Schweregrad:** 🟠 HIGH

Der LLM-Client nutzt `urllib.request` ohne Connection-Pooling, Retry-Logik oder Session-Management. Jede Anfrage öffnet eine neue TCP-Verbindung.

**Empfehlung:** Migration auf `requests.Session()`. Damit entfallen auch die aktuell sehr ausführlichen Try/Except-Blöcke um URL-Parsing und Error-Handling.

---

### F-04 — Typ-Inkonsistenz zwischen `match.py` und `knowledge_base.py`
**Datei:** [skills/match.py](../skills/match.py), [knowledge_base.py](../knowledge_base.py)  
**Schweregrad:** 🟠 HIGH

`match_application_candidates()` deklariert `list[dict[str, str]]` für `confirmed_links`/`rejected_links`, während `KnowledgeBase` intern `list[dict[str, Any]]` verwendet. `cmdb_id` kann `None` sein, was unter `str` nicht passt.

**Empfehlung:** Vereinheitlichung auf `dict[str, Any]` oder Einführung von `TypedDict`-Klassen (`ConfirmedLink`, `RejectedLink`).

---

### F-05 — CMDB-Datei ohne Fehlerbehandlung geladen
**Datei:** [cmdb.py](../cmdb.py)  
**Schweregrad:** 🟠 HIGH

`load_cmdb_rows()` gibt bei nicht vorhandener Datei stillschweigend `[]` zurück. Pflicht-Spalten (UUID, Name) werden nicht validiert. Malformed CSV hat keinen expliziten Fehlerfall.

**Empfehlung:**
- `FileNotFoundError` werfen statt leere Liste zurückgeben
- Pflicht-Spalten beim Einlesen prüfen (Übergabe via Parameter aus Config)
- `csv.Error` explizit abfangen

---

### F-06 — User-Input im Review-Tab ohne Längen-/Inhaltsvalidierung
**Datei:** [app.py](../app.py)  
**Schweregrad:** 🟠 HIGH

Manuell eingetragene Anwendungsnamen werden direkt in die KB übernommen. Keine Längenprüfung, keine Zeichenvalidierung, keine Deduplizierung.

**Empfehlung:** Einfache Validierungsfunktion vor dem KB-Schreiben: Max-Länge, Leerzeichen-Trimming, Leer-String-Prüfung.

---

### F-07 — Neo4j-Verbindung wird pro Anfrage neu aufgebaut
**Datei:** [app.py](../app.py)  
**Schweregrad:** 🟠 HIGH

Jeder Tab-1-Query erzeugt ein neues `Neo4jClient`-Objekt inkl. neuem Driver. Das Neo4j-Bolt-Protokoll sieht Connection Pooling vor, aber der Pool wird bei jedem `close()` verworfen.

**Empfehlung:** Client-Instanz im Streamlit Session-State cachen oder als `@st.cache_resource` halten.

---

## Medium-Severity Findings

### F-08 — `identity.py` ist ein Minimal-Stub
**Datei:** [skills/identity.py](../skills/identity.py)  
**Schweregrad:** 🟡 MEDIUM

Laut Architektur verwaltet `identity.py` die Prozessidentität über mehrere Runs. Aktuell extrahiert die Datei nur BPMN-Prozess-IDs aus XML. Die KB-Integration (z. B. Name-Disambiguation über Runs) fehlt.

**Status:** Bewusst für v1 abgespeckt (Neu-1 in `openPointsClaude.md`). Explizit als Stub markieren.

---

### F-09 — Inkonsistente Pfadauflösung
**Datei:** [app_config.py](../app_config.py)  
**Schweregrad:** 🟡 MEDIUM

`resolve_project_path()` liefert Pfade, die möglicherweise nicht existieren. `resolve_runtime_output_path()` hat Fallback-Logik, `resolve_input_cmdb_path()` nicht. Das führt zu unterschiedlichen Fehlerprofilen je nach Einstiegspunkt.

**Empfehlung:** Dokumentation der Garantien (existiert vs. existiert möglicherweise) oder Vereinheitlichung.

---

### F-10 — Read-Only-Validierung in `neo4j_utils.py` prüft keine String-Literale
**Datei:** [neo4j_utils.py](../neo4j_utils.py)  
**Schweregrad:** 🟡 MEDIUM

`validate_read_only_cypher()` konvertiert die Query zu Uppercase und prüft auf verbotene Tokens. Tokens innerhalb von String-Literalen (z. B. `RETURN "CREATE this"`) würden irrtümlich blockiert. Tokens in Kommentaren ebenfalls.

**Empfehlung:** Tests für Edge Cases (String-Literale, `//`-Kommentare, `/* */`-Kommentare) ergänzen.

---

### F-11 — Fehlende Fehler-Szenarien in den Tests
**Datei:** [tests/](../tests/)  
**Schweregrad:** 🟡 MEDIUM

Happy-Path-Coverage vorhanden. Folgende Szenarien fehlen:
- LLM-Timeout / ungültige JSON-Antwort
- Neo4j-Verbindungsausfall während Pipeline
- Korrupte `kb.json`
- CMDB mit fehlenden Pflicht-Spalten
- BPMN mit kaputtem XML

---

### F-12 — `requirements.txt` enthält `neo4j` nicht
**Datei:** [requirements.txt](../requirements.txt)  
**Schweregrad:** 🟡 MEDIUM

`neo4j` ist nur in `requirements-dev.txt` (falls vorhanden) oder implizit durch Conda enthalten. Ein `pip install -r requirements.txt` auf einer frischen Umgebung würde `neo4j_utils.py` nicht lauffähig machen.

**Empfehlung:** `neo4j>=5.0,<6.0` in `requirements.txt` aufnehmen.

---

### F-13 — Magic Strings an vielen Stellen
**Datei:** Mehrere Dateien  
**Schweregrad:** 🟡 MEDIUM

Strings wie `"stark"`, `"schwach"`, `"knowledge_base"`, `"fuzzy"`, `"processed"`, `"skipped_unchanged"` sind über `app.py`, `skills/match.py`, `pipeline.py` und `graph_writer.py` verteilt.

**Empfehlung:** Konstantenmodul `constants.py` mit `DocumentStatus`, `Confidence`, `MatchSource`.

---

### F-14 — Streamlit-Versionsschranke zu eng
**Datei:** [requirements.txt](../requirements.txt)  
**Schweregrad:** 🟡 MEDIUM

`streamlit>=1.45,<1.57` schließt Sicherheits-Updates aus. Der Grund (Starlette-Kompatibilität lokal) sollte in einem Kommentar oder in `CLAUDE.md` dokumentiert sein, damit die Schranke nicht unbewusst aufgeweitet wird.

---

### F-15 — Session-State-Synchronisation mit Hardcoded-Pfadvergleichen
**Datei:** [app.py](../app.py)  
**Schweregrad:** 🟡 MEDIUM

`sync_config_session_defaults()` erkennt veraltete Default-Pfade via Zeichenkettenvergleich (`"data/input"`, `".\\data\\input"`). Das ist fragil und wächst mit jedem Pfadwechsel.

---

## Low-Severity Findings

### F-16 — Fehlende Docstrings bei öffentlichen Funktionen
**Datei:** Alle Module  
**Schweregrad:** 🟢 LOW

Öffentliche Funktionen (z. B. `match_application_candidates`, `write_graph`, `confirm_link`) haben keine Docstrings. IDE-Hints und automatische Dokumentation sind damit eingeschränkt.

---

### F-17 — Silent-Pass bei Neo4j-Client-Schließung
**Datei:** [app.py](../app.py)  
**Schweregrad:** 🟢 LOW

`finally: neo4j_client.close()` fängt Exceptions mit `pass`. Ressourcen-Leck-Hinweise werden dadurch verworfen.

**Empfehlung:** `st.warning(...)` statt `pass`.

---

### F-18 — Potenzielle Regex-Injection in `_extract_json_block()`
**Datei:** [llm_client.py](../llm_client.py) (oder entsprechende Funktion)  
**Schweregrad:** 🟢 LOW

Falls die Funktion rohe LLM-Ausgabe als Regex-Pattern verwendet, besteht minimales ReDoS-Risiko. Prüfen, ob JSON-Extraktion über `re.search` auf roh-string arbeitet.

---

## Umsetzungsstatus nach Review

### Aufgegriffen und umgesetzt

- `F-01` Secrets aus `config.json` entfernt; Neo4j-Werte werden env-backed behandelt; secrets invaldiert und zurückgesetzt
- `F-02` Neo4j-Fehler in `neo4j_utils.py` nach Verbindungs-, Auth-, Query- und Syntaxfehlern getrennt
- `F-03` `llm_client.py` von `urllib` auf `requests.Session()` umgestellt
- `F-04` KB-/Match-Typen ueber `TypedDict` vereinheitlicht
- `F-05` CMDB-Validierung fuer Datei, Header und Pflichtspalten ergaenzt
- `F-06` Validierung fuer manuelle Review-Eingaben ergaenzt
- `F-07` Neo4j-Client in Streamlit-Session wiederverwendet statt pro Anfrage neu aufgebaut
- `F-08` `identity.py` explizit als bewusster `v1`-Stub markiert
- `F-09` Pfadgarantien in `app_config.py` expliziter dokumentiert
- `F-10` Read-only-Cypher-Validierung gegen String-Literale und Kommentare gehaertet
- `F-11` Fehlerszenario-Tests fuer LLM-JSON, Neo4j-Ausfall, korrupte `kb.json`, fehlende CMDB-Spalten und kaputtes BPMN ergaenzt
- `F-12` `neo4j` explizit in `requirements.txt` und `pyproject.toml` aufgenommen
- `F-13` zentrale Status-/Confidence-/Match-Quellen in `constants.py` eingefuehrt
- `F-15` harter Legacy-Pfadvergleich in Session-State-Synchronisation durch robusteren Helper ersetzt
- `F-17` stilles Schlucken von Neo4j-Close-Fehlern entfernt; Warnings bei fehlerhaftem Schliessen
- `F-18` JSON-Extraktion im LLM-Pfad regexfrei gemacht; sicherer Brace-/String-Scanner statt potenziell riskanter Regex-Variante

### Bewusst zurueckgestellt

- `F-14` Streamlit-Versionsschranke dokumentieren
  Status: bewusst vertagt, weil funktional kein Blocker und derzeit keine unmittelbare Folgegefahr fuer die Weiterentwicklung
- `F-16` Docstrings fuer oeffentliche Funktionen
  Status: bewusst vertagt zugunsten funktionaler und sicherheitsrelevanter Arbeiten

### Projektinterne Ergaenzung ausserhalb des externen Reviews

- UI-Verwaltung fuer die Knowledge Base ergaenzt: KB komplett, nur `confirmed` oder nur `rejected` direkt aus der App leerbar

---

## Architektur-Compliance

| Architektur-Prinzip (CLAUDE.md) | Status |
|---|---|
| Prompts over code — Intelligence in `.md`-Dateien | ✅ Compliant |
| Sequential pipeline — kein Parallelismus | ✅ Compliant |
| Idempotente Pipeline — Hash-basiertes Überspringen | ✅ Compliant |
| CMDB als Single Source of Truth — nur `cmdb_id` im Graph | ✅ Compliant |
| KB-first Matching — KB → Fuzzy → LLM | ✅ Compliant |
| Neo4j-Schema (Constraints, Labels, Relations) | ✅ Compliant |
| Read-only Neo4j-User (Neu-2) | ⚠️ Nur Query-Validierung, kein DB-User |
| Prozessidentität über Runs (Neu-1) | ⚠️ Minimal-Stub, dokumentieren |
| v1-Scope: nur BPMN | ✅ Compliant |

---

## Zusammenfassung

| Kategorie | Anzahl | Schweregrad |
|---|---|---|
| Kritisch | 1 | 🔴 |
| High | 6 | 🟠 |
| Medium | 7 | 🟡 |
| Low | 3 | 🟢 |
| **Gesamt** | **17** | |

**Sofortmaßnahmen (heute):**
1. `config.json` bereinigen und Neo4j-Passwort rotieren
2. `.gitignore` prüfen — `config.json` darf keine Secrets enthalten

**Nächste Sprint-Items:**
- F-02, F-03, F-04 (Code-Qualität / Typing)
- F-05, F-06 (Input-Validierung)
- F-11 (Test-Coverage für Fehlerszenarien)
- F-12 (requirements.txt vervollständigen)

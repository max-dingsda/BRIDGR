# Bridgr
**CMDB-Zielarchitektur** | Stand: Juni 2026 | v0.19

---

## 1. Ziel

Prozessdokumentation und CMDB-Export zusammenfuehren, um einen EA-Wissensgraphen aufzubauen
und ihn ueber eine natuerlichsprachliche Web-Oberflaeche abfragbar zu machen.

Kernfrage:
Welche IT-Bausteine unterstuetzen welche Geschaeftsprozesse und wie sicher wissen wir das?

Bridgr schliesst die Luecke klassischer Discovery-Tools: Diese kennen die IT-Landschaft,
aber nicht den Business-Kontext aus Prozessdokumentation.

### Visionsziel: vollwertiger EA-Chatbot

Der Tab "Kommunikation" ist kein einfaches Query-Werkzeug, sondern ein vollwertiger
Unternehmens-Architektur-Chatbot. Benutzer stellen Fragen in natuerlicher Sprache zu
IT-Bausteinen, Prozessen und deren Beziehungen und erhalten kontextbewusste,
gesprächsfoerdernde Antworten — unabhaengig davon, wie die Frage formuliert ist.

Dieses Visionsziel ist der Massstab fuer alle Designentscheidungen im Abfrage-Layer.
Jede Abwaegung in diesem Bereich wird daran gemessen.

---

## 2. Gesamtarchitektur

Das System besteht weiterhin aus zwei klar getrennten Schichten:

- Pipeline:
  Prozessdokumente + CMDB -> optionale Vortransformation fuer grosse BPMN -> Extraktion
  -> Matching -> Review-Artefakte -> Graph-DB
- Abfrage-Layer:
  Web-UI -> LLM (Orchestrator) -> Tool: Cypher-Ausfuehrung -> Neo4j -> Antwort in
  natuerlicher Sprache

Die Pipeline bleibt sequentiell, nachvollziehbar und idempotent.

Der Abfrage-Layer wechselt in v0.19 grundlegend das Architekturmuster:
Der LLM wird zum Orchestrator; imperativische Code-seitige Gesprächszustandsverwaltung
entfaellt zugunsten von nativem LLM-Konversationsmanagement.

---

## 3. Inputs und Dateifluss

*(unveraendert gegenueber v0.18)*

### 3.1 Eingangsdateien

- Prozessdokumente:
  BPMN sowie unstrukturierte Prozessbeschreibungen als TXT, DOCX oder PDF
- Transformierte BPMN-Prozessdateien:
  aus grossen BPMN/XML-Dateien abgeleitete, kompakte TXT-Dateien mit genau einer
  Importeinheit pro Prozess
- CMDB-Export:
  vorerst nur CSV

### 3.2 Inbox-Prinzip

`Input/` ist die reine Inbox des Benutzers.

- der Benutzer legt dort neue Prozessdateien und die aktuell zu verwendende CMDB-Datei ab
- `Input/` und seine Unterordner dienen nicht als dauerhafter Ablageort bereits verarbeiteter
  Prozessdateien
- nach einem erfolgreichen Importlauf verschwinden die verarbeiteten Prozessdateien aus der
  Inbox

### 3.3 Archivierung verarbeiteter Dateien

```text
bridgr/
├── Input/
├── data/
│   └── input_archive/
│       └── <run-id-oder-timestamp>/
│           ├── <prozessdatei1>
│           └── ...
```

---

## 4. Scope v0.19

| Bereich | In Scope | Out of Scope |
|---|---|---|
| Eingabeformate | BPMN, TXT, DOCX, PDF, CMDB als CSV | ODT/ODF und weitere CMDB-Dateiformate |
| UI | Streamlit Web-UI (4 Tabs) | CLI-Review |
| Chat-Architektur | Tool-Use (LLM als Orchestrator) mit Prompt-Only-Fallback | Multi-Agenten-Orchestrierung |
| LLM-Backends | OpenAI-kompatible API (lokal und remote); Tool-Use wenn unterstuetzt | cloud-spezifische Provider-Integrationen |
| Review | Bearbeitung schwacher oder offener Matching-Faelle | Externes Ticketing |
| Lauf-Modi | `full`, `partial` | automatische Delta-Erkennung als eigener UI-Modus |
| CMDB-Modell | `Anwendung`, `Schnittstelle`, `Server`, `OrgEinheit` | tiefe Attributmodellierung |
| Deployment | Lokal / Docker | Cloud-Deployment |

---

## 5. Domaenenmodell

*(unveraendert gegenueber v0.18)*

### Prozess

Ein Prozess entspricht bei BPMN einem `<process>`-Element. Bei transformierten
BPMN-TXT-Dateien entspricht eine Datei genau einem Prozess.

### folgt_auf

Bei BPMN aus dem Sequenzzusammenhang abgeleitet. Bei unstrukturierten Formaten nur dann
befuellt, wenn die Beschreibung dies explizit hergibt.

### Anwendung

Ein in der CMDB gefuehrtes System. Pflichtattribute: `id`, `name`.

### Schnittstelle

Ein in der CMDB separat gefuehrter Integrations- oder Uebergabepunkt. Pflichtattribute:
`id`, `name`.

### Server

Ein physischer oder virtueller Infrastrukturknoten aus der CMDB. Pflichtattribute: `id`,
`name`, `server_type` (`physical` oder `virtual`).

### Rolle und OrgEinheit

`rolle` wird aus Prozessquellen uebernommen. `org_einheit` wird nur direkt gesetzt bei
1:1-Match gegen bekannte Organisationseinheiten. Moegliche Organisationseinheiten aus
Prozessdokumenten bleiben Kandidaten bis zur Bestaetigung in Tab 4.

### Verantwortung

`VERANTWORTET` ist eine generische Beziehung von `OrgEinheit` zu Prozess, Anwendung,
Schnittstelle oder Server. Unsichere Owner-Strings aus der CMDB werden als Kandidaten
behandelt, nicht direkt geschrieben.

---

## 6. Anwendungsschichten

*(unveraendert gegenueber v0.18)*

```text
bridgr/
├── prompts/
├── skills/
├── services/
│   ├── import_service.py
│   ├── organization_service.py
│   ├── query_service.py
│   ├── review_service.py
│   └── runtime_service.py
├── ui/
│   ├── config_tab.py
│   ├── organization_tab.py
│   ├── query_tab.py
│   └── review_tab.py
├── knowledge_base/
├── Input/
├── Output/
├── data/
├── config.json
├── app.py
└── main.py
```

Verantwortlichkeiten bleiben gegenueber v0.18 unveraendert. `query_service.py` wird
vereinfacht: imperativische Gesprächszustandsverwaltung entfaellt, der Service kapselt
kuenftig die Tool-Ausfuehrung und System-Prompt-Zusammenstellung.

---

## 7. Importlogik

*(unveraendert gegenueber v0.18)*

Zwei Importmodi:
- `full`: gesamter Prozessdateibestand aus `Input/`
- `partial`: vom Benutzer explizit ausgewaehlte Dateien

---

## 8. Matching und Review

*(unveraendert gegenueber v0.18)*

Reihenfolge: Knowledge Base -> Fuzzy Matching -> optionaler LLM-Fallback.

Schwache Kandidaten bleiben reviewbar.

---

## 9. Graph Writer

*(unveraendert gegenueber v0.18)*

```cypher
(:Prozess)
(:Anwendung)
(:Schnittstelle)
(:Server)
(:OrgEinheit)
(:Alias)

(:OrgEinheit)-[:VERANTWORTET]->(:Prozess)
(:OrgEinheit)-[:VERANTWORTET]->(:Anwendung)
(:OrgEinheit)-[:VERANTWORTET]->(:Schnittstelle)
(:OrgEinheit)-[:VERANTWORTET]->(:Server)
(:Prozess)-[:FOLGT_AUF]->(:Prozess)
(:Anwendung)-[:DIENT]->(:Prozess)
(:Anwendung)-[:USES_INTERFACE]->(:Schnittstelle)
(:Anwendung)-[:RUNS_ON]->(:Server)
(:Schnittstelle)-[:RUNS_ON]->(:Server)
(:Alias)-[:KANN_MEINEN]->(:OrgEinheit)
(:Alias)-[:KANN_MEINEN]->(:Anwendung)
```

---

## 10. Abfrage-Layer

### 10.1 Visionsziel

Tab "Kommunikation" ist ein vollwertiger EA-Chatbot. Der Benutzer muss keine besondere
Abfragesyntax kennen. Folgefragen, Rueckfragen, Praezisierungen und Kontextwechsel werden
nativ als Gespraech behandelt.

### 10.2 Architekturprinzip: LLM als Orchestrator

Der LLM treibt die Konversation. Code stellt Werkzeuge bereit, die der LLM aufruft.

```
Benutzereinagbe
   ↓
LLM (Orchestrator)
   ├── Tool: execute_cypher(query) ──→ Neo4j ──→ Ergebnis-Rows
   │      (wiederholbar pro Turn)
   └── Antwort in natuerlicher Sprache
```

Der LLM entscheidet eigenstaendig:
- ob und welche Cypher-Query zur Beantwortung benoetigt wird
- ob mehrere Queries nacheinander noetig sind (z. B. Zaehlabfrage, dann Detailabfrage)
- ob eine Rueckfrage an den Benutzer sinnvoller ist als eine Query
- wie er Mehrdeutigkeiten im Kontext der Gesprächshistorie aufloest

Imperativische Gesprächszustandsverwaltung (Pending-Options, Fokus-Entitaet,
Disambiguierungslogik) entfaellt aus dem Code. Der LLM traegt diesen Kontext nativ.

### 10.3 Tool: execute_cypher

Das primaere (und zunaechst einzige) Tool.

Signatur:

```
execute_cypher(query: str) -> {rows: list[dict], error: str | null}
```

Verhalten:
- der Code validiert die Query vor Ausfuehrung (read-only, Schema-konform)
- bei Validierungsfehler wird der Fehler als Tool-Fehlerantwort zurueckgegeben; der LLM
  kann die Query korrigieren und erneut aufrufen
- bei leerem Ergebnis wird serverseitig deterministisch nach Alias-Treffern gesucht;
  vorhandene Aliase werden im Tool-Ergebnis als Hinweis mitgegeben, damit der LLM
  entscheiden kann, ob er die Query auf den kanonischen Namen umschreibt oder den Benutzer
  fragt
- der Code schreibt niemals in den Graphen; das Tool ist strikt read-only

### 10.4 System-Prompt

Der System-Prompt enthaelt:

- Rollenbeschreibung: EA-Chatbot fuer Unternehmen X, kennt den Wissensgraphen
- vollstaendiges Graph-Schema aus `graph_schema.py`
- Tool-Beschreibung: Zweck, Signatur, Einschraenkungen von `execute_cypher`
- Ausgaberegeln: Sprache (Deutsch), Format, Umgang mit unbekannten Informationen
- Query-Regeln: read-only, schema-konservativ, keine erfundenen Beziehungstypen

Das Schema in `graph_schema.py` bleibt die kanonische Quelle. Prompt und Validierung
stuetzen sich auf diese Quelle, nicht auf Live-Introspektion der Datenbank.

### 10.5 Konversationshistorie

Die vollstaendige Gesprächshistorie (Benutzer- und Assistenznachrichten) wird bei jedem
LLM-Aufruf mitgegeben. Dadurch traegt der LLM nativ:

- Folgefragenkontexte
- Disambiguierungszustand ("welche Option hatte ich angeboten?")
- Topikfokus aus vorherigen Turns

Die Historientiefe wird durch ein konfigurierbares Maximum (z. B. 20 Nachrichten) begrenzt,
um Kontextfensterueberlaeufe zu verhindern. Aeltere Nachrichten werden abgeschnitten, nicht
zusammengefasst.

### 10.6 Dual-Mode-Betrieb

Nicht alle LLM-Backends unterstuetzen Tool-Use gleichwertig. Bridgr unterstuetzt deshalb
zwei Betriebsmodi, umschaltbar per Konfiguration:

**Tool-Use-Modus** (Standard fuer faehige Backends):
- LLM erhaelt das Tool als formales Function-Calling-Schema
- Tool-Aufrufe und -Ergebnisse werden als separater Message-Typ in der History gefuehrt
- LLM kann execute_cypher mehrfach pro Turn aufrufen

**Prompt-Only-Modus** (Fallback fuer lokale Modelle ohne Tool-Support):
- LLM gibt Cypher in einem definierten Format im Text aus (z. B. ```cypher-Block)
- Code extrahiert, validiert, fuehrt aus und gibt das Ergebnis als naechste Nachricht
  in der History zurueck
- LLM antwortet dann auf Basis dieses Ergebnisses

Beide Modi teilen denselben System-Prompt und dieselbe Validierungslogik.

### 10.7 Bereinigung der Code-Zustandsverwaltung — erledigt

Mit dem Wechsel auf LLM-als-Orchestrator wurden folgende Bestandteile entfernt:

- `CHAT_PENDING_APPLICATION_OPTIONS_STATE_KEY` und der zugehoerige Disambiguierungsstate
- `CHAT_FOCUS_ENTITY_STATE_KEY`
- `handle_query_clarification` und alle Unterfunktionen
- `resolve_application_clarification`, `_normalize_clarification_text`
- `_resolve_options_by_type`, `_resolve_clarification_fallback`
- `run_name_lookup_query`, `run_id_lookup_query`
- `build_follow_up_query_context`, `should_use_follow_up_context`

Verblieben ist:
- `execute_cypher`-Implementierung mit Validierung
- System-Prompt-Zusammenstellung (Schema + Rollenbeschreibung)
- Alias-Lookup als serverseitige Anreicherung des Tool-Ergebnisses
- Gesprächshistorie-Verwaltung (Befuellung, Kuerzen auf Maximum)
- Fehlertranslation fuer nicht behebbare technische Fehler

### 10.8 Migrationshinweis — erledigt

Der Umbau auf Tool-Use wurde als eigenstaendiger Schritt durchgefuehrt. Beide Modi
(Tool-Use und Prompt-Only) sind implementiert und per `chat_mode` in der Konfiguration
umschaltbar. Die imperativische Gesprächszustandsverwaltung ist vollstaendig entfernt.

---

## 11. Konfiguration

*(unveraendert gegenueber v0.18 mit Ergaenzungen)*

Tab 3 verwaltet zusaetzlich:

- Chat-Modus: `tool-use` oder `prompt-only` (mit Hinweis auf Backend-Anforderungen)
- Wissensbasis-Reset: gesamte KB leeren, nur Bestaetigungen leeren oder nur Ablehnungen leeren
  (inkl. konsistenter Alias-Synchronisation nach Neo4j)

---

## 12. Akzeptanzkriterien

Alle Kriterien aus v0.18 gelten weiterhin. Neu hinzugekommen:

13. Folgefragen, Praezisierungen und Kontextwechsel im Chat werden ohne imperativische
    Code-Zustandsverwaltung korrekt behandelt
14. Mehrdeutigkeiten werden vom LLM im Gesprächskontext aufgeloest, ohne dass dafuer ein
    separater Disambiguierungszustand im Code verwaltet werden muss
15. `query_service.py` kapselt Tool-Ausfuehrung und System-Prompt-Zusammenstellung;
    keine Gesprächszustandslogik ausserhalb der Gesprächshistorie

---

## 13. Getroffene Entscheidungen

*(alle Entscheidungen aus v0.18 bleiben gueltig; neu hinzugekommen:)*

| Entscheidung | Gewaehlt | Verworfen | Begruendung |
|---|---|---|---|
| Chat-Architektur | LLM als Orchestrator mit `execute_cypher` als Tool | deterministischer Code als Gesprächsmanager | Code-seitige Gesprächszustandsverwaltung wird mit wachsender Dialogvielfalt unwartbar; LLM loest Kontext, Disambiguierung und Folgefragen nativ |
| Dual-Mode | Tool-Use + Prompt-Only-Fallback | ausschliesslich Tool-Use | Bridgr soll mit lokalen Modellen ohne Function-Calling-Support betreibbar bleiben |
| Alias-Lookup | serverseitige Anreicherung des Tool-Ergebnisses | eigenes Tool oder LLM-freie Aufloesung | haelt die Alias-Semantik deterministisch, ohne dem LLM einen freien Inventionsraum fuer alternative Namen zu geben |
| Historienlaenge | konfigurierbares Maximum, alte Nachrichten werden abgeschnitten | Zusammenfassung aelterer Turns | Zusammenfassungen koennen fachlich relevante Details verlieren; Abschneiden ist deterministisch und nachvollziehbar |
| Scope deterministischer Matching-Code | bleibt fuer Import-Pipeline | auch fuer Chat-Disambiguierung | Import-Matching hat andere Anforderungen (Idempotenz, Auditierbarkeit) als Chat-Konversation |

---

*Bridgr | Architektur v0.19 | Stand Juni 2026*

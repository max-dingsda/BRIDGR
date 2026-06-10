# Bridgr
**Erweitertes ArchiMate-Mapping und Export-Precheck** | Stand: Juni 2026 | v0.22

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

Das System besteht aus zwei klar getrennten Schichten:

- Pipeline:
  Prozessdokumente + CMDB + ArchiMate-Modelle -> optionale Vortransformation fuer grosse BPMN
  -> Extraktion -> Matching -> Review-Artefakte -> Graph-DB
- Abfrage-Layer:
  Web-UI -> LLM (Orchestrator) -> Tool: Cypher-Ausfuehrung -> Neo4j -> Antwort in
  natuerlicher Sprache

Die Pipeline bleibt sequentiell, nachvollziehbar und idempotent.

Der LLM ist Orchestrator im Abfrage-Layer; imperativische Code-seitige
Gesprächszustandsverwaltung entfaellt zugunsten von nativem LLM-Konversationsmanagement.

---

## 3. Inputs und Dateifluss

### 3.1 Eingangsdateien

- Prozessdokumente:
  BPMN sowie unstrukturierte Prozessbeschreibungen als TXT, DOCX oder PDF
- Transformierte BPMN-Prozessdateien:
  aus grossen BPMN/XML-Dateien abgeleitete, kompakte TXT-Dateien mit genau einer
  Importeinheit pro Prozess
- CMDB-Export:
  vorerst nur CSV
- ArchiMate-Modelle:
  ArchiMate Exchange Format 3.x als XML (Dateiendung `.xml` oder `.archimate`)

ArchiMate-Dateien ersetzen die bestehenden Eingabeformate nicht. Sie ergaenzen den
BRIDGR-Graphen um eine weitere Quelle — analog zum CMDB-Import.

### 3.2 Inbox-Prinzip

`Input/` ist die reine Inbox des Benutzers.

- der Benutzer legt dort neue Prozessdateien, die aktuell zu verwendende CMDB-Datei
  und ArchiMate-Modelle ab
- `Input/` und seine Unterordner dienen nicht als dauerhafter Ablageort bereits
  verarbeiteter Prozessdateien
- nach einem erfolgreichen Importlauf verschwinden die verarbeiteten Prozessdateien
  aus der Inbox

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

## 4. Scope v0.22

| Bereich | In Scope | Out of Scope |
|---|---|---|
| Eingabeformate | BPMN, TXT, DOCX, PDF, CMDB als CSV, ArchiMate Exchange Format 3.x | ODT/ODF, weitere CMDB-Formate, Archi-natives `.archimate`-Format |
| UI | Streamlit Web-UI (5 Tabs) | CLI-Review |
| Chat-Architektur | Tool-Use (LLM als Orchestrator) mit Prompt-Only-Fallback | Multi-Agenten-Orchestrierung |
| LLM-Backends | OpenAI-kompatible API (lokal und remote); Tool-Use wenn unterstuetzt | cloud-spezifische Provider-Integrationen |
| Review | Bearbeitung schwacher oder offener Matching-Faelle inkl. ArchiMate-Kandidaten | Externes Ticketing |
| Lauf-Modi | `full`, `partial` | automatische Delta-Erkennung als eigener UI-Modus |
| CMDB-Modell | `Anwendung`, `Schnittstelle`, `Server`, `OrgEinheit` | tiefe Attributmodellierung |
| ArchiMate-Export | Vollstaendiger Graph als ArchiMate Exchange Format (ohne Views) | Views/Viewpoints, selektiver Export, Archi-natives Format |
| ArchiMate-Import-Mapping | Erweiterbar: beliebige AM-Typen koennen auf BRIDGR-Labels gemappt werden (m:1) | Neue BRIDGR-Labels aus ArchiMate-Typen |
| Export-Precheck | Nodes ohne archimate_type vor Export anzeigen und tippen | Automatische Typ-Ableitung ohne Benutzerbestaetigung |
| Deployment | Lokal / Docker | Cloud-Deployment |
| Rollen-Modell | Lanes als `:Rolle` mit `BETEILIGT_AN`; `KANN_EINNEHMEN` als kuratierbarer Link | automatische OrgEinheit-Ableitung aus Lanes |

---

## 5. Domaenenmodell

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

### Rolle

Eine `Rolle` repraesentiert einen Prozessteilnehmer auf Prozessebene — typischerweise aus
einer BPMN-Lane abgeleitet. Sie ist bewusst von `OrgEinheit` getrennt: Beteiligung an
einem Prozess impliziert keine Eigentuemer- oder Verantwortungsbeziehung.

Rollen werden immer aus Prozessquellen extrahiert; sie entstehen nie aus CMDB-Daten.

### OrgEinheit

Eine `OrgEinheit` ist ein reales organisatorisches Objekt (Abteilung, Team, Bereich).
Sie entsteht entweder:
- durch explizite Pflege in Tab 4, oder
- durch Bestaetigung eines CMDB-Owner-Kandidaten.

OrgEinheiten aus Prozessquellen entstehen nicht mehr automatisch. Stattdessen werden
alle Lanes als Rollen extrahiert; der Benutzer ordnet Rollen in Tab 4 einer OrgEinheit zu.

### Verantwortung

`VERANTWORTET` verbindet eine `OrgEinheit` mit dem Objekt, fuer das sie verantwortlich ist.
Die Beziehung wird nur gesetzt wenn:
- ein CMDB-Owner-String exakt einer bekannten OrgEinheit entspricht, oder
- der Benutzer die Zuordnung in Tab 4 manuell bestaetigt (CMDB-Kandidaten-Flow).

`VERANTWORTET` wird nicht aus Prozessextraktion abgeleitet. Lane-Beteiligung ist kein
Ownership-Nachweis.

### Rollenzuordnung

`KANN_EINNEHMEN` verbindet eine `OrgEinheit` mit einer `Rolle`. Die Beziehung drueckt aus:
"Diese Organisationseinheit besetzt diese Prozessrolle." Sie entsteht ausschliesslich durch
Benutzerbestaetigung in Tab 4 und wird nie automatisch geschrieben.

### Neue Properties aus ArchiMate-Import

ArchiMate-importierte Knoten erhalten drei zusaetzliche Properties:

| Property | Typ | Bedeutung |
|---|---|---|
| `archimate_id` | String | Interner Identifier aus dem ArchiMate-Modell (`identifier`-Attribut im XML) |
| `archimate_source` | String | Dateiname der Quelldatei |
| `archimate_type` | String | Originaler ArchiMate-Elementtyp beim Import (z.B. `"BusinessProcess"`) |

Diese Properties werden auch gesetzt, wenn ein ArchiMate-Element mit einem bestehenden
BRIDGR-Knoten gemergt wird. Die BRIDGR-native Identitaet (`process_id`, `cmdb_id` etc.)
bleibt primaer — `archimate_id` ist ein ergaenzender Identifier.

Bei einem Re-Import derselben ArchiMate-Datei wird `archimate_id` fuer den deterministischen
Lookup verwendet (Prio 1), bevor Namens-Matching greift.

ArchiMate-importierte Relationen erhalten eine zusaetzliche Property:

| Property | Typ | Bedeutung |
|---|---|---|
| `archimate_rel_type` | String | Originaler ArchiMate-Beziehungstyp beim Import (z.B. `"FlowRelationship"`) |

Diese Property wird fuer den Roundtrip-Export verwendet (siehe Abschnitt 13.3).

---

## 6. Anwendungsschichten

```text
bridgr/
├── core/                                # shared foundations (config, Neo4j, LLM, schema)
├── processing/                          # pipeline, import, KB, CMDB, query layer
├── prompts/
├── skills/
├── services/
│   ├── import_service.py
│   ├── cmdb_service.py
│   ├── archimate_import_service.py      (v0.21)
│   ├── archimate_export_service.py      (v0.21; erweitert v0.22)
│   ├── organization_service.py
│   ├── alias_service.py
│   ├── query_service.py
│   ├── review_service.py
│   └── runtime_service.py
├── ui/
│   ├── config_tab.py
│   ├── organization_tab.py
│   ├── query_tab.py
│   ├── review_tab.py
│   └── archimate_tab.py                 (v0.21; erweitert v0.22)
├── knowledge_base/
├── Input/
├── Output/
├── data/
│   └── archimate_mapping.json
├── scripts/                             # Wartungsskripte
├── config.json
├── app.py
└── main.py
```

`query_service.py` kapselt Tool-Ausfuehrung und System-Prompt-Zusammenstellung;
keine Gesprächszustandslogik ausserhalb der Gesprächshistorie.

Die beiden ArchiMate-Services lesen `archimate_mapping.json` als gemeinsame
Wissensquelle. Kein Mapping-Wissen im Code. `cmdb_service.py` dient als Referenzmuster.

---

## 7. Importlogik

Zwei Importmodi fuer Prozessdateien:
- `full`: gesamter Prozessdateibestand aus `Input/`
- `partial`: vom Benutzer explizit ausgewaehlte Dateien

ArchiMate-Import und CMDB-Import laufen unabhaengig von diesen Modi;
sie werden separat ueber Tab 5 ausgeloest.

Ein expliziter CMDB-Sync schreibt nicht nur CMDB-Entitaeten, Relationen und
Owner-Ableitungen nach Neo4j, sondern bewertet auch die Review-Artefakte des
letzten gespeicherten Laufs gegen den aktuellen CMDB-Stand neu. Dadurch koennen
zuvor offene oder schwache Anwendungszuordnungen ohne erneuten Prozessimport
automatisch entfallen, sobald die aktualisierte CMDB einen starken Match liefert.

---

## 8. Matching und Review

Reihenfolge: Knowledge Base -> Fuzzy Matching -> optionaler LLM-Fallback.

Schwache Kandidaten bleiben reviewbar, sofern fuer dieselbe Prozessanwendung kein starker Match existiert. Gibt es bereits einen starken Match (Konfidenz "stark", cmdb_id gesetzt), wird der schwache Kandidat automatisch unterdrückt und erscheint nicht im Review-Tab.

Diese Unterdrueckungsregel gilt auch fuer eine nachtraegliche CMDB-Synchronisation:
Wenn ein zuvor offener oder schwacher Fall im letzten gespeicherten Lauf durch die
aktualisierte CMDB nun einen starken Match mit `cmdb_id` erhaelt, wird der
Review-Fall bei der Neubewertung entfernt.

Beim Fuzzy Matching werden CMDB-Eintraege nach `entity_type` gewichtet: Eintraege vom Typ `application` erhalten einen Bonus (+0.05), Eintraege vom Typ `interface` einen Abzug (-0.05) auf den berechneten Score. Damit werden Anwendungen gegenueber Schnittstellen bevorzugt, was dem mentalen Modell der Anwender entspricht.

Der ArchiMate-Import nutzt denselben Fuzzy-Matching-Mechanismus. Der Schwellwert
ist separat in `archimate_mapping.json` konfigurierbar (initialer Wert entspricht
dem allgemeinen Fuzzy-Threshold aus `config.json`).

---

## 9. Graph Writer

### 9.1 Vollstaendiges Schreibmodell

```cypher
(:Prozess)
(:Anwendung)
(:Schnittstelle)
(:Server)
(:OrgEinheit)
(:Rolle)
(:Alias)

(:Rolle)-[:BETEILIGT_AN]->(:Prozess)
(:OrgEinheit)-[:KANN_EINNEHMEN]->(:Rolle)
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

`(:OrgEinheit)-[:VERANTWORTET]->(:Prozess)` existiert nicht mehr. Prozessperspektive
wird ausschliesslich ueber `BETEILIGT_AN` und `KANN_EINNEHMEN` abgebildet.

### 9.2 Schreibregeln pro Quelle

| Quelle | Erzeugt |
|---|---|
| BPMN-Extraktion (Lanes) | `(:Rolle)-[:BETEILIGT_AN]->(:Prozess)` |
| Unstrukturierter Text (Rolle-Feld) | `(:Rolle)-[:BETEILIGT_AN]->(:Prozess)` |
| Unstrukturierter Text (prozess_eigentuemer-Feld, explizit) | Kandidat → Review in Tab 4 |
| Tab 4 (Prozess-Owner-Zuweisung) | `(:OrgEinheit)-[:VERANTWORTET]->(:Prozess)` |
| Tab 4 (Rollenzuordnung) | `(:OrgEinheit)-[:KANN_EINNEHMEN]->(:Rolle)` |
| CMDB (exakter Owner-Match) | `(:OrgEinheit)-[:VERANTWORTET]->(Anwendung\|Schnittstelle\|Server)` |
| Tab 4 (CMDB-Kandidaten-Bestaetigung) | `(:OrgEinheit)-[:VERANTWORTET]->(Anwendung\|Schnittstelle\|Server)` |
| ArchiMate-Import (exakter Namens-Match) | MERGE auf bestehendem Knoten; `archimate_id`, `archimate_source`, `archimate_type` werden gesetzt |
| ArchiMate-Import (kein Match) | Neuer Knoten mit `archimate_id`, `archimate_source`, `archimate_type` |
| Tab 5 (ArchiMate-Kandidaten-Bestaetigung) | MERGE + `archimate_id`-Zuweisung auf bestehendem Knoten |
| Tab 5 (Export-Precheck-Bestaetigung) | `SET n.archimate_type` — ausschliesslich dieses eine Attribut; keine anderen Properties werden angefasst |

### 9.3 Idempotenz

- `BETEILIGT_AN`-Kanten werden bei jedem Reimport geloescht und neu geschrieben.
- `KANN_EINNEHMEN`-Kanten sind kuratierten Ursprungs und werden nicht bei Reimport
  geloescht. Sie bleiben erhalten bis der Benutzer sie explizit entfernt.
- ArchiMate-Import ist idempotent: bei Wiederholung wird der bestehende Knoten via
  `archimate_id` gefunden und angereichert, nicht dupliziert.

### 9.4 Kardinalitaet Prozess-Owner

Pro Prozess gibt es 0 oder 1 `VERANTWORTET`-Kante von einer OrgEinheit. Beim Schreiben
wird eine eventuell vorhandene Kante zuerst geloescht, dann die neue gesetzt. Die
Datenbank erzwingt diese Regel nicht; die Anwendung ist verantwortlich fuer die Einhaltung.

### 9.5 Attribut-Eigentuemer-Prinzip

Jede Importquelle ist Eigentuemer ihrer eigenen Attribute. Ein Update durch Quelle X
setzt ausschliesslich die Attribute, die zu Quelle X gehoeren. Andere Attribute
bleiben unveraendert.

Beispiele:
- ArchiMate-Import setzt `archimate_id`, `archimate_source`, `archimate_type` —
  nicht `name`, `process_id`, `cmdb_id` oder andere BRIDGR-native Attribute.
- Export-Precheck-Bestaetigung setzt `archimate_type` — keine anderen Attribute.
- CMDB-Import setzt CMDB-spezifische Properties — nicht ArchiMate-Properties.

Dieses Prinzip gilt fuer alle Import-Services und wird bei jeder neuen Schreiboperation
als Constraint beruecksichtigt.

---

## 10. Abfrage-Layer

### 10.1 Visionsziel

Tab "Kommunikation" ist ein vollwertiger EA-Chatbot. Der Benutzer muss keine besondere
Abfragesyntax kennen. Folgefragen, Rueckfragen, Praezisierungen und Kontextwechsel werden
nativ als Gespraech behandelt.

### 10.2 Architekturprinzip: LLM als Orchestrator

Der LLM treibt die Konversation. Code stellt Werkzeuge bereit, die der LLM aufruft.

```
Benutzereingabe
   |
   v
LLM (Orchestrator)
   ├── Tool: execute_cypher(query) ──> Neo4j ──> Ergebnis-Rows
   │      (wiederholbar pro Turn)
   └── Antwort in natuerlicher Sprache
```

Der LLM entscheidet eigenstaendig:
- ob und welche Cypher-Query zur Beantwortung benoetigt wird
- ob mehrere Queries nacheinander noetig sind
- ob eine Rueckfrage an den Benutzer sinnvoller ist als eine Query
- wie er Mehrdeutigkeiten im Kontext der Gesprächshistorie aufloest

Imperativische Gesprächszustandsverwaltung entfaellt aus dem Code. Der LLM traegt
diesen Kontext nativ.

### 10.3 Tool: execute_cypher

Das primaere (und zunaechst einzige) Tool.

Signatur:

```
execute_cypher(query: str) -> {rows: list[dict], error: str | null}
```

Verhalten:
- der Code validiert die Query vor Ausfuehrung (read-only, Schema-konform)
- bei Validierungsfehler wird der Fehler als Tool-Fehlerantwort zurueckgegeben;
  der LLM kann die Query korrigieren und erneut aufrufen
- bei leerem Ergebnis wird serverseitig deterministisch nach Alias-Treffern gesucht;
  vorhandene Aliase werden im Tool-Ergebnis als Hinweis mitgegeben
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

Auf jede Aenderung am Neo4j-Schreibmodell (Labels, Beziehungstypen, Richtungen,
abfragbare Properties) muss `graph_schema.py` im gleichen Schritt aktualisiert werden.

### 10.5 Konversationshistorie

Die vollstaendige Gesprächshistorie wird bei jedem LLM-Aufruf mitgegeben. Dadurch traegt
der LLM nativ Folgefragenkontexte, Disambiguierungszustand und Topikfokus.

Die Historientiefe wird durch ein konfigurierbares Maximum begrenzt. Aeltere Nachrichten
werden abgeschnitten, nicht zusammengefasst.

### 10.6 Dual-Mode-Betrieb

**Tool-Use-Modus** (Standard fuer faehige Backends):
- LLM erhaelt das Tool als formales Function-Calling-Schema
- LLM kann `execute_cypher` mehrfach pro Turn aufrufen

**Prompt-Only-Modus** (Fallback fuer lokale Modelle ohne Tool-Support):
- LLM gibt Cypher in einem definierten Format im Text aus (```cypher-Block)
- Code extrahiert, validiert, fuehrt aus und gibt das Ergebnis als naechste Nachricht
  in der History zurueck

Beide Modi teilen denselben System-Prompt und dieselbe Validierungslogik.
Umschaltbar per `chat_mode` in `config.json`.

---

## 11. Organisation-Tab (Tab 4)

### 11.1 Bestehender Flow: OrgEinheiten und CMDB-Kandidaten

Tab 4 zeigt alle bekannten OrgEinheiten. Fuer jede OrgEinheit koennen CMDB-Owner-Kandidaten
bestaetigt oder abgelehnt werden. Bestaetigung erzeugt `VERANTWORTET`-Kanten.

### 11.2 Flow: Prozess-Owner-Pflege

Jede OrgEinheit-Card zeigt einen Button "Prozesse verwalten". Dahinter erscheint eine
Multiselect-Liste aller Prozesse im Graphen. Bereits dieser OE zugewiesene Prozesse sind
vorselektiert. Prozesse mit einem anderen Eigentuemer werden mit einem Hinweis markiert
("→ [andere OE]"); eine Auswahl ersetzt den bisherigen Eigentuemer (1-Owner-Constraint).

Zusaetzlich gibt es einen Abschnitt "Prozesse ohne Eigentuemer" mit allen Prozessen ohne
`VERANTWORTET`-Kante. Dort kann direkt eine OE zugewiesen werden.

Extrahierte `prozess_eigentuemer`-Kandidaten aus unstrukturierten Texten erscheinen als
Vorschlaege im Kandidaten-Abschnitt und erfordern Benutzerbestaetigung.

### 11.3 Flow: Rollenzuordnung

Tab 4 zeigt alle `:Rolle`-Knoten aus Neo4j, die noch keine `KANN_EINNEHMEN`-Kante zu
einer OrgEinheit haben:

```cypher
MATCH (r:Rolle)-[:BETEILIGT_AN]->(p:Prozess)
WHERE NOT (:OrgEinheit)-[:KANN_EINNEHMEN]->(r)
RETURN r.name AS rolle, collect(p.name) AS prozesse
ORDER BY r.name
```

Fuer jede nicht zugeordnete Rolle kann der Benutzer:
- eine bestehende OrgEinheit auswaehlen und zuordnen → erzeugt `KANN_EINNEHMEN`
- eine neue OrgEinheit anlegen und sofort zuordnen → erzeugt OrgEinheit + `KANN_EINNEHMEN`
- die Rolle ohne Zuordnung belassen (kein Pflichtfeld)

`KANN_EINNEHMEN` wird in Neo4j geschrieben; kein Schreiben in kb.json.

---

## 12. Konfiguration

### config.json (Laufzeit-Konfiguration)

Tab 3 verwaltet:

- Input-Pfad
- aktive CMDB-Datei
- Output-Pfad
- LLM-Endpoint, Modell und API-Key-Umgebungsvariable
- Neo4j-Zugangsdaten
- Fuzzy-Threshold
- Importmodus
- Chat-Modus: `tool-use` oder `prompt-only` (mit Hinweis auf Backend-Anforderungen)
- Wissensbasis-Reset: gesamte KB leeren, nur Bestaetigungen leeren oder nur Ablehnungen
  leeren (inkl. konsistenter Alias-Synchronisation nach Neo4j)

### archimate_mapping.json (ArchiMate-Mapping-Konfiguration)

Eigenstaendige Konfigurationsdatei neben `config.json`. Enthaelt ausschliesslich
ArchiMate-bezogenes Mapping-Wissen — kein Laufzeit-Konfigurationswert.

Wird beim ersten Start mit Standard-Defaults angelegt.
Wird von `archimate_import_service.py` und `archimate_export_service.py` gelesen.
Wird durch Tab 5 (EA-Modell) bearbeitet.

Struktur: siehe Abschnitt 13.4.

---

## 13. ArchiMate-Integration

### 13.1 Services und Verantwortlichkeiten

Zwei Services; kein Mapping-Wissen im Code:

| Service | Verantwortung |
|---|---|
| `services/archimate_import_service.py` | XML parsen, Typ-Mapping anwenden, Identity Resolution, Neo4j schreiben |
| `services/archimate_export_service.py` | Neo4j lesen, Typ-Mapping anwenden, ArchiMate-XML erzeugen, Precheck-Abfrage, Typ-Schreiben fuer Precheck-Bestaetigung |

Beide Services lesen `archimate_mapping.json` als gemeinsame Wissensquelle.
`cmdb_service.py` dient als Referenzmuster fuer Servicestruktur und Fehlerbehandlung.

### 13.2 Import-Pipeline

```
Input/*.xml  oder  Input/*.archimate
  |
  v
XML-Parser
  Liest <elements> + <relationships> aus dem ArchiMate Exchange Format
  Extrahiert je Element: {identifier, xsi:type, name(n)}
  Extrahiert je Relation: {identifier, xsi:type, source, target}
  |
  v
Namenswahl (Mehrsprachigkeit)
  Sucht <name xml:lang="de"> oder <name xml:lang="german"> (beide gelten als Deutsch)
  Fallback: naechste Sprache in language_preference-Liste
  Letzter Fallback: erstes verfuegbares <name>-Element
  Ohne xml:lang-Attribut: Name direkt uebernehmen
  |
  v
Element-Mapping (aus archimate_mapping.json, elements.import)
  xsi:type in Mapping? → bridgr_label zuweisen
  xsi:type nicht in Mapping? → ueberspringen, im Log festhalten (Typ + Anzahl)

  Hinweis Mapping-Kardinalitaet: mehrere ArchiMate-Typen koennen auf dasselbe
  BRIDGR-Label zeigen (m:1). Jeder Eintrag hat genau ein BRIDGR-Label (kein Mehrdeutigkeits-
  spielraum zur Laufzeit), aber zwei Eintraege koennen dieselbe Seite haben.
  Beispiel: ApplicationProcess -> Prozess, BusinessProcess -> Prozess.
  |
  v
Identity Resolution (je aufgeloestem Element)
  1. archimate_id bekannt? (Re-Import) → direkter Property-Lookup (deterministisch)
  2. Exakter Namensabgleich gegen Neo4j-Knoten (gleicher bridgr_label) → MERGE
  3. Fuzzy Match >= fuzzy_match_threshold → Kandidat in Review-Queue (Tab 5)
  4. Kein Match → neuer Knoten anlegen
  |
  v
Beziehungs-Mapping (aus archimate_mapping.json, relationships.import)
  Beide Endpoints aufgeloest?
    xsi:type in akzeptierter Liste fuer dieses Label-Paar? → BRIDGR-Relation erstellen
    xsi:type nicht in Liste? → ueberspringen, im Log festhalten
  Mindestens ein Endpoint unaufgeloest?
    → ueberspringen, im Log festhalten
    v1-Einschraenkung: nach Review-Bestaetigung werden Beziehungen nicht automatisch
    nachgezogen; ein Re-Import der ArchiMate-Datei ist erforderlich
  |
  v
Neo4j-Writer
  MERGE auf (name, label) fuer exakte Matches
  SET archimate_id, archimate_source, archimate_type an Knoten (Attribut-Eigentuemer-Prinzip)
  SET r.archimate_rel_type an Relationen
```

### 13.3 Export-Pipeline

Export-Scope: immer vollstaendiger Graph. Solange keine Views/Viewpoints unterstuetzt
werden, gibt es keinen sinnvollen Teilexport. Der Export bildet alle BRIDGR-Knoten und
-Relationen ab, unabhaengig von ihrer Herkunft (BPMN, CMDB oder ArchiMate).

```
[Optional] Export-Precheck (Tab 5, vor dem Export)
  Neo4j: alle Knoten ohne archimate_type-Property abfragen (nur Labels aus _EXPORT_LABELS)
  Knoten ohne konfigurierten Export-Typ: ignorieren (wuerden im Export ohnedies uebersprungen)
  Knoten mit konfiguriertem Export-Typ aber ohne archimate_type:
    → in Tab 5 anzeigen (nach Label gruppiert: Anzahl + vorgeschlagener Typ)
    → Benutzer kann vorgeschlagene Typen per Gruppe akzeptieren oder pro Node ueberschreiben
    → Bestaetigung schreibt archimate_type via SET n.archimate_type (Attribut-Eigentuemer-Prinzip)
  Wenn keine Nodes ohne archimate_type vorhanden: Export startet ohne Precheck
  |
  v
Neo4j (alle Knoten + alle Relationen lesen)
  |
  v
Element-Mapping (aus archimate_mapping.json, elements.export)
  archimate_type-Property vorhanden? → Original-Typ verwenden (Roundtrip-Erhalt)
  Sonst: konfigurierter Export-Typ fuer dieses BRIDGR-Label
  Kein Export-Typ konfiguriert? → Knoten ueberspringen
  |
  v
Beziehungs-Mapping (aus archimate_mapping.json, relationships.export)
  archimate_rel_type-Property vorhanden? → Original-Typ verwenden (Roundtrip-Erhalt)
  Sonst: konfigurierter kanonischer Typ fuer dieses Label-Paar
  |
  v
ArchiMate-XML-Generator
  Erzeugt valides ArchiMate Exchange Format 3.x
  <elements> + <relationships> + <organizations>
  Kein <views>/<viewpoints>-Block (v1)
  |
  v
Output/archimate_export_<timestamp>.xml
```

Roundtrip-Konsistenz: ein ArchiMate-Modell, das importiert und dann exportiert wird,
erhaelt alle originalen ArchiMate-Typen unveraendert — unabhaengig von der aktuellen
Mapping-Konfiguration. Knoten und Relationen ohne ArchiMate-Herkunft erhalten den
konfigurierten kanonischen Typ (ggf. nach Export-Precheck kuratiert).

### 13.4 archimate_mapping.json — Struktur

```json
{
  "language_preference": ["de", "german", "en", "english"],
  "fuzzy_match_threshold": 0.85,
  "elements": {
    "import": {
      "BusinessProcess":      "Prozess",
      "ApplicationComponent": "Anwendung",
      "ApplicationInterface": "Schnittstelle",
      "Node":                 "Server",
      "BusinessActor":        "OrgEinheit",
      "BusinessRole":         "Rolle"
    },
    "export": {
      "Prozess":       "BusinessProcess",
      "Anwendung":     "ApplicationComponent",
      "Schnittstelle": "ApplicationInterface",
      "Server":        "Node",
      "OrgEinheit":    "BusinessActor",
      "Rolle":         "BusinessRole"
    }
  },
  "relationships": {
    "import": {
      "Anwendung->Prozess":        ["Serving", "Realization"],
      "Rolle->Prozess":            ["Assignment"],
      "OrgEinheit->Rolle":         ["Assignment"],
      "Prozess->Prozess":          ["Triggering", "Flow"],
      "Anwendung->Schnittstelle":  ["Composition", "Aggregation"],
      "Anwendung->Server":         ["Realization", "Assignment"],
      "Schnittstelle->Server":     ["Realization"],
      "OrgEinheit->Anwendung":     ["Association", "Assignment"],
      "OrgEinheit->Schnittstelle": ["Association"],
      "OrgEinheit->Server":        ["Association"]
    },
    "export": {
      "Anwendung->Prozess":        "Serving",
      "Rolle->Prozess":            "Assignment",
      "OrgEinheit->Rolle":         "Assignment",
      "Prozess->Prozess":          "Triggering",
      "Anwendung->Schnittstelle":  "Composition",
      "Anwendung->Server":         "Realization",
      "Schnittstelle->Server":     "Realization",
      "OrgEinheit->Anwendung":     "Association",
      "OrgEinheit->Schnittstelle": "Association",
      "OrgEinheit->Server":        "Association"
    }
  }
}
```

Mapping-Kardinalitaet:
- `elements.import`: m:1 — mehrere ArchiMate-Typen koennen auf dasselbe BRIDGR-Label zeigen;
  jeder einzelne Eintrag bleibt eindeutig (1 AM-Typ → 1 BRIDGR-Label)
- `elements.export`: m:1 erlaubt — mehrere BRIDGR-Labels koennen denselben ArchiMate-Typ ergeben
- `relationships.import`: m:1 — Liste akzeptierter ArchiMate-Typen pro Label-Paar
- `relationships.export`: 1:1 — ein kanonischer ArchiMate-Typ pro Label-Paar

### 13.5 EA-Modell-Tab (Tab 5)

Zentraler ArchiMate-Arbeitsbereich.

**Bereich 1 — Import-Mapping konfigurieren**

Liste aller konfigurierten Import-Eintraege (eine Zeile pro ArchiMate-Typ):
- Spalte "ArchiMate-Typ": welcher AM-Typ (Dropdown aus ARCHIMATE_ELEMENT_TYPES)
- Spalte "BRIDGR-Label": auf welches Label er abgebildet wird (Dropdown aus BRIDGR_LABELS)
- Loeschen-Button pro Zeile
- "+ Mapping hinzufuegen"-Button fuer neue Eintraege
- Mehrere Eintraege koennen auf dasselbe BRIDGR-Label zeigen (m:1 explizit erlaubt)

**Bereich 2 — Export-Mapping konfigurieren**

Tabelle (eine Zeile pro BRIDGR-Label):
- Spalte "Export": welcher ArchiMate-Typ beim Export erzeugt wird (Dropdown), falls kein
  `archimate_type`-Property auf dem Knoten gesetzt ist

[ Mapping speichern ] schreibt in `archimate_mapping.json`.

**Bereich 3 — Beziehungs-Mapping konfigurieren (optional)**

Tabelle (eine Zeile pro Label-Paar aus graph_schema.py):
- Spalte "Import akzeptiert": mehrere ArchiMate-Beziehungstypen (Multiselect)
- Spalte "Export kanonisch": ein ArchiMate-Typ (Dropdown)

Bereich standardmaessig eingeklappt (checkbox), da er selten geaendert wird.

**Bereich 4 — Import**

Datei-Upload + Import-Button. Ergebnis-Anzeige (importiert / Kandidaten / uebersprungen).
Uebersprungene AM-Typen werden mit Anzahl aufgelistet.

**Bereich 5 — Export**

```
[ Als ArchiMate exportieren ]
```

Klick auf den Button:
- Wenn alle Nodes einen `archimate_type` haben: direkt exportieren
- Wenn Nodes ohne `archimate_type` vorhanden sind (Precheck):
  → Precheck-Ansicht erscheint (siehe 13.6)

**Precheck-Ansicht:**

```
14 Nodes ohne ArchiMate-Typ gefunden.

Prozess (8 Nodes) — Standard: BusinessProcess
  [Details einblenden]
    Posteingang          → [BusinessProcess ▼]
    Bestellabwicklung    → [BusinessProcess ▼]
    ...

Anwendung (6 Nodes) — Standard: ApplicationComponent
  [Details einblenden]
    SAP SD               → [ApplicationComponent ▼]
    ...

[ Vorschlaege uebernehmen und exportieren ]   [ Abbrechen ]
```

Einzelne Nodes sind im "Details"-Expander individuell ueberschreibbar.
"Vorschlaege uebernehmen" schreibt `archimate_type` per `SET n.archimate_type` (nur dieses Attribut)
und startet dann den Export.

### 13.6 Bekannte Einschraenkungen (v0.22)

**Realization-Richtung bei RUNS_ON:**

BRIDGR exportiert `RUNS_ON`-Kanten als `Realization` in der Richtung
`Anwendung → Server` (bzw. `Schnittstelle → Server`). In ArchiMate's formalem
Metamodell gilt fuer Deployment-Beziehungen die umgekehrte Richtung:
`Node → ApplicationComponent` (der Node realisiert den Deployment-Kontext der Anwendung).

Konsequenz: Tools mit strenger Metamodell-Validierung (z.B. MID Innovator) korrigieren
die Richtung beim Import automatisch. Das importierte Modell ist inhaltlich korrekt,
aber die Pfeilrichtung entspricht nicht dem ArchiMate-Standard.

Behebung: Im Export-Service die Source- und Target-Felder fuer `RUNS_ON`-Kanten
tauschen (Server als Source, Anwendung/Schnittstelle als Target).
Noch nicht umgesetzt, da der Import trotz Richtungskorrektur funktioniert und
die Semantik erhalten bleibt.

**Export-Precheck und neue BRIDGR-Nodes nach dem Precheck:**

Der Precheck zeigt den Zustand zum Zeitpunkt des Klicks. Werden zwischen Precheck und
Export-Bestaetigung neue Nodes ohne `archimate_type` geschrieben (unwahrscheinlich,
aber moeglich), landen diese ohne Precheck-Kuration im Export — mit dem konfigurierten
kanonischen Typ.

---

## 14. Akzeptanzkriterien

1. Korrekte Informationen aus den Quelldaten koennen ueber die Weboberflaeche abgefragt werden
2. Mappings sind ueber die Weboberflaeche pflegbar
3. Informationen zu Prozessen, Anwendungen, Schnittstellen und Servern koennen ueber die
   Weboberflaeche abgerufen werden
4. Die Pipeline laeuft stabil durch einen vollstaendigen Importzyklus
5. Der Ausbau auf TXT, DOCX und PDF folgt demselben gemeinsamen semantischen Extraktionsschema
6. Grosse BPMN/XML-Dateien koennen ueber den Transformationspfad in prozessweise, stabile
   Importeinheiten ueberfuehrt werden
7. `Input/` bleibt nach einem erfolgreichen Lauf frei von verarbeiteten Prozessdateien
8. Verarbeitete Prozessdateien werden transparent in ein Archiv unter `data/input_archive/`
   verschoben
9. `app.py` enthaelt nur noch Entrypoint- und Verdrahtungslogik; Tab-Rendering und UI-nahe
   Orchestrierung liegen in getrennten Modulen
10. CMDB-Objekte werden nicht mehr pauschal als `Anwendung` in Neo4j geschrieben
11. Verantwortungsinformationen aus der CMDB werden als `VERANTWORTET` verarbeitet; bei
    unsicherer Org-Zuordnung als Kandidat, nicht als stiller Direktschreibvorgang
12. Prozessbeziehungen zu IT-Bausteinen werden als `(:Anwendung)-[:DIENT]->(:Prozess)`
    modelliert
13. Folgefragen, Praezisierungen und Kontextwechsel im Chat werden ohne imperativische
    Code-Zustandsverwaltung korrekt behandelt
14. Mehrdeutigkeiten werden vom LLM im Gesprächskontext aufgeloest, ohne dass dafuer ein
    separater Disambiguierungszustand im Code verwaltet werden muss
15. `query_service.py` kapselt Tool-Ausfuehrung und System-Prompt-Zusammenstellung;
    keine Gesprächszustandslogik ausserhalb der Gesprächshistorie
16. Unstrukturierte Dokumente mit explizitem `prozess_eigentuemer` erzeugen einen
    Kandidaten im Review-Flow
17. Alle BPMN-Lanes werden als `:Rolle`-Knoten extrahiert und mit `BETEILIGT_AN` mit dem
    Prozess verbunden
18. `(:OrgEinheit)-[:VERANTWORTET]->(:Prozess)` wird aus der Prozessextraktion nicht
    mehr geschrieben
19. Tab 4 zeigt nicht zugeordnete Rollen aus Neo4j und erlaubt die Erstellung von
    `KANN_EINNEHMEN`-Kanten
20. `KANN_EINNEHMEN`-Kanten ueberleben einen Reimport unveraendert
21. Der Chat-Layer kann Rollen, `BETEILIGT_AN` und `KANN_EINNEHMEN` abfragen
22. Pro Prozess existiert hoechstens eine `VERANTWORTET`-Kante von einer OrgEinheit;
    eine neue Zuweisung ersetzt die alte
23. Eine ArchiMate-Exchange-Format-3.x-Datei in `Input/` wird beim Import erkannt
    und verarbeitet
24. Elemente mit unbekanntem `xsi:type` werden uebersprungen; der Import-Log zeigt
    Typ und Anzahl der uebersprungenen Elemente
25. Bei exaktem Namens-Match wird der bestehende Neo4j-Knoten angereichert
    (`archimate_id`, `archimate_source`, `archimate_type`), nicht dupliziert
26. Fuzzy-Matches erzeugen Kandidaten, die in Tab 5 bestaetigt werden koennen
27. Ein wiederholter Import derselben Datei erzeugt keine Duplikate
    (Lookup via `archimate_id` vor Namens-Matching)
28. Beziehungen mit unaufgeloestem Endpoint werden uebersprungen und im Log
    festgehalten; der Nutzer wird auf Re-Import hingewiesen
29. Der Export erzeugt eine valide ArchiMate-Exchange-Format-3.x-Datei
30. Ein Import-Export-Roundtrip erhaelt alle originalen ArchiMate-Element- und
    Beziehungstypen unveraendert (`archimate_type`, `archimate_rel_type`)
31. BRIDGR-native Knoten (ohne `archimate_type`) erhalten beim Export den
    konfigurierten kanonischen Typ
32. Tab 5 zeigt Mapping-Konfiguration, Import-Aktion und Export-Aktion
    in einem zusammenhaengenden Arbeitsbereich
33. `archimate_mapping.json` wird beim ersten Start mit Defaults angelegt
34. Mehrere ArchiMate-Typen koennen im Import-Mapping auf dasselbe BRIDGR-Label
    zeigen (m:1); die UI zeigt eine Zeile pro AM-Typ (nicht eine Zeile pro BRIDGR-Label)
35. Import-Mapping-Eintraege koennen einzeln geloescht und neue hinzugefuegt werden
36. Vor dem Export werden Nodes ohne `archimate_type` identifiziert und dem Benutzer
    mit vorgeschlagenen Typen (aus dem Export-Mapping) zur Bestaetigung angezeigt
37. Die Export-Precheck-Bestaetigung schreibt ausschliesslich `archimate_type` pro Node;
    alle anderen Attribute bleiben unveraendert (Attribut-Eigentuemer-Prinzip)

---

## 15. Getroffene Entscheidungen

| Entscheidung | Gewaehlt | Verworfen | Begruendung |
|---|---|---|---|
| CMDB-Dateiformat | vorerst nur CSV | gleichzeitige Erweiterung auf mehrere Formate | zuerst muss das fachliche Modell stabilisiert werden, bevor Dateiformatbreite Mehrwert bringt |
| CMDB-Zielobjekte | `Anwendung`, `Schnittstelle`, `Server`, `OrgEinheit` | alles als `Anwendung` modellieren | das bisherige Modell verliert fachliche Unterschiede typischer CMDB-Inhalte |
| Attributtiefe | Minimalmodell mit `id`, `name`, bei `Server` zusaetzlich `server_type` | breites Attributset im ersten Schritt | die Funktionalitaet ist aktuell wichtiger als ein frueh ueberladenes Datenmodell |
| Server-Modell | ein Label `Server` mit Attribut `server_type` | getrennte Labels fuer physische und virtuelle Server | haelt das Modell im ersten Schritt einfach und ausreichend auswertbar |
| Ownership-Semantik | generische Beziehung `VERANTWORTET` | semantisch enges `BESITZT` | `VERANTWORTET` ist fachlich lesbarer und passt besser zu generischer Ownership |
| Quelle fuer `VERANTWORTET` | Prozessquellen und CMDB duerfen beide Verantwortungen liefern | Verantwortung nur aus Prozessquellen | in realen Modellen ist Ownership generisch und muss aus der CMDB abbildbar sein |
| Unsichere CMDB-Owner | Kandidatenlogik analog zur Org-Pruefung | unsichere Owner-Strings direkt schreiben | verhindert stilles Aufblaehen des Org-Modells durch Freitext aus der CMDB |
| Prozessanbindung | `(:Anwendung)-[:DIENT]->(:Prozess)` | `(:Prozess)-[:NUTZT]->(:Anwendung)` | naeher an ArchiMate und semantisch klarer fuer die Servicesicht |
| Kuratierte Alternativbegriffe | `(:Alias)-[:KANN_MEINEN]->(:OrgEinheit\|:Anwendung)` | freie LLM-Synonymerfindung | haelt alternative Namen nachvollziehbar, mehrdeutig modellierbar und deterministisch aufloesbar |
| Chat-Architektur | LLM als Orchestrator mit `execute_cypher` als Tool | deterministischer Code als Gesprächsmanager | Code-seitige Zustandsverwaltung wird mit wachsender Dialogvielfalt unwartbar |
| Dual-Mode | Tool-Use + Prompt-Only-Fallback | ausschliesslich Tool-Use | Bridgr soll mit lokalen Modellen ohne Function-Calling-Support betreibbar bleiben |
| Alias-Lookup | serverseitige Anreicherung des Tool-Ergebnisses | eigenes Tool oder LLM-freie Aufloesung | haelt die Alias-Semantik deterministisch, ohne dem LLM Inventionsraum zu geben |
| Historienlaenge | konfigurierbares Maximum, alte Nachrichten werden abgeschnitten | Zusammenfassung aelterer Turns | Zusammenfassungen koennen fachlich relevante Details verlieren |
| Scope deterministischer Matching-Code | bleibt fuer Import-Pipeline | auch fuer Chat-Disambiguierung | Import-Matching hat andere Anforderungen (Idempotenz, Auditierbarkeit) als Chat |
| Lane → Rolle statt OrgEinheit | Lanes erzeugen immer `:Rolle` | Lane direkt als OrgEinheit schreiben | Lane-Beteiligung impliziert kein Ownership; automatische Klassifikation waere unzuverlaessig |
| KANN_EINNEHMEN als kuratierbarer Link | nur durch Benutzeraktion in Tab 4 | automatisch bei Namensgleichheit | identische Namen koennen verschiedene Konzepte meinen |
| Rollenzuordnung graph-only | Neo4j-Abfrage fuer nicht zugeordnete Rollen | kb.json-Kandidatenmechanismus | Neo4j ist robuster gegen Dateimanipulation; aligned mit kb.json-Abloesung |
| ArchiMate als ergaenzende Quelle | Ergaenzung zu BPMN/CMDB | Ersatz fuer bestehende Quellen | Nutzer haben oft beides; Ergaenzung vermeidet Informationsverlust |
| Mapping-Wissen extern | `archimate_mapping.json` | Konstanten im Code | Organisations-spezifisches Wissen gehoert nicht in den Code; analog zu "Prompts over code" |
| Zwei getrennte Services | `archimate_import_service.py` + `archimate_export_service.py` | ein gemeinsamer Service | analog zu `cmdb_service.py`; Import und Export haben unterschiedliche Datenfluss-Richtungen |
| Element-Import m:1, Export m:1 | Import m:1 (mehrere AM-Typen → ein BRIDGR-Label), Export flexibel | Import strikt 1:1 | Erweiterbarkeit des Imports ohne Graphmodell-Erweiterung; UI zeigt Zeilen pro AM-Typ, nicht pro BRIDGR-Label |
| Beziehungs-Import m:1, Export 1:1 | mehrere AM-Typen → eine BRIDGR-Relation; ein kanonischer AM-Typ pro Export | beides 1:1 | Organisationen verwenden verschiedene AM-Beziehungstypen fuer dieselbe Semantik |
| Roundtrip via Original-Typ-Properties | `archimate_type` + `archimate_rel_type` | kein Roundtrip-Erhalt | Modelle die importiert, bearbeitet und re-exportiert werden, sollen typgetreu bleiben |
| Primaere Identitaet unveraendert | BRIDGR-native ID bleibt primaer; `archimate_id` ergaenzend | `archimate_id` als neue primaere ID | bestehende Identitaetslogik bleibt stabil; Re-Import nutzt `archimate_id` deterministisch |
| Uebersprungene Beziehungen — kein Auto-Nachzug | Re-Import nach Review erforderlich | automatischer Nachzug | Auto-Nachzug erfordert persistente Pending-Queue; fuer v1 zu aufwaendig |
| Export-Scope vollstaendig | immer gesamter Graph | selektiver Export | ohne Views/Viewpoints gibt es keine sinnvolle Selektion |
| Tab-Name "EA-Modell" | "EA-Modell" | "ArchiMate", "Mapping" | neutral, nicht tool-spezifisch |
| Export-Precheck: Persistenz als archimate_type | Bestaetigung schreibt `archimate_type` in Neo4j | transiente Session-Overrides ohne Persistenz | einmal kuratiert greift der Roundtrip-Mechanismus; naechster Export laeuft ohne Precheck fuer diese Nodes |
| Attribut-Eigentuemer-Prinzip | jede Quelle schreibt nur ihre eigenen Attribute | vollstaendiger Node-Ueberschrieb durch letzten Importer | single-source-of-truth ist auf Attributebene, nicht auf Node-Ebene |
| Import-Mapping UI: Zeilen pro AM-Typ | eine Zeile pro AM-Typ mit Loeschen-Button | eine Zeile pro BRIDGR-Label mit Inversion | Inversion verliert m:1-Eintraege; Zeilen-pro-AM-Typ ist der natuerlicere Darstellungsrahmen |

---

## 16. UML-Diagramme

### 16.1 Komponentendiagramm

Zeigt die statische Gliederung aller Systemkomponenten in Schichten (Präsentation, Services, Pipeline, Infrastruktur) sowie ihre Abhängigkeiten untereinander und zu externen Systemen (Neo4j, LLM, Filesystem).

![BRIDGR Komponentendiagramm](BRIDGR_Komponentendiagramm.png)

Quelle: [uml_component_diagram.puml](uml_component_diagram.puml)

---

### 16.2 Klassenmodell

Zeigt alle Klassen mit Attributen und Methoden, gegliedert nach den Packages Konfiguration, CMDB-Datenmodell, Wissensbasis, Extraktion & Verarbeitung, Matching & Review, Pipeline & Artefakte, Infrastruktur, Fehlerbehandlung, Services, ArchiMate-Integration und UI-Komponenten.

![BRIDGR Klassenmodell](BRIDGR_Klassenmodell.png)

Quelle: [uml_class_model.puml](uml_class_model.puml)

---

### 16.3 Sequenzdiagramme

#### Sequenz 1 – Dokument-Import-Pipeline

Vollständiger Ablauf vom Import-Start durch die Pipeline über Extraktion, Matching und Graph-Schreiben bis zur Archivierung verarbeiteter Dateien (vgl. Abschnitte 7 und 8).

![Sequenz 1: Dokument-Import-Pipeline](BRIDGR_Sequenzdiagramme.png)

#### Sequenz 2 – Natürlichsprachige Graph-Abfrage

Konversationsfluss im Query-Tab für beide Betriebsmodi (`tool-use` und `prompt-only`) inkl. Alias-Lookup und Cypher-Fehlerkorrektur (vgl. Abschnitt 10).

![Sequenz 2: Graph-Abfrage](BRIDGR_Sequenzdiagramme_001.png)

#### Sequenz 3 – CMDB-Synchronisation

Ablauf des CMDB-Sync vom CSV-Laden über Owner-Auflösung, Graph-Schreiben, Neubewertung des letzten gespeicherten Laufs bis zur Alias-Synchronisation (vgl. Abschnitte 7 und 8).

![Sequenz 3: CMDB-Synchronisation](BRIDGR_Sequenzdiagramme_002.png)

#### Sequenz 4 – Review: Anwendungslink bestätigen / ablehnen

Drei Pfade im Review-Tab: Bestätigen, Ablehnen und manuelle Verknüpfung eines Anwendungslinks inkl. Schreiben in KnowledgeBase und Neo4j (vgl. Abschnitt 8).

![Sequenz 4: Review](BRIDGR_Sequenzdiagramme_003.png)

Quelle aller Sequenzdiagramme: [uml_sequence_diagram.puml](uml_sequence_diagram.puml)

---

*Bridgr | Architektur v0.22 | Stand Juni 2026*

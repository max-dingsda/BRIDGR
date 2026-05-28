# Bridgr
**Import- und Review-Zielarchitektur** | Stand: Mai 2026 | v0.15

---

## 1. Ziel

Prozessdokumentation und CMDB-Export zusammenfuehren, um einen EA-Wissensgraphen aufzubauen und ihn ueber eine natuerlichsprachliche Web-Oberflaeche abfragbar zu machen.

Kernfrage:
Welche IT-Anwendungen unterstuetzen welche Geschaeftsprozesse und wie sicher wissen wir das?

Bridgr schliesst die Luecke klassischer Discovery-Tools: Diese kennen die IT-Landschaft, aber nicht den Business-Kontext aus Prozessdokumentation.

---

## 2. Gesamtarchitektur

Das System besteht weiterhin aus zwei klar getrennten Schichten:

- Pipeline:
  Prozessdokumente + CMDB -> optionale Vortransformation fuer grosse BPMN -> Extraktion -> Matching -> Review-Artefakte -> Graph-DB
- Abfrage-Layer:
  Web-UI -> LLM -> Cypher -> Neo4j -> Antwort in natuerlicher Sprache

Die Pipeline bleibt sequentiell, nachvollziehbar und idempotent.

Neu in v0.15 ist die fachliche Trennung zwischen:

- **Import**
  verarbeitet neue Dokumente aus der Inbox und schreibt freigegebene Ergebnisse in Neo4j
- **Review**
  oeffnet und bearbeitet bereits bekannte schwache bzw. offene Matching-Faelle, ohne einen neuen Importlauf aus dem aktuellen Input zu starten

---

## 3. Inputs und Dateifluss

### 3.1 Eingangsdateien

- Prozessdokumente:
  BPMN sowie unstrukturierte Prozessbeschreibungen als TXT, DOCX oder PDF
- Transformierte BPMN-Prozessdateien:
  aus grossen BPMN/XML-Dateien abgeleitete, kompakte TXT-Dateien mit genau einer Importeinheit pro Prozess
- CMDB-Export:
  CSV oder Excel; das benoetigte Spaltenmapping wird in Tab 3 gepflegt

### 3.2 Inbox-Prinzip

`Input/` ist die reine Inbox des Benutzers.

Das bedeutet:

- der Benutzer legt dort neue Prozessdateien und die aktuell zu verwendende CMDB-Datei ab
- `Input/` und seine Unterordner dienen nicht als dauerhafter Ablageort bereits verarbeiteter Prozessdateien
- nach einem erfolgreichen Importlauf verschwinden die verarbeiteten Prozessdateien aus der Inbox

### 3.3 Archivierung verarbeiteter Dateien

Verarbeitete Prozessdateien werden nicht stillschweigend geloescht, sondern in ein Archiv unterhalb von `data/` verschoben.

Zielstruktur:

```text
bridgr/
├── Input/                      # nur neue, noch nicht verarbeitete Eingaben
├── data/
│   └── input_archive/
│       └── <run-id-oder-timestamp>/
│           ├── <prozessdatei1>
│           ├── <prozessdatei2>
│           └── ...
```

Regeln:

- pro erfolgreichem Importlauf wird ein eigener Archivordner angelegt
- der Archivordnername ist transparent und eindeutig, z. B. Timestamp oder Run-ID
- die GUI zeigt nach dem Lauf an, wohin die Dateien verschoben wurden
- Laufartefakte halten fest, welche Quelldateien in welchen Archivordner ueberfuehrt wurden

Die CMDB-Datei bleibt davon ausgenommen, sofern sie als weiterhin aktive Referenzdatei im Input-Bereich benoetigt wird.

---

## 4. Scope v0.15

| Bereich | In Scope | Out of Scope |
|---|---|---|
| Eingabeformate | BPMN, TXT, DOCX, PDF | Weitere Formate |
| UI | Streamlit Web-UI (4 Tabs inkl. `Organisation`) mit getrennten UI- und Service-Modulen | CLI-Review |
| Review | Bearbeitung bereits bekannter schwacher oder offener Matching-Faelle | Externes Ticketing |
| Lauf-Modi | `full`, `partial` | `initial`, automatische Delta-Erkennung ueber Hashvergleich als eigener UI-Modus |
| Deployment | Lokal / Docker | Cloud-Deployment der Anwendung |

Wichtige Einordnung:

- `Input/` ist keine dauerhafte Dokumentablage, sondern eine verarbeitete Inbox
- Review ist kein neuer Importlauf auf dem aktuellen Input-Bestand

---

## 5. Domaenenmodell

### Prozess

Ein Prozess entspricht bei BPMN einem `<process>`-Element. Bei transformierten BPMN-TXT-Dateien entspricht eine Datei genau einem Prozess. Bei unstrukturierten Formaten wird der vom LLM extrahierte oder spaeter gematchte Prozessname als fachlicher Bezugspunkt verwendet.

### folgt_auf

Bei BPMN wird die Beziehung aus dem modellierten Sequenzzusammenhang zwischen Prozessen abgeleitet. Bei unstrukturierten Formaten kann `folgt_auf` nur dann befuellt werden, wenn die Beschreibung dies explizit oder hinreichend klar hergibt.

### Anwendung

Eine Anwendung ist ein in der CMDB gefuehrtes System. Pflichtfelder in Bridgr bleiben UUID und Name. Im Graph wird nur die Referenz `cmdb_id` plus der Anzeigename der Anwendung gehalten.

### Rolle und OrgEinheit

Lane- oder Akteursbezeichnungen aus Prozessmodellen werden fachlich zunaechst als `rolle` behandelt.

`org_einheit` ist davon getrennt zu modellieren und darf nicht stillschweigend aus einer Rollenbezeichnung abgeleitet werden.

Fuer v0.15 gilt als Zielregel:

- `rolle` wird immer aus der Prozessquelle uebernommen, wenn ein verantwortlicher Akteur oder eine Lane-Bezeichnung vorliegt
- `org_einheit` wird nur dann gesetzt, wenn die Bezeichnung 1:1 gegen eine gepflegte Liste bekannter Organisationseinheiten gematcht werden kann
- bei einem 1:1-Match duerfen `rolle` und `org_einheit` gleichzeitig denselben Wert tragen
- ohne Match bleibt `org_einheit` leer
- moegliche Organisationseinheiten aus Prozessdokumenten duerfen im ersten Wurf nur als Kandidaten gesammelt werden und fliessen nicht direkt als `org_einheit` in den produktiven Graph

Bridgr fuehrt keine fachlich eigenstaendige Pflege oder manuelle Zuordnung `OrgEinheit -> Prozess` ein; solche Verantwortungsbeziehungen werden nur abgebildet, wenn sie aus dem Prozessmanagement bzw. aus den verarbeiteten Prozessquellen ableitbar oder dort bereits gepflegt sind.

---

## 6. Anwendungsschichten

### 6.1 Zielstruktur

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

### 6.2 Verantwortlichkeiten

#### `app.py`

- Streamlit-Entrypoint
- Page-Setup
- Tab-Verdrahtung
- keine fachlichen UI-Aktionen und keine langen Seiteneffekt-Workflows

#### `ui/*`

- Rendern von Tabs, Formularen, Tabellen, Expandern und Hinweisen
- Auslesen von Benutzereingaben
- Aufruf von Service-Funktionen
- keine Fachlogik fuer KB-, Graph-, Archiv- oder Refresh-Operationen ausser einfacher Ergebnisdarstellung

#### `services/*`

- kapseln UI-ausgeloeste Seiteneffekte
- orchestrieren Import, Archivierung, Knowledge Base, Artefakt-Refresh, Neo4j-Synchronisation und Query-Ausfuehrung
- liefern moeglichst kleine, testbare Funktionen mit klaren Ein- und Ausgaben

#### `pipeline.py` und `skills/*`

- bleiben die fachliche Kernstrecke fuer Extraktion, Matching, Review-Artefakterzeugung und Graph-Schreiben
- werden nicht durch Streamlit-spezifische Zustandslogik verunreinigt

---

## 7. Importlogik

### 7.1 Importmodi

Es gibt in v0.15 nur noch zwei fachlich sichtbare Importmodi:

- `full`
  verarbeitet den gesamten aktuellen Prozessdateibestand unterhalb von `Input/`
- `partial`
  verarbeitet nur die vom Benutzer explizit ausgewaehlten Prozessdateien

Der bisherige Modus `initial` entfaellt.

Der Begriff `partial` ist bewusst gewaehlt, weil hier nicht "seit letztem Lauf geaendert", sondern "gezielt ausgewaehlte Teilmenge" gemeint ist.

### 7.2 Verhalten nach dem Import

Nach einem erfolgreichen Importlauf gilt:

- die verarbeiteten Prozessdateien werden aus `Input/` entfernt
- sie werden in das Laufarchiv unter `data/input_archive/<run-id-oder-timestamp>/` verschoben
- der Zielpfad wird in der GUI sichtbar gemacht
- die Laufartefakte verweisen auf den Archivkontext des Imports

### 7.3 Upload-Verhalten

Ein separater Button `Importdateien speichern` ist im Zielbild nicht mehr vorgesehen.

Begruendung:

- `Input/` ist die Inbox
- der Benutzer legt Dateien dort direkt ab
- ein zusaetzlicher Speicher-Button erzeugt nur einen zweiten, konkurrierenden Importweg

---

## 8. Matching und Review

Die Reihenfolge bleibt:

1. Knowledge Base
2. Fuzzy Matching
3. optional spaeterer LLM-Fallback fuer unklare Matching-Faelle

Schwache Kandidaten bleiben reviewbar und werden nicht automatisch in den Graph geschrieben.

Explizite manuelle Links bleiben moeglich. Bestaetigte Links aus der Knowledge Base duerfen jedoch nicht mehr stillschweigend historische, im aktuellen Extrakt nicht mehr vorhandene Anwendungen wieder in den Graph-Lauf einschleusen, ausser sie wurden bewusst als manueller Zusatzlink angelegt.

### 8.1 Review-Semantik

Tab 2 ist in v0.15 fachlich keine "Pipeline Preview" mehr.

Stattdessen ist die Funktion:

- `Review oeffnen`
  laedt bereits bekannte schwache, offene oder manuell zu bearbeitende Matching-Faelle aus den vorhandenen Laufartefakten

Das bedeutet:

- Review startet keinen neuen regulären Importlauf auf dem aktuellen Input-Bestand
- Review bearbeitet bekannte Artefakte, offene Links und KB-nahe Entscheidungen
- gezielte Aktualisierungen einzelner Artefakte duerfen weiterhin erfolgen, aber nicht als verdeckter Vollimport aus der Inbox

Fuer Rollen und Organisationseinheiten gilt zusaetzlich:

- das Mapping von `rolle` zu `org_einheit` ist kein Fuzzy-Matching
- im ersten Wurf wird nur ein normalisierter 1:1-Abgleich gegen benutzergepflegte Organisationseinheiten zugelassen
- Prozessquellen duerfen zusaetzlich Kandidaten fuer moegliche Organisationseinheiten liefern, diese bleiben aber ausserhalb des produktiven Graph-Modells, bis der Benutzer sie in Tab 4 bestaetigt, mappt oder verwirft

---

## 9. Graph Writer

Das Neo4j-Schema bleibt unveraendert:

```cypher
(:OrgEinheit)-[:VERANTWORTET]->(:Prozess)
(:Prozess)-[:FOLGT_AUF]->(:Prozess)
(:Prozess)-[:NUTZT]->(:Anwendung)
```

In den Graph werden weiterhin nur geschrieben:

- starke Links
- oder durch Knowledge Base freigegebene Links

Vor dem Neuschreiben der prozessbezogenen Beziehungen werden bestehende `NUTZT`-, `VERANTWORTET`- und `BETEILIGT_AN`-Kanten dieses Prozesses entfernt.

Nicht mehr extrahierte Anwendungen werden bei Full- oder Partial-Updates nicht durch normale bestaetigte KB-Links automatisch wiederbelebt. Nur explizite manuelle Zusatzlinks duerfen weiterhin ausserhalb des aktuellen Extrakts fortgeschrieben werden.

---

## 10. Abfrage-Layer

Tab 1 bleibt:

- Frage in natuerlicher Sprache
- LLM erzeugt read-only Cypher
- Neo4j liefert Treffer
- LLM formuliert eine natuerliche Antwort

Die Query-Validierung bleibt weiterhin technisch abgesichert. Ein getrennter read-only Neo4j-User bleibt ein sinnvoller spaeterer Haertungsschritt.

---

## 11. Anwendungskonfig

Tab 3 verwaltet weiterhin:

- Input-Pfad
- aktive CMDB-Datei
- Output-Pfad
- LLM-Endpoint, Modell und API-Key-Umgebungsvariable
- Neo4j-Zugangsdaten
- Fuzzy-Threshold
- Importmodus

Mit v0.15 gilt zusaetzlich:

- der Importbereich fokussiert auf den echten Importlauf
- der Button `Pipeline starten` bleibt der einzige regulaere Startpunkt fuer neue Imports
- die Benennung `Pipeline Preview starten` entfaellt zugunsten einer klaren Review-Benennung in Tab 2

---

## 12. Akzeptanzkriterien

1. Korrekte Informationen aus den Quelldaten koennen ueber die Weboberflaeche abgefragt werden
2. Mappings sind ueber die Weboberflaeche pflegbar
3. Informationen zu Prozessen und Anwendungen koennen ueber die Weboberflaeche abgerufen werden
4. Die Pipeline laeuft stabil durch einen vollstaendigen Importzyklus
5. Der Ausbau auf TXT, DOCX und PDF folgt demselben gemeinsamen semantischen Extraktionsschema
6. Grosse BPMN/XML-Dateien koennen ueber den Transformationspfad in prozessweise, stabile Importeinheiten ueberfuehrt werden
7. `Input/` bleibt nach einem erfolgreichen Lauf frei von verarbeiteten Prozessdateien
8. Verarbeitete Prozessdateien werden transparent in ein Archiv unter `data/input_archive/` verschoben
9. `app.py` enthaelt nur noch Entrypoint- und Verdrahtungslogik; Tab-Rendering und UI-nahe Orchestrierung liegen in getrennten Modulen
10. UI-Aktionen fuer Review, Organisation, Query und Import sind ausserhalb des Entrypoints testbar

---

## 13. Getroffene Entscheidungen

| Entscheidung | Gewaehlt | Verworfen | Begruendung |
|---|---|---|---|
| UI-Struktur | getrennte Tab-Module plus Service-Schicht | monolithische `app.py` als alleiniger Ort fuer UI und Seiteneffekte | reduziert Kopplung, verbessert Testbarkeit und ermoeglicht inkrementelle Erweiterungen ohne neuen God-File |
| Extraktion | gemeinsamer semantischer Extraktionspfad | format-spezifische fachliche Parser fuer TXT, DOCX oder PDF | der semantische Kern liegt im Modell und im Prompt, nicht in pro Format unterschiedlicher Fachlogik |
| Lane-/Akteursbezeichnungen | zunaechst immer als `rolle`, `org_einheit` nur bei 1:1-Match gegen gepflegte Referenzliste | direkte Ableitung `Lane = OrgEinheit` oder fruehes Fuzzy-/Vision-Mapping | Rollen und Organisationseinheiten duerfen fachlich nicht vermischt werden |
| Verantwortung `OrgEinheit -> Prozess` | Bridgr bildet solche Beziehungen nur aus angelieferten oder aus Prozessquellen ableitbaren Informationen ab | manuelle fachliche Pflege dieser Beziehungen innerhalb von Bridgr | die fachliche Quelle fuer Prozessverantwortung bleibt das Prozessmanagement; Bridgr ist hier abbildendes System, nicht fuehrendes System |
| Importmodi | nur `full` und `partial` | `initial` als separater Modus, `delta` als mehrdeutiger Begriff | die Benennung muss das fachliche Verhalten widerspiegeln: gesamter Inbox-Bestand oder explizit gewaehlte Teilmenge |
| Inbox-Semantik | `Input/` ist reine Inbox fuer neue Eingaben | `Input/` als dauerhafte Mischung aus neuen und bereits verarbeiteten Prozessdateien | der Arbeitsbereich des Benutzers bleibt klar und nachvollziehbar |
| Umgang mit verarbeiteten Dateien | nach erfolgreichem Lauf aus `Input/` entfernen und transparent unter `data/input_archive/` archivieren | stilles Behalten in `Input/` oder endgueltiges Loeschen ohne Archivspur | verbindet saubere Inbox mit Nachvollziehbarkeit und Reproduzierbarkeit |
| Review-Funktion | Review oeffnet bekannte schwache/offene Faelle aus Artefakten | Review als neuer regulaerer Importlauf auf dem aktuellen Input-Bestand | Import und Review sind fachlich verschieden und muessen in der UI klar getrennt sein |
| Importweg | kein separater Button `Importdateien speichern` | paralleler zweiter Speicher-/Importweg neben direkter Inbox-Nutzung | reduziert Verwirrung und erzwingt einen klaren Benutzerpfad |

---

*Bridgr | Architektur v0.15 | Stand Mai 2026*

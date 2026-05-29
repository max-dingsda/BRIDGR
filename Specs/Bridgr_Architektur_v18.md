# Bridgr
**CMDB-Zielarchitektur** | Stand: Mai 2026 | v0.18

---

## 1. Ziel

Prozessdokumentation und CMDB-Export zusammenfuehren, um einen EA-Wissensgraphen aufzubauen und ihn ueber eine natuerlichsprachliche Web-Oberflaeche abfragbar zu machen.

Kernfrage:
Welche IT-Bausteine unterstuetzen welche Geschaeftsprozesse und wie sicher wissen wir das?

Bridgr schliesst die Luecke klassischer Discovery-Tools: Diese kennen die IT-Landschaft, aber nicht den Business-Kontext aus Prozessdokumentation.

---

## 2. Gesamtarchitektur

Das System besteht weiterhin aus zwei klar getrennten Schichten:

- Pipeline:
  Prozessdokumente + CMDB -> optionale Vortransformation fuer grosse BPMN -> Extraktion -> Matching -> Review-Artefakte -> Graph-DB
- Abfrage-Layer:
  Web-UI -> LLM -> Cypher -> Neo4j -> Antwort in natuerlicher Sprache

Die Pipeline bleibt sequentiell, nachvollziehbar und idempotent.

Neu in v0.18 ist die fachliche Erweiterung des CMDB-Modells:

- CMDB-Objekte werden nicht mehr pauschal als `Anwendung` interpretiert
- Bridgr unterscheidet mindestens zwischen `Anwendung`, `Schnittstelle` und `Server`
- Verantwortungsbeziehungen aus der CMDB duerfen generisch als `VERANTWORTET` uebernommen werden
- Die Prozessanbindung wird naeher an ArchiMate als `Anwendung -[:DIENT]-> Prozess` modelliert

---

## 3. Inputs und Dateifluss

### 3.1 Eingangsdateien

- Prozessdokumente:
  BPMN sowie unstrukturierte Prozessbeschreibungen als TXT, DOCX oder PDF
- Transformierte BPMN-Prozessdateien:
  aus grossen BPMN/XML-Dateien abgeleitete, kompakte TXT-Dateien mit genau einer Importeinheit pro Prozess
- CMDB-Export:
  vorerst nur CSV; weitere Formate bleiben bewusst ausserhalb von v0.16

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

## 4. Scope v0.18

| Bereich | In Scope | Out of Scope |
|---|---|---|
| Eingabeformate | BPMN, TXT, DOCX, PDF, CMDB als CSV | ODT/ODF und weitere CMDB-Dateiformate |
| UI | Streamlit Web-UI (4 Tabs inkl. `Organisation`) mit getrennten UI- und Service-Modulen | CLI-Review |
| Review | Bearbeitung bereits bekannter schwacher oder offener Matching-Faelle | Externes Ticketing |
| Lauf-Modi | `full`, `partial` | `initial`, automatische Delta-Erkennung ueber Hashvergleich als eigener UI-Modus |
| CMDB-Modell | `Anwendung`, `Schnittstelle`, `Server`, `OrgEinheit` | tiefe Attributmodellierung ueber `id`, `name`, `server_type` hinaus |
| Deployment | Lokal / Docker | Cloud-Deployment der Anwendung |

Wichtige Einordnung:

- `Input/` ist keine dauerhafte Dokumentablage, sondern eine verarbeitete Inbox
- Review ist kein neuer Importlauf auf dem aktuellen Input-Bestand
- die CMDB-Erweiterung priorisiert funktionales Verhalten vor Attributtiefe

---

## 5. Domaenenmodell

### Prozess

Ein Prozess entspricht bei BPMN einem `<process>`-Element. Bei transformierten BPMN-TXT-Dateien entspricht eine Datei genau einem Prozess. Bei unstrukturierten Formaten wird der vom LLM extrahierte oder spaeter gematchte Prozessname als fachlicher Bezugspunkt verwendet.

### folgt_auf

Bei BPMN wird die Beziehung aus dem modellierten Sequenzzusammenhang zwischen Prozessen abgeleitet. Bei unstrukturierten Formaten kann `folgt_auf` nur dann befuellt werden, wenn die Beschreibung dies explizit oder hinreichend klar hergibt.

### Anwendung

Eine Anwendung ist ein in der CMDB gefuehrtes System.

Pflichtattribute in v0.18:

- `id`
- `name`

### Schnittstelle

Eine Schnittstelle ist ein in der CMDB separat gefuehrter Integrations- oder Uebergabepunkt.

Pflichtattribute in v0.18:

- `id`
- `name`

### Server

Ein Server ist ein physischer oder virtueller Infrastrukturknoten aus der CMDB.

Pflichtattribute in v0.18:

- `id`
- `name`
- `server_type` mit `physical` oder `virtual`

### Rolle und OrgEinheit

Lane- oder Akteursbezeichnungen aus Prozessmodellen werden fachlich zunaechst als `rolle` behandelt.

`org_einheit` ist davon getrennt zu modellieren und darf nicht stillschweigend aus einer Rollenbezeichnung abgeleitet werden.

Fuer v0.18 gilt:

- `rolle` wird immer aus der Prozessquelle uebernommen, wenn ein verantwortlicher Akteur oder eine Lane-Bezeichnung vorliegt
- `org_einheit` wird nur dann direkt gesetzt, wenn die Bezeichnung 1:1 gegen eine gepflegte Liste bekannter Organisationseinheiten gematcht werden kann
- ohne Match bleibt `org_einheit` leer
- moegliche Organisationseinheiten aus Prozessdokumenten duerfen nur als Kandidaten gesammelt werden und fliessen nicht direkt als `org_einheit` in den produktiven Graph

### Verantwortung

`VERANTWORTET` ist in v0.18 eine generische fachliche Beziehung von `OrgEinheit` zu einem Zielobjekt.

Moegliche Zielobjekte:

- `Prozess`
- `Anwendung`
- `Schnittstelle`
- `Server`

Quellen:

- Prozessdokumente
- CMDB

Fuer Verantwortungsinformationen aus der CMDB gilt:

- bei einem 1:1-Match zu einer bekannten Organisationseinheit darf `VERANTWORTET` direkt geschrieben werden
- bei unsicherem oder fehlendem Match wird ein Kandidat erzeugt
- Bridgr schreibt keine freie neue `OrgEinheit` allein auf Basis eines unsicheren Owner-Strings produktiv in den Graph

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
- kapseln kuenftig auch CMDB-spezifisches Mapping und Owner-Kandidatenlogik
- liefern moeglichst kleine, testbare Funktionen mit klaren Ein- und Ausgaben

#### `pipeline.py` und `skills/*`

- bleiben die fachliche Kernstrecke fuer Extraktion, Matching, Review-Artefakterzeugung und Graph-Schreiben
- werden nicht durch Streamlit-spezifische Zustandslogik verunreinigt

---

## 7. Importlogik

### 7.1 Importmodi

Es gibt in v0.16 nur noch zwei fachlich sichtbare Importmodi:

- `full`
  verarbeitet den gesamten aktuellen Prozessdateibestand unterhalb von `Input/`
- `partial`
  verarbeitet nur die vom Benutzer explizit ausgewaehlten Prozessdateien

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

Explizite manuelle Links bleiben moeglich.

### 8.1 Review-Semantik

Tab 2 ist in v0.16 fachlich weiterhin kein neuer Importlauf.

Stattdessen ist die Funktion:

- Bearbeitung bereits bekannter schwacher, offener oder manuell zu pflegender Matching-Faelle aus den vorhandenen Laufartefakten

Das bedeutet:

- Review startet keinen neuen regulaeren Importlauf auf dem aktuellen Input-Bestand
- Review bearbeitet bekannte Artefakte, offene Links und KB-nahe Entscheidungen
- gezielte Aktualisierungen einzelner Artefakte duerfen weiterhin erfolgen, aber nicht als verdeckter Vollimport aus der Inbox

Fuer Organisationseinheiten gilt zusaetzlich:

- das Mapping von `rolle` zu `org_einheit` ist kein Fuzzy-Matching
- aus Prozessquellen identifizierte moegliche Organisationseinheiten bleiben Kandidaten, bis sie in Tab 4 bestaetigt, gemappt oder verworfen werden
- dieselbe Kandidatenlogik gilt fuer unsichere Owner-Bezeichnungen aus der CMDB

---

## 9. Graph Writer

Das Zielschema wird in v0.18 erweitert.

Mindestens folgende Knotenlabels werden unterschieden:

```cypher
(:Prozess)
(:Anwendung)
(:Schnittstelle)
(:Server)
(:OrgEinheit)
```

Mindestens folgende Beziehungen werden fachlich vorgesehen:

```cypher
(:OrgEinheit)-[:VERANTWORTET]->(:Prozess)
(:OrgEinheit)-[:VERANTWORTET]->(:Anwendung)
(:OrgEinheit)-[:VERANTWORTET]->(:Schnittstelle)
(:OrgEinheit)-[:VERANTWORTET]->(:Server)
(:Prozess)-[:FOLGT_AUF]->(:Prozess)
(:Anwendung)-[:DIENT]->(:Prozess)
(:Anwendung)-[:USES_INTERFACE]->(:Schnittstelle)
(:Anwendung)-[:RUNS_ON]->(:Server)
(:Schnittstelle)-[:RUNS_ON]->(:Server)
```

Diese technischen Beziehungen zwischen `Anwendung`, `Schnittstelle` und `Server` sind in v0.18 nicht mehr nur vorbereitet, sondern Teil des aktuellen Ziel- und Query-Schemas.

In den Graph werden weiterhin nur geschrieben:

- starke Links
- oder durch Knowledge Base bzw. explizite Bestaetigung freigegebene Links

Vor dem Neuschreiben der prozessbezogenen Beziehungen werden bestehende prozessbezogene Kanten des betroffenen Prozesses konsistent bereinigt.

---

## 10. Abfrage-Layer

Tab 1 bleibt:

- Frage in natuerlicher Sprache
- LLM erzeugt read-only Cypher
- Neo4j liefert Treffer
- LLM formuliert eine natuerliche Antwort

Mit v0.18 muss der Query-Layer das erweiterte CMDB-Schema kennen:

- `Anwendung`
- `Schnittstelle`
- `Server`
- `OrgEinheit`
- `Prozess`
- `DIENT`
- `VERANTWORTET`
- `FOLGT_AUF`
- `USES_INTERFACE`
- `RUNS_ON`

`graph_schema.py` ist die kanonische Quelle fuer dieses erlaubte Query-Schema. Prompting und lokale Query-Validierung muessen sich auf dieses kanonische Schema stuetzen und nicht auf eine Live-Introspektion der aktuell befuellten Datenbank.

Fuer Chat-Folgefragen gilt zusaetzlich:

- der Abfrage-Layer darf nicht nur die aktuelle Benutzerfrage isoliert betrachten
- der Code kuratiert einen relevanten Kontextblock aus vorherigen Benutzer- und Assistant-Nachrichten
- in der aktuellen Umsetzung umfasst dieser Kontextblock einen begrenzten, aber grosszuegigen Ausschnitt der juengsten Chat-Nachrichten beider Rollen statt nur den letzten Turn
- dieser Kontextblock wird bei der Query-Generierung explizit mitgegeben, ohne technische Rohdaten wie ganze Result-Tabellen oder Cypher-Verlaeufe mitzuschleppen
- zusaetzlich darf der Code einen aktuell aufgeloesten Objektfokus, z. B. `Anwendung` + `Name` + optionale `ID`, separat als strukturierten Kontext halten und an spaetere Folgefragen weiterreichen
- welche Inhalte als fortgeltender Chat-Zustand gelten, entscheidet nicht frei das LLM, sondern der Code anhand expliziter Regeln

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

Mit v0.16 gilt zusaetzlich:

- der Importbereich fokussiert auf den echten Importlauf
- der Button `Pipeline starten` bleibt der einzige regulaere Startpunkt fuer neue Imports
- die CMDB-Konfiguration muss kuenftig auch das Mapping auf die Zieltypen `Anwendung`, `Schnittstelle`, `Server` sowie auf Owner-/Verantwortungsinformationen unterstuetzen

---

## 12. Akzeptanzkriterien

1. Korrekte Informationen aus den Quelldaten koennen ueber die Weboberflaeche abgefragt werden
2. Mappings sind ueber die Weboberflaeche pflegbar
3. Informationen zu Prozessen, Anwendungen, Schnittstellen und Servern koennen ueber die Weboberflaeche abgerufen werden
4. Die Pipeline laeuft stabil durch einen vollstaendigen Importzyklus
5. Der Ausbau auf TXT, DOCX und PDF folgt demselben gemeinsamen semantischen Extraktionsschema
6. Grosse BPMN/XML-Dateien koennen ueber den Transformationspfad in prozessweise, stabile Importeinheiten ueberfuehrt werden
7. `Input/` bleibt nach einem erfolgreichen Lauf frei von verarbeiteten Prozessdateien
8. Verarbeitete Prozessdateien werden transparent in ein Archiv unter `data/input_archive/` verschoben
9. `app.py` enthaelt nur noch Entrypoint- und Verdrahtungslogik; Tab-Rendering und UI-nahe Orchestrierung liegen in getrennten Modulen
10. CMDB-Objekte werden nicht mehr pauschal als `Anwendung` in Neo4j geschrieben
11. Verantwortungsinformationen aus der CMDB werden als `VERANTWORTET` verarbeitet, bei unsicherer Org-Zuordnung jedoch als Kandidat statt als stiller Direktschreibvorgang
12. Prozessbeziehungen zu IT-Bausteinen werden im Zielbild als `Anwendung -[:DIENT]-> Prozess` modelliert

---

## 13. Getroffene Entscheidungen

| Entscheidung | Gewaehlt | Verworfen | Begruendung |
|---|---|---|---|
| CMDB-Dateiformat | vorerst nur CSV | gleichzeitige Erweiterung auf mehrere Formate | zuerst muss das fachliche Modell stabilisiert werden, bevor Dateiformatbreite Mehrwert bringt |
| CMDB-Zielobjekte | `Anwendung`, `Schnittstelle`, `Server`, `OrgEinheit` | alles als `Anwendung` modellieren | das bisherige Modell verliert fachliche Unterschiede typischer CMDB-Inhalte |
| Attributtiefe | Minimalmodell mit `id`, `name`, bei `Server` zusaetzlich `server_type` | breites Attributset im ersten Schritt | die Funktionalitaet ist aktuell wichtiger als ein frueh ueberladenes Datenmodell |
| Server-Modell | ein Label `Server` mit Attribut `server_type` | getrennte Labels fuer physische und virtuelle Server | haelt das Modell im ersten Schritt einfach und ausreichend auswertbar |
| Ownership-Semantik | generische Beziehung `VERANTWORTET` | semantisch enges `BESITZT` | `VERANTWORTET` ist fachlich lesbarer und passt besser zu generischer Ownership in Prozess- und CMDB-Quellen |
| Quelle fuer `VERANTWORTET` | Prozessquellen und CMDB duerfen beide Verantwortungen liefern | Verantwortung nur aus Prozessquellen zulassen | in realen Modellen ist Ownership haeufig generisch und muss deshalb auch aus der CMDB abbildbar sein |
| Unsichere CMDB-Owner | Kandidatenlogik analog zur Org-Pruefung aus dem Prozessimport | unsichere Owner-Strings direkt als produktive Org-Einheiten schreiben | verhindert stilles Aufblaehen des Org-Modells durch Freitext aus der CMDB |
| Prozessanbindung | `(:Anwendung)-[:DIENT]->(:Prozess)` | `(:Prozess)-[:NUTZT]->(:Anwendung)` als alleinige Zielsemantik | die neue Richtung ist naeher an ArchiMate und semantisch klarer fuer die Servicesicht |

---

*Bridgr | Architektur v0.16 | Stand Mai 2026*

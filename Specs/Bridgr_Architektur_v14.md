# Bridgr
**Zielarchitektur nach UI-Entschlackung** | Stand: Mai 2026 | v0.14

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
  Prozessdokumente + CMDB -> optionale Vortransformation fuer grosse BPMN -> Extraktion -> Matching -> Review -> Graph-DB
- Abfrage-Layer:
  Web-UI -> LLM -> Cypher -> Neo4j -> Antwort in natuerlicher Sprache

Neu in v0.14 ist die interne Trennung innerhalb der Web-Anwendung:

- UI-Module rendern Tabs, Formulare, Tabellen und Statusmeldungen
- Service-Module kapseln fachliche UI-Aktionen mit Seiteneffekten
- technische Session-/Runtime-Helfer bleiben getrennt von Fachlogik

Die Pipeline bleibt sequentiell, nachvollziehbar und idempotent.

---

## 3. Inputs

- Prozessdokumente:
  BPMN sowie unstrukturierte Prozessbeschreibungen als TXT, DOCX oder PDF
- Transformierte BPMN-Prozessdateien:
  aus grossen BPMN/XML-Dateien abgeleitete, kompakte TXT-Dateien mit genau einer Importeinheit pro Prozess
- CMDB-Export:
  CSV oder Excel; das benoetigte Spaltenmapping wird in Tab 3 gepflegt

Wichtige Einordnung:
Der Input-Pfad bleibt eine Ablage- und Auswahlhilfe. Verarbeitet werden im UI-Pfad nicht stillschweigend alle Dateien des Ordners, sondern die vom Benutzer explizit ausgewaehlten Prozessdateien.

---

## 4. Scope v0.14

| Bereich | In Scope | Out of Scope |
|---|---|---|
| Eingabeformate | BPMN, TXT, DOCX, PDF | Weitere Formate |
| UI | Streamlit Web-UI (4 Tabs inkl. `Organisation`) mit modularisiertem UI-Code | CLI-Review |
| Review | Tab 2 im Web-UI | Externes Ticketing |
| Lauf-Modi | Initial, Full Update, Delta Update | Parallele Agent-Pipeline |
| Query-Layer | Tab 1 (NL -> Cypher -> Antwort) | Schreibender Query-Layer |
| Deployment | Lokal / Docker | Cloud-Deployment der Anwendung |

Wichtige Einordnung:
Die Spezifikation oeffnet den fachlichen Scope fuer unstrukturierte Prozessbeschreibungen. Die aktuelle Implementierung bleibt BPMN-first, unterstuetzt aber inzwischen auch einen transformierten Importpfad fuer sehr grosse BPMN/XML-Dateien.

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

Fuer v0.14 gilt als Zielregel:

- `rolle` wird immer aus der Prozessquelle uebernommen, wenn ein verantwortlicher Akteur oder eine Lane-Bezeichnung vorliegt
- `org_einheit` wird nur dann gesetzt, wenn die Bezeichnung 1:1 gegen eine gepflegte Liste bekannter Organisationseinheiten gematcht werden kann
- bei einem 1:1-Match duerfen `rolle` und `org_einheit` gleichzeitig denselben Wert tragen
- ohne Match bleibt `org_einheit` leer
- moegliche Organisationseinheiten aus Prozessdokumenten duerfen im ersten Wurf nur als Kandidaten gesammelt werden und fliessen nicht direkt als `org_einheit` in den produktiven Graph

Diese Trennung ist bewusst konservativ, um Rollen nicht faelschlich als Organisationseinheiten in den Graph zu schreiben.

---

## 6. Anwendungsschichten

### 6.1 Zielstruktur

```text
bridgr/
├── prompts/
├── skills/
├── services/
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
- keine Fachlogik fuer KB-, Graph- oder Refresh-Operationen ausser einfacher Ergebnisdarstellung

#### `services/*`

- kapseln UI-ausgeloeste Seiteneffekte
- orchestrieren Knowledge Base, Artefakt-Refresh, Neo4j-Synchronisation und Query-Ausfuehrung
- liefern moeglichst kleine, testbare Funktionen mit klaren Ein- und Ausgaben

#### `pipeline.py` und `skills/*`

- bleiben die fachliche Kernstrecke fuer Extraktion, Matching, Review-Artefakterzeugung und Graph-Schreiben
- werden nicht durch Streamlit-spezifische Zustandslogik verunreinigt

---

## 7. Pipeline

Die Pipeline bleibt sequentiell. Geschwindigkeit ist gegenueber Korrektheit, Transparenz und Wiederholbarkeit nachrangig.

### 7.1 Extraktion

#### Grundsatz

Es gibt keinen format-spezifischen fachlichen Parser-Layer fuer unstrukturierte Prozessbeschreibungen.

Bridgr trennt stattdessen drei Dinge:

- optionale strukturierende Vorreduktion fuer grosse BPMN/XML-Dateien
- technische Textgewinnung pro Format
- gemeinsame semantische Extraktion ueber das LLM

Das bedeutet:

- BPMN klein/mittel:
  rohes XML direkt an das Modell
- BPMN gross/rauschig:
  zunaechst LLM-freie Vortransformation in kompakte Prozessdateien, danach TXT-basierte Extraktion
- TXT:
  Text direkt an das Modell
- DOCX:
  Text aus dem Dokument gewinnen, dann an das Modell
- PDF:
  Text aus dem Dokument gewinnen, dann an das Modell

Die eigentliche Fachintelligenz bleibt im Prompt und im gemeinsamen Ausgabeschema, nicht in format-spezifischer Parserlogik.

#### BPMN-Transformer fuer grosse Modelle

Fuer sehr grosse oder sehr technische BPMN/XML-Dateien ist ein vorbereitender Transformationsschritt vorgesehen.

Eigenschaften:

- liest BPMN/XML ohne LLM
- erzeugt pro `<process>` genau eine kompakte TXT-Datei
- reduziert XML-Rauschen auf fachlich relevante Hinweise wie Prozessname, Prozess-ID, Lanes und modellnahe Anwendungsreferenzen
- stabilisiert damit lokale Modelllaeufe und verbessert Fehlerisolation

Die transformierte Datei ist keine neue fachliche Wahrheit, sondern eine technische Vorreduktion fuer den bestehenden Importpfad.

#### Fehlerbehandlung

- Kaputte oder ungueltige BPMN-Dateien werden als Dokumentfehler markiert
- Fehler in der Textgewinnung aus TXT, DOCX oder PDF werden ebenfalls als Dokumentfehler markiert
- Ungueltiges LLM-JSON wird mit Retry behandelt; danach wird das Dokument als Fehler markiert
- OpenAI-kompatible JSON-Ausgabe wird technisch ueber `response_format=json_object` plus nachgelagerte Strukturpruefung abgesichert

---

## 8. Matching und Review

Die Reihenfolge bleibt:

1. Knowledge Base
2. Fuzzy Matching
3. optional spaeterer LLM-Fallback fuer unklare Matching-Faelle

Schwache Kandidaten bleiben reviewbar und werden nicht automatisch in den Graph geschrieben.

Die primaere Arbeitsflaeche fuer den Benutzer bleibt die Review-Liste in Tab 2. Mehrfachkandidaten pro Prozessanwendung sind weiterhin erlaubt.

Explizite manuelle Links bleiben moeglich. Bestaetigte Links aus der Knowledge Base duerfen jedoch nicht mehr stillschweigend historische, im aktuellen Extrakt nicht mehr vorhandene Anwendungen wieder in den Graph-Lauf einschleusen, ausser sie wurden bewusst als manueller Zusatzlink angelegt.

Fuer Rollen und Organisationseinheiten gilt zusaetzlich:

- das Mapping von `rolle` zu `org_einheit` ist kein Fuzzy-Matching
- im ersten Wurf wird nur ein normalisierter 1:1-Abgleich gegen benutzergepflegte Organisationseinheiten zugelassen
- Prozessquellen duerfen zusaetzlich Kandidaten fuer moegliche Organisationseinheiten liefern, diese bleiben aber ausserhalb des produktiven Graph-Modells, bis der Benutzer sie in Tab 4 bestaetigt, mappt oder verwirft
- Bridgr fuehrt keine fachlich eigenstaendige Pflege oder manuelle Zuordnung `OrgEinheit -> Prozess` ein; solche Verantwortungsbeziehungen werden nur abgebildet, wenn sie aus dem Prozessmanagement bzw. aus den verarbeiteten Prozessquellen ableitbar oder dort bereits gepflegt sind

Neu in v0.14:

- Review-Aktionen werden aus der UI in dedizierte Service-Funktionen ausgelagert
- UI-Aktionen mit lokalem Fachbezug duerfen keine versteckten Vollumbauten ausloesen
- Refresh-Operationen muessen gezielt auf betroffene Dokumente oder den letzten Lauf begrenzt bleiben

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

Nicht mehr extrahierte Anwendungen werden bei Full- oder Delta-Updates nicht durch normale bestaetigte KB-Links automatisch wiederbelebt. Nur explizite manuelle Zusatzlinks duerfen weiterhin ausserhalb des aktuellen Extrakts fortgeschrieben werden.

---

## 10. Abfrage-Layer

Tab 1 bleibt:

- Frage in natuerlicher Sprache
- LLM erzeugt read-only Cypher
- Neo4j liefert Treffer
- LLM formuliert eine natuerliche Antwort

Die Query-Validierung bleibt weiterhin technisch abgesichert. Ein getrennter read-only Neo4j-User bleibt ein sinnvoller spaeterer Haertungsschritt.

Neu in v0.14:

- Chat-UI und Query-Ausfuehrung werden intern getrennt
- Rueckfragen, Ambiguitaetsbehandlung und Fehlerlogging sitzen nicht mehr im Streamlit-Entrypoint

---

## 11. Anwendungskonfig

Tab 3 verwaltet weiterhin:

- Input-Pfad
- aktive CMDB-Datei
- Output-Pfad
- LLM-Endpoint, Modell und API-Key-Umgebungsvariable
- Neo4j-Zugangsdaten
- Fuzzy-Threshold
- Laufmodus

Mit v0.14 gilt zusaetzlich:

- die Konfigurations-UI bleibt ein eigener Tab, wird aber code-seitig in ein eigenes UI-Modul ausgelagert
- Session-State-, Status- und Connection-Helfer werden von der eigentlichen Darstellungslogik getrennt

---

## 12. Akzeptanzkriterien

1. Korrekte Informationen aus den Quelldaten koennen ueber die Weboberflaeche abgefragt werden
2. Mappings sind ueber die Weboberflaeche pflegbar
3. Informationen zu Prozessen und Anwendungen koennen ueber die Weboberflaeche abgerufen werden
4. Die Pipeline laeuft stabil durch einen vollstaendigen Importzyklus
5. Der Ausbau auf TXT, DOCX und PDF folgt demselben gemeinsamen semantischen Extraktionsschema
6. Grosse BPMN/XML-Dateien koennen ueber den Transformationspfad in prozessweise, stabile Importeinheiten ueberfuehrt werden
7. `app.py` enthaelt nur noch Entrypoint- und Verdrahtungslogik; Tab-Rendering und UI-nahe Orchestrierung liegen in getrennten Modulen
8. UI-Aktionen fuer Review, Organisation, Query und Import sind ausserhalb des Entrypoints testbar

---

## 13. Getroffene Entscheidungen

| Entscheidung | Gewaehlt | Verworfen | Begruendung |
|---|---|---|---|
| UI-Struktur | getrennte Tab-Module plus Service-Schicht | monolithische `app.py` als alleiniger Ort fuer UI und Seiteneffekte | reduziert Kopplung, verbessert Testbarkeit und ermoeglicht inkrementelle Erweiterungen ohne neuen God-File |
| UI-Aktionslogik | gezielte Service-Funktionen fuer Refresh, Sync und KB-Aktionen | direkte Fachlogik in Streamlit-Callbacks | Seiteneffekte werden nachvollziehbarer und koennen ausserhalb des Renderings getestet werden |
| Extraktion | gemeinsamer semantischer Extraktionspfad | format-spezifische fachliche Parser fuer TXT, DOCX oder PDF | der semantische Kern liegt im Modell und im Prompt, nicht in pro Format unterschiedlicher Fachlogik |
| Lane-/Akteursbezeichnungen | zunaechst immer als `rolle`, `org_einheit` nur bei 1:1-Match gegen gepflegte Referenzliste | direkte Ableitung `Lane = OrgEinheit` oder fruehes Fuzzy-/Vision-Mapping | Rollen und Organisationseinheiten duerfen fachlich nicht vermischt werden |
| Verantwortung `OrgEinheit -> Prozess` | Bridgr bildet solche Beziehungen nur aus angelieferten oder aus Prozessquellen ableitbaren Informationen ab | manuelle fachliche Pflege dieser Beziehungen innerhalb von Bridgr | die fachliche Quelle fuer Prozessverantwortung bleibt das Prozessmanagement; Bridgr ist hier abbildendes System, nicht fuehrendes System |
| Importsteuerung im UI | explizite Dateiauswahl fuer den Lauf | stilles Verarbeiten des kompletten `input_path` | der Input-Ordner soll Orientierung geben, aber die Verarbeitungseinheit muss fuer den Benutzer explizit und kontrollierbar bleiben |

---

*Bridgr | Architektur v0.14 | Stand Mai 2026*

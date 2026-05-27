# Bridgr
**Architektur & Konzept** | Stand: Mai 2026 | v0.13

---

## 1. Ziel

Prozessdokumentation und CMDB-Export zusammenfuehren, um einen EA-Wissensgraphen aufzubauen und ihn ueber eine natuerlichsprachliche Web-Oberflaeche abfragbar zu machen.

Kernfrage:
Welche IT-Anwendungen unterstuetzen welche Geschaeftsprozesse und wie sicher wissen wir das?

Bridgr schliesst die Luecke klassischer Discovery-Tools: Diese kennen die IT-Landschaft, aber nicht den Business-Kontext aus Prozessdokumentation.

---

## 2. Gesamtarchitektur

Das System besteht aus zwei klar getrennten Schichten:

- Pipeline:
  Prozessdokumente + CMDB -> optionale Vortransformation fuer grosse BPMN -> Extraktion -> Matching -> Review -> Graph-DB
- Abfrage-Layer:
  Web-UI -> LLM -> Cypher -> Neo4j -> Antwort in natuerlicher Sprache

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

## 4. Scope v0.13

| Bereich | In Scope | Out of Scope |
|---|---|---|
| Eingabeformate | BPMN, TXT, DOCX, PDF | Weitere Formate |
| UI | Streamlit Web-UI (3 produktive Tabs, 4. Tab `Organisation` als naechster Ausbauschritt vorgesehen) | CLI-Review |
| Review | Tab 2 im Web-UI | Externes Ticketing |
| Lauf-Modi | Initial, Full Update, Delta Update | Parallele Agent-Pipeline |
| Query-Layer | Tab 1 (NL -> Cypher -> Antwort) | Schreibender Query-Layer |
| Deployment | Lokal / Docker | Cloud-Deployment der Anwendung |

Wichtige Einordnung:
Die Spezifikation oeffnet den fachlichen Scope fuer unstrukturierte Prozessbeschreibungen. Die aktuelle Implementierung ist weiterhin BPMN-first, unterstuetzt aber inzwischen auch einen transformierten Importpfad fuer sehr grosse BPMN/XML-Dateien.

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

Fuer v0.13 gilt als Zielregel:

- `rolle` wird immer aus der Prozessquelle uebernommen, wenn ein verantwortlicher Akteur oder eine Lane-Bezeichnung vorliegt
- `org_einheit` wird nur dann gesetzt, wenn die Bezeichnung 1:1 gegen eine gepflegte Liste bekannter Organisationseinheiten gematcht werden kann
- bei einem 1:1-Match duerfen `rolle` und `org_einheit` gleichzeitig denselben Wert tragen
- ohne Match bleibt `org_einheit` leer
- moegliche Organisationseinheiten aus Prozessdokumenten duerfen im ersten Wurf nur als Kandidaten gesammelt werden und fliessen nicht direkt als `org_einheit` in den produktiven Graph

Diese Trennung ist bewusst konservativ, um Rollen nicht faelschlich als Organisationseinheiten in den Graph zu schreiben.

---

## 6. Pipeline

Die Pipeline bleibt sequentiell. Geschwindigkeit ist gegenueber Korrektheit, Transparenz und Wiederholbarkeit nachrangig.

### 6.1 Projektstruktur

```text
bridgr/
├── prompts/
│   ├── extract_bpmn.md
│   ├── extract_generic.md
│   ├── match_fuzzy.md
│   ├── process_identity.md
│   └── cypher_gen.md
├── skills/
│   ├── extract/
│   │   ├── extract_base.py
│   │   ├── extract_bpmn.py
│   │   ├── extract_pdf.py
│   │   ├── extract_docx.py
│   │   └── extract_txt.py
│   ├── identity.py
│   ├── match.py
│   ├── review.py
│   └── graph_writer.py
├── knowledge_base/
├── Input/
├── Output/
├── data/
├── config.json
├── app.py
└── main.py
```

### 6.2 Extraktion

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

#### Warum kein fachlicher Extraktor fuer TXT, DOCX und PDF?

Bei leistungsfaehigen OpenAI-kompatiblen Modellen ist der Mehrwert eines zusaetzlichen semantischen Parsers gering. Der relevante Unterschied zwischen den Formaten liegt primär darin, wie ihr Text gewonnen wird, nicht darin, wie ihre Prozesssemantik modelliert ist.

Diese Entscheidung gilt bewusst fuer den Ausbaupfad mit starken Webmodellen. Fuer kleinere lokale Modelle kann spaeter eine staerkere Vorstrukturierung sinnvoll werden; fuer grosse BPMN/XML-Dateien wird diese Vorstrukturierung in v0.13 nun gezielt ueber den Transformer abgedeckt.

#### Extraktionssichten

Fuer Anwendungen bleiben zwei Sichten bestehen:

- `raw_applications`:
  rohe Varianten aus dem LLM-Output fuer Transparenz und UI-Hinweise
- `applications`:
  bereinigte und deduplizierte Arbeitssicht fuer Matching, Review und Graph-Schreiben

#### Output-Schema

```json
{
  "prozess": "Auftragsabwicklung",
  "prozess_id": "proc_001",
  "org_einheit": "Vertrieb",
  "folgt_auf": ["Angebotserstellung"],
  "anwendungen": [
    { "name": "SAP SD", "konfidenz": "stark" },
    { "name": "das Planungssystem", "konfidenz": "schwach" }
  ]
}
```

#### Fehlerbehandlung

- Kaputte oder ungueltige BPMN-Dateien werden als Dokumentfehler markiert
- Fehler in der Textgewinnung aus TXT, DOCX oder PDF werden ebenfalls als Dokumentfehler markiert
- Ungueltiges LLM-JSON wird mit Retry behandelt; danach wird das Dokument als Fehler markiert
- OpenAI-kompatible JSON-Ausgabe wird technisch ueber `response_format=json_object` plus nachgelagerte Strukturpruefung abgesichert

---

## 7. Prozessidentitaet

- BPMN:
  `process id` aus dem XML bleibt die primaere stabile Identitaet
- Transformierte BPMN-TXT-Dateien:
  eine explizit enthaltene `Process ID:` wird als Quellwert technisch bevorzugt und nicht dem LLM ueberlassen
- Unstrukturierte Formate:
  LLM-basiertes Namens-Matching bleibt der vorgesehene spaetere Weg

`skills/identity.py` bleibt in der aktuellen Implementierung bewusst ein v1/v0.13-Stub fuer BPMN-orientierte Identitaet.

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
- weitergehende Quellen wie Organigramme, Bilder, SVG, BPMN-Modelle oder OCR-basierte Ableitungen bleiben moegliche spaetere Erweiterungen, sind aber nicht Voraussetzung fuer den Basisbetrieb

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

Vor dem Neuschreiben der `NUTZT`-Beziehungen eines Prozesses werden bestehende `NUTZT`-Kanten dieses Prozesses entfernt.

Wichtige Ergaenzung in v0.13:
Nicht mehr extrahierte Anwendungen werden bei Full- oder Delta-Updates nicht durch normale bestaetigte KB-Links automatisch wiederbelebt. Nur explizite manuelle Zusatzlinks duerfen weiterhin ausserhalb des aktuellen Extrakts fortgeschrieben werden.

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
- Laufmodus

Mit v0.13 gilt zusaetzlich:

- der Input-Pfad ist fachlich ein gemeinsamer Ablageort fuer mehrere Dokumenttypen
- verarbeitet werden im UI-Lauf die explizit ausgewaehlten Prozessdateien
- transformierte BPMN-Dateien koennen direkt aus dem UI erzeugt und anschliessend gezielt importiert werden

Geplanter naechster UI-Ausbau:

- ein zusaetzlicher Tab `Organisation`
- dort pflegt der Benutzer im ersten Wurf manuell bekannte Organisationseinheiten
- diese Liste dient als Referenz fuer den konservativen 1:1-Abgleich zwischen extrahierter `rolle` und `org_einheit`
- derselbe Tab enthaelt zusaetzlich einen Bereich `Kandidaten`, in dem moegliche Organisationseinheiten aus Prozessdokumenten gesammelt werden
- fuer Kandidaten sind im ersten Wurf drei Aktionen vorgesehen: auf bestehende Organisationseinheit mappen, als neue Organisationseinheit uebernehmen oder abweisen
- erst nach einer solchen Benutzerentscheidung duerfen Kandidaten Einfluss auf `org_einheit` im produktiven Graph nehmen
- die Pflege ueber Importe aus Organigrammen oder anderen Quellen bleibt ausdruecklich als spaetere Erweiterung offen

---

## 12. Ausbau-Reihenfolge fuer unstrukturierte Formate

Die fachliche Freigabe fuer unstrukturierte Prozessbeschreibungen bedeutet nicht, dass alle Formate gleichzeitig implementiert werden muessen.

Empfohlene Reihenfolge:

1. TXT
2. DOCX
3. PDF

Begruendung:

- TXT hat praktisch keine technische Vorverarbeitung
- DOCX braucht nur kontrollierte Textgewinnung
- PDF ist typischerweise am unruhigsten in Layout und Textqualitaet

---

## 13. Akzeptanzkriterien

1. Korrekte Informationen aus den Quelldaten koennen ueber die Weboberflaeche abgefragt werden
2. Mappings sind ueber die Weboberflaeche pflegbar
3. Informationen zu Prozessen und Anwendungen koennen ueber die Weboberflaeche abgerufen werden
4. Die Pipeline laeuft stabil durch einen vollstaendigen Importzyklus
5. Der Ausbau auf TXT, DOCX und PDF folgt demselben gemeinsamen semantischen Extraktionsschema
6. Grosse BPMN/XML-Dateien koennen ueber den Transformationspfad in prozessweise, stabile Importeinheiten ueberfuehrt werden

---

## 14. Getroffene Entscheidungen

| Entscheidung | Gewaehlt | Verworfen | Begruendung |
|---|---|---|---|
| BPMN-Extraktion | LLM liest XML als Rohtext, bei grossen Modellen optional nach LLM-freier Vortransformation | Dedizierter XML-Parser + LLM-Layer als Pflichtpfad | BPMN ist strukturierter Text; fuer grosse Enterprise-Dateien reduziert der Transformationsschritt gezielt das XML-Rauschen, ohne die Pipeline fachlich neu zu modellieren. |
| BPMN-Vorreduktion | Pro `<process>` genau eine kompakte Transform-Datei | Eine Sammeldatei fuer die gesamte BPMN | Eine Datei pro Prozess passt besser zum bestehenden Extraktionsschema, verbessert Fehlerisolation und reduziert Promptgroesse. |
| Unstrukturierte Formate | Nur Textgewinnung plus gemeinsamer LLM-Extraktionsschritt | Format-spezifische fachliche Parser fuer TXT, DOCX oder PDF | Der semantische Kern liegt im Modell und im Prompt, nicht in pro Format unterschiedlicher Fachlogik. |
| Extrahierte Anwendungen | Zwei Sichten: `raw_applications` und deduplizierte `applications` | Fruehes Verwerfen der Rohvarianten | Die Rohsicht bleibt fuer Transparenz und UI-Hinweise wichtig, die deduplizierte Sicht stabilisiert Matching und Graph-Schreiben. |
| Lane-/Akteursbezeichnungen | Zunaechst immer als `rolle`, `org_einheit` nur bei 1:1-Match gegen gepflegte Referenzliste | Direkte Ableitung `Lane = OrgEinheit` oder fruehes Fuzzy-/Vision-Mapping | Rollen und Organisationseinheiten duerfen fachlich nicht vermischt werden; der erste Wurf bleibt konservativ und erzwingt kein spezielles Quellformat fuer Organigramme. |
| Dokumenthinweise auf moegliche OrgEinheiten | Als Kandidatenliste in Tab 4 sammeln, aber nicht direkt in `org_einheit` uebernehmen | Direkte automatische Uebernahme freier Dokumentaussagen als OrgEinheit | Die kuratierte Referenzliste bleibt die einzige produktive Wahrheit fuer `org_einheit`; Dokumente duerfen nur Vorschlaege liefern. |
| Schwache Matches im Graph | Nicht automatisch schreiben; erst nach Bestaetigung oder KB-Eintrag | Sofortiges Schreiben aller fuzzy-Kandidaten | Der Query-Layer soll nur freigegebenes Wissen sehen. |
| LLM-Anbindung | OpenAI-kompatible Schnittstelle mit frei konfigurierbarer Base-URL plus JSON-Haertung | Feste lokale Laufzeitkopplung oder rein promptbasierte JSON-Disziplin | Prompt- und Pipeline-Logik bleiben gleich, egal ob lokal oder ueber Webprovider gearbeitet wird; formale JSON-Stabilitaet braucht zusaetzliche technische Absicherung. |
| Importsteuerung im UI | Explizite Dateiauswahl fuer den Lauf | Stilles Verarbeiten des kompletten `input_path` | Der Input-Ordner soll Orientierung geben, aber die Verarbeitungseinheit muss fuer den Benutzer explizit und kontrollierbar bleiben. |

---

*Bridgr | Architektur v0.13 | Stand Mai 2026*

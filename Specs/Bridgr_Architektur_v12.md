# Bridgr
**Architektur & Konzept** | Stand: Mai 2026 | v0.12

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
  Prozessdokumente + CMDB -> Extraktion -> Matching -> Review -> Graph-DB
- Abfrage-Layer:
  Web-UI -> LLM -> Cypher -> Neo4j -> Antwort in natuerlicher Sprache

Die Pipeline bleibt sequentiell, nachvollziehbar und idempotent.

---

## 3. Inputs

- Prozessdokumente:
  BPMN sowie unstrukturierte Prozessbeschreibungen als TXT, DOCX oder PDF
- CMDB-Export:
  CSV oder Excel; das benoetigte Spaltenmapping wird in Tab 3 gepflegt

---

## 4. Scope v0.12

| Bereich | In Scope | Out of Scope |
|---|---|---|
| Eingabeformate | BPMN, TXT, DOCX, PDF | Weitere Formate |
| UI | Streamlit Web-UI (3 Tabs) | CLI-Review |
| Review | Tab 2 im Web-UI | Externes Ticketing |
| Lauf-Modi | Initial, Full Update, Delta Update | Parallele Agent-Pipeline |
| Query-Layer | Tab 1 (NL -> Cypher -> Antwort) | Schreibender Query-Layer |
| Deployment | Lokal / Docker | Cloud-Deployment der Anwendung |

Wichtige Einordnung:
Die Spezifikation oeffnet den fachlichen Scope fuer unstrukturierte Prozessbeschreibungen. Die aktuelle Implementierung ist weiterhin BPMN-first und wird schrittweise erweitert.

---

## 5. Domaenenmodell

### Prozess

Ein Prozess entspricht bei BPMN einem `<process>`-Element. Bei unstrukturierten Formaten wird der vom LLM extrahierte oder spaeter gematchte Prozessname als fachlicher Bezugspunkt verwendet.

### folgt_auf

Bei BPMN wird die Beziehung aus dem modellierten Sequenzzusammenhang zwischen Prozessen abgeleitet. Bei unstrukturierten Formaten kann `folgt_auf` nur dann befuellt werden, wenn die Beschreibung dies explizit oder hinreichend klar hergibt.

### Anwendung

Eine Anwendung ist ein in der CMDB gefuehrtes System. Pflichtfelder in Bridgr bleiben UUID und Name. Im Graph wird nur die Referenz `cmdb_id` plus der Anzeigename der Anwendung gehalten.

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

Bridgr trennt stattdessen zwei Dinge:

- technische Textgewinnung pro Format
- gemeinsame semantische Extraktion ueber das LLM

Das bedeutet:

- BPMN:
  rohes XML direkt an das Modell
- TXT:
  Text direkt an das Modell
- DOCX:
  Text aus dem Dokument gewinnen, dann an das Modell
- PDF:
  Text aus dem Dokument gewinnen, dann an das Modell

Die eigentliche Fachintelligenz bleibt im Prompt und im gemeinsamen Ausgabeschema, nicht in format-spezifischer Parserlogik.

#### Warum kein fachlicher Extraktor fuer TXT, DOCX und PDF?

Bei leistungsfaehigen OpenAI-kompatiblen Modellen ist der Mehrwert eines zusaetzlichen semantischen Parsers gering. Der relevante Unterschied zwischen den Formaten liegt primär darin, wie ihr Text gewonnen wird, nicht darin, wie ihre Prozesssemantik modelliert ist.

Diese Entscheidung gilt bewusst fuer den Ausbaupfad mit starken Webmodellen. Fuer kleinere lokale Modelle kann spaeter eine staerkere Vorstrukturierung sinnvoll werden, ist aber in v0.12 nicht vorgesehen.

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

---

## 7. Prozessidentitaet

- BPMN:
  `process id` aus dem XML bleibt die primaere stabile Identitaet
- Unstrukturierte Formate:
  LLM-basiertes Namens-Matching bleibt der vorgesehene spaetere Weg

`skills/identity.py` bleibt in der aktuellen Implementierung bewusst ein v1/v0.12-Stub fuer BPMN-orientierte Identitaet.

---

## 8. Matching und Review

Die Reihenfolge bleibt:

1. Knowledge Base
2. Fuzzy Matching
3. optional spaeterer LLM-Fallback fuer unklare Matching-Faelle

Schwache Kandidaten bleiben reviewbar und werden nicht automatisch in den Graph geschrieben.

Die primaere Arbeitsflaeche fuer den Benutzer bleibt die Review-Liste in Tab 2. Mehrfachkandidaten pro Prozessanwendung sind weiterhin erlaubt.

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

Vor dem Neuschreiben der `NUTZT`-Beziehungen eines Prozesses werden bestehende `NUTZT`-Kanten dieses Prozesses entfernt, damit keine veralteten schwachen Altlinks im Graph verbleiben.

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

Mit v0.12 muss der Input-Pfad fachlich fuer mehrere Dokumenttypen gedacht werden, nicht mehr nur fuer BPMN/XML.

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

---

## 14. Getroffene Entscheidungen

| Entscheidung | Gewaehlt | Verworfen | Begruendung |
|---|---|---|---|
| BPMN-Extraktion | LLM liest XML als Rohtext | Dedizierter XML-Parser + LLM-Layer | BPMN ist strukturierter Text; ein zusaetzlicher Parser-Layer bringt fuer den Zielpfad keinen entscheidenden Mehrwert. |
| Unstrukturierte Formate | Nur Textgewinnung plus gemeinsamer LLM-Extraktionsschritt | Format-spezifische fachliche Parser fuer TXT, DOCX oder PDF | Der semantische Kern liegt im Modell und im Prompt, nicht in pro Format unterschiedlicher Fachlogik. |
| Extrahierte Anwendungen | Zwei Sichten: `raw_applications` und deduplizierte `applications` | Fruehes Verwerfen der Rohvarianten | Die Rohsicht bleibt fuer Transparenz und UI-Hinweise wichtig, die deduplizierte Sicht stabilisiert Matching und Graph-Schreiben. |
| Schwache Matches im Graph | Nicht automatisch schreiben; erst nach Bestaetigung oder KB-Eintrag | Sofortiges Schreiben aller fuzzy-Kandidaten | Der Query-Layer soll nur freigegebenes Wissen sehen. |
| LLM-Anbindung | OpenAI-kompatible Schnittstelle mit frei konfigurierbarer Base-URL | Feste lokale Laufzeitkopplung | Prompt- und Pipeline-Logik bleiben gleich, egal ob lokal oder ueber Webprovider gearbeitet wird. |

---

*Bridgr | Architektur v0.12 | Stand Mai 2026*

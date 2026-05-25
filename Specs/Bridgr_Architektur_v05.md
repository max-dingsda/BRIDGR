# Bridgr
**Architektur & Konzept** | Stand: Juni 2026 | v0.5

---

## 1. Ziel

Prozessdokumentation und CMDB-Export zusammenführen, um einen EA-Wissensgraphen aufzubauen — und diesen über eine natürlichsprachliche Web-Oberfläche abfragbar zu machen.

> **Kernfrage:** Welche IT-Anwendungen unterstützen welche Geschäftsprozesse — und wie sicher wissen wir das?

Das Tool schließt die Lücke, die klassische IT-Discovery-Tools offen lassen: sie kennen die IT-Landschaft, aber nicht den Business-Kontext. Dieser fehlt, weil er nur in Prozessdokumentationen steht — und dort in unstrukturierter, menschlicher Sprache.

---

## 2. Gesamtarchitektur

Das System besteht aus zwei klar getrennten Schichten:

```
┌─────────────────────────────────────────┐
│           PIPELINE (Befüllung)          │
│  Prozessdoks + CMDB → Extraktion →     │
│  Matching → Review → Graph-DB           │
└─────────────────────┬───────────────────┘
                      │
                 Neo4j Graph-DB
                      │
┌─────────────────────┴───────────────────┐
│         ABFRAGE-LAYER (Nutzung)         │
│  Web-UI → LLM → Cypher-Query →         │
│  Neo4j → Antwort in natürlicher Sprache │
└─────────────────────────────────────────┘
```

---

## 3. Inputs

- Prozessdokumente — Ordner mit beliebigen Formaten (PDF, DOCX, TXT, BPMN)
- CMDB-Export — CSV oder Excel mit der offiziellen Applikationsliste

---

## 4. Pipeline

Der Ablauf ist sequenziell — kein Agent-Framework, keine Parallelisierung. EA-Inventarisierung ist nicht zeitkritisch; Korrektheit und Nachvollziehbarkeit sind wichtiger als Geschwindigkeit.

### 4.1 Projektstruktur

```
ea-mapper/
├── prompts/
│   ├── extract_generic.md      # für PDF, DOCX, TXT
│   ├── extract_bpmn.md         # speziell für BPMN-Annotationen
│   ├── match_fuzzy.md          # Fuzzy-Matching-Entscheidung
│   └── cypher_gen.md           # Prompt für LLM → Cypher-Übersetzung
├── skills/
│   ├── extract/
│   │   ├── extract_base.py     # gemeinsames Interface + Output-Schema, lädt Prompts zur Laufzeit
│   │   ├── extract_pdf.py
│   │   ├── extract_docx.py
│   │   ├── extract_bpmn.py     # Parser-Layer + LLM-Layer
│   │   └── extract_txt.py
│   ├── match.py                # JSON → CMDB-Abgleich
│   ├── review.py               # schwache Links zur Review vorbereiten
│   └── graph_writer.py         # schreibt Knoten und Kanten in Neo4j
├── knowledge_base/
│   └── kb.json                 # persistierte menschliche Entscheidungen
├── data/
│   ├── input/                  # Prozessdokumente
│   └── cmdb.csv                # CMDB-Export
├── app.py                      # Streamlit Web-UI (Abfrage-Layer)
└── main.py                     # orchestriert die Pipeline sequenziell
```

### 4.2 Komponenten

#### Extractor (`skills/extract/`)

Pro Dateiformat ein eigener Extractor-Skill. Alle teilen dasselbe Output-Schema (`extract_base.py`), so dass `main.py` nur die Dateiendung prüft und zum richtigen Extractor routet.

Die eigentliche Intelligenz steckt nicht im Python-Code, sondern in den Prompts. Python liest die Datei, lädt den passenden Prompt aus `prompts/`, befüllt den Platzhalter mit dem Dokumentinhalt und schickt alles ans LLM. Was das LLM daraus macht — also welche Anwendungen es erkennt, auch implizite wie "das System" oder "die Datenbank" — ist Sache des Prompts, nicht des Codes.

```python
# Prinzip in extract_base.py
prompt_template = open("prompts/extract_generic.md").read()
prompt = prompt_template.replace("{{TEXT}}", dokument_inhalt)
# → ans LLM schicken (Ollama)
```

Prompts können damit gepflegt, getauscht und getestet werden ohne den Code anzufassen.

| Format | Methode | Hinweis |
|---|---|---|
| PDF, DOCX, TXT | LLM (Ollama) | Semantische Extraktion via lokalem Modell (Gemma/Qwen/Mistral) |
| BPMN | Parser + LLM | XML-Parser für Datenspeicher & Service Tasks (stark); LLM für Annotationen (schwach) |
| Weitere Formate | Erweiterbar | Neues `extract_xyz.py` anlegen — Rest bleibt unberührt |

LLM-Output-Schema (JSON) pro Dokument:

```json
{
  "prozess": "Auftragsabwicklung",
  "org_einheit": "Vertrieb",
  "folgt_auf": "Angebotserstellung",
  "anwendungen": [
    { "name": "SAP SD",             "konfidenz": "stark"   },
    { "name": "das Planungssystem", "konfidenz": "schwach" }
  ]
}
```

#### Matcher (`skills/match.py`)

Gleicht die extrahierten Anwendungsnamen gegen den CMDB-Export ab. Reihenfolge:

1. **Knowledge Base zuerst** — bereits validierte Entscheidungen haben Vorrang
2. **Fuzzy Matching** — für ähnliche aber nicht identische Bezeichnungen
3. **LLM-Fallback** — für unklare Fälle, die noch nicht in der KB stehen

#### Konfidenz-Level

| Level | Bedeutung | Beispiel |
|---|---|---|
| ⬛ Stark | Explizit im Text genannt | "Daten werden in SAP SD erfasst" |
| ▨ Schwach | Implizit / interpretiert | "das System schickt eine Bestätigung" |
| □ Kein Match | Keine Softwarereferenz gefunden | — |

#### Knowledge Base (`knowledge_base/kb.json`)

Persistiert alle menschlichen Entscheidungen über Läufe hinweg. Enthält:

- Bestätigte Links (schwach → stark hochgestuft)
- Verworfene Links
- Manuelle Ergänzungen mit Kontext
- Disambiguierungsregeln — z.B. `"Adobe"` + Prozess `"Lieferscheindruck"` → Adobe Reader

> **Lerneffekt:** Bei jedem Folgelauf wird die KB zuerst konsultiert. Das System wird mit der Zeit treffsicherer — nicht durch Modelltraining, sondern durch akkumuliertes menschliches Wissen.

#### Review-Interface (`skills/review.py`)

Der Mensch sieht alle schwachen Links und offenen Matches und kann:

- ✓ bestätigen
- ✗ verwerfen
- \+ manuell verknüpfen und Kontext ergänzen (Prozess, Hinweis)

#### Graph Writer (`skills/graph_writer.py`)

Schreibt das validierte Inventar als Knoten und Kanten in Neo4j:

```cypher
(:OrgEinheit)-[:VERANTWORTET]->(:Prozess)
(:Prozess)-[:FOLGT_AUF]->(:Prozess)
(:Prozess)-[:NUTZT {konfidenz: "stark"}]->(:Anwendung {cmdb_id: "..."})
```

Die technische Infrastruktur wird **nicht** in den Graphen kopiert — die Anwendung trägt nur die CMDB-ID als Attribut. Die technische Sicht bleibt in der CMDB als Single Source of Truth.

---

## 5. Graph-Datenmodell

```
(OrgEinheit) -[:VERANTWORTET]-> (Prozess)
(Prozess)    -[:FOLGT_AUF]->    (Prozess)
(Prozess)    -[:NUTZT]->        (Anwendung)
(Anwendung)                     { cmdb_id, name, konfidenz }
```

| Beziehung | Quelle |
|---|---|
| OrgEinheit → Prozess | Prozessdokument / BPMN Swimlane |
| Prozess → Prozess | Prozessdokument / BPMN Sequenzfluss |
| Prozess → Anwendung | LLM-Extraktion + KB |
| Anwendung → Infrastruktur | CMDB (nur Referenz via cmdb_id) |

---

## 6. Abfrage-Layer

```
Benutzer → Web-UI (Streamlit, 3 Tabs) → LLM / Neo4j
```

Das Web-UI ist in drei Tabs gegliedert — kein Anfassen von Config-Files nötig.

---

### Tab 1 — Kommunikation

Der Benutzer stellt Fragen in natürlicher Sprache. Das LLM übersetzt die Frage in eine Cypher-Query, holt die Daten aus Neo4j und formuliert eine verständliche Antwort.

```
[ Frage eingeben                    ] [Senden]

──────────────────────────────────────────────
Antwort:

SAP SD wird in 4 Prozessen genutzt:
Auftragsabwicklung, Retoure, Fakturierung
und Gutschriftverfahren.
```

---

### Tab 2 — Link Editing

Übersicht aller schwachen Links und offenen Matches. Der Benutzer kann:

- ✓ bestätigen (schwach → stark)
- ✗ löschen
- ✎ korrigieren (z.B. falsch erkannte Anwendung korrigieren)
- \+ manuellen Link anlegen (Prozess → Anwendung, die das LLM nicht erkannt hat)

Bestätigte und korrigierte Links werden automatisch in die Knowledge Base geschrieben und beim nächsten Lauf berücksichtigt.

---

### Tab 3 — Anwendungskonfig

Konfiguration der Anwendung — kein Anfassen von Config-Files nötig.

**Input**
- Pfad zum Prozessdok-Ordner
- Pfad zur CMDB-Datei

**LLM**
- Ollama-URL (z.B. `http://localhost:11434`)
- Modell-Auswahl — Dropdown, dynamisch befüllt via `GET /api/tags` gegen die konfigurierte Ollama-URL
- Refresh-Button — aktualisiert die Modellliste zur Laufzeit (z.B. nach `ollama pull`)

**Graph-DB**
- Neo4j-URL
- User / Passwort

**Pipeline**
- Lauf-Modus: Initial oder Delta
- Pipeline starten

---

## 7. Lauf-Modi

### Initial
Erster Lauf, Knowledge Base leer. Alle Dokumente werden verarbeitet.

- Link stark → automatisch bestätigt
- Link schwach → ins Review

### Full Update
Alle Dokumente werden neu verarbeitet, Graph wird neu aufgebaut. KB-Einträge fließen in die Bewertung ein.

- Link war bestätigt + LLM findet ihn wieder → automatisch bestätigt
- Link war bestätigt + LLM findet ihn nicht mehr → ins Review mit Hinweis "war bestätigt, nicht mehr gefunden"
- Link neu + stark → automatisch bestätigt
- Link neu + schwach → ins Review

### Delta Update
Nur die übergebenen Dokumente werden neu verarbeitet. Der Rest des Graphen bleibt unangetastet. Gleiche Bewertungslogik wie Full Update, aber nur für die betroffenen Prozesse.

---

## 8. Differenzierung

> **vs. Discovery-Tools:** Discovery-Tools (ServiceNow, Dynatrace etc.) kennen die IT-Landschaft — Systeme, Verbindungen, Abhängigkeiten. Sie wissen aber nicht, warum ein System existiert oder welchen Prozess es unterstützt. Dieser Business-Kontext steckt in Prozessdokumentationen und ist nur durch menschliches Lesen zugänglich.

> **Qualitätsspiegel:** Fehlende Links im Output zeigen direkt, wo die Prozessdokumentation löchrig ist. Das Tool liefert damit nicht nur ein Inventar, sondern auch eine Dokumentationsqualitäts-Analyse als Nebenprodukt.

> **Lernender Layer:** Im Gegensatz zu reinen Scan-Tools lernt dieses System durch menschliche Eingabe. Disambiguation-Regeln und bestätigte Links akkumulieren sich über Zeit — der manuelle Review-Aufwand nimmt mit jedem Lauf ab.

---

## 9. Offene Punkte

- LLM-Modellwahl für Extraktion: Gemma vs. Qwen vs. Mistral — Qualitätsvergleich ausstehend
- LLM-Modellwahl für Cypher-Generierung: ggf. anderes Modell als für Extraktion sinnvoll
- BPMN-Varianten: Swimlanes, Datenspeicher, Annotationen — Testdaten fehlen noch
- Normalisierung: Wie aggressiv soll Fuzzy Matching sein?
- Review-Interface: CLI für PoC, Web-UI als spätere Option

---

*Bridgr | Architektur v0.5 | Stand Juni 2026*

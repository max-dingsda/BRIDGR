# Bridgr
**Architektur & Konzept** | Stand: Mai 2026 | v0.6

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

- **Prozessdokumente** — Ordner mit BPMN-Dateien (v1); PDF, DOCX, TXT folgen in späteren Versionen
- **CMDB-Export** — CSV oder Excel; Spaltenmapping wird einmalig in Tab 3 konfiguriert (CMDB-agnostisch)

---

## 4. MVP-Scope (v1)

| Bereich | In Scope | Out of Scope |
|---|---|---|
| Eingabeformate | BPMN | PDF, DOCX, TXT |
| UI | Streamlit Web-UI (alle 3 Tabs) | — |
| Review | Tab 2 im Web-UI | CLI |
| Lauf-Modi | Initial, Full Update, Delta Update | — |
| Query-Layer | Tab 1 (NL → Cypher → Antwort) | — |
| Deployment | Lokal / Docker | Cloud |

---

## 5. Pipeline

Der Ablauf ist sequenziell — kein Agent-Framework, keine Parallelisierung. EA-Inventarisierung ist nicht zeitkritisch; Korrektheit und Nachvollziehbarkeit sind wichtiger als Geschwindigkeit.

Die Pipeline ist **idempotent** — ein abgebrochener Lauf kann jederzeit sicher neu gestartet werden. Bereits verarbeitete Dokumente werden anhand eines Datei-Hashes erkannt und übersprungen.

### 5.1 Projektstruktur

```
bridgr/
├── prompts/
│   ├── extract_bpmn.md         # LLM-Layer für BPMN-Annotationen
│   ├── extract_generic.md      # für PDF, DOCX, TXT (spätere Versionen)
│   ├── match_fuzzy.md          # Fuzzy-Matching-Entscheidung
│   └── cypher_gen.md           # Prompt für LLM → Cypher-Übersetzung
├── skills/
│   ├── extract/
│   │   ├── extract_base.py     # gemeinsames Interface + Output-Schema, lädt Prompts zur Laufzeit
│   │   ├── extract_bpmn.py     # Parser-Layer (XML) + LLM-Layer (Annotationen)
│   │   ├── extract_pdf.py      # spätere Version
│   │   ├── extract_docx.py     # spätere Version
│   │   └── extract_txt.py      # spätere Version
│   ├── match.py                # JSON → CMDB-Abgleich
│   ├── review.py               # schwache Links für Tab 2 aufbereiten
│   └── graph_writer.py         # schreibt Knoten und Kanten in Neo4j
├── knowledge_base/
│   └── kb.json                 # persistierte menschliche Entscheidungen
├── data/
│   ├── input/                  # Prozessdokumente
│   └── cmdb.csv                # CMDB-Export
├── app.py                      # Streamlit Web-UI
└── main.py                     # orchestriert die Pipeline sequenziell
```

### 5.2 Komponenten

#### Extractor (`skills/extract/`)

Pro Dateiformat ein eigener Extractor-Skill. Alle teilen dasselbe Output-Schema (`extract_base.py`), so dass `main.py` nur die Dateiendung prüft und zum richtigen Extractor routet.

Die eigentliche Intelligenz steckt nicht im Python-Code, sondern in den Prompts. Python liest die Datei, lädt den passenden Prompt aus `prompts/`, befüllt den Platzhalter mit dem Dokumentinhalt und schickt alles ans LLM.

```python
# Prinzip in extract_base.py
prompt_template = open("prompts/extract_bpmn.md").read()
prompt = prompt_template.replace("{{TEXT}}", dokument_inhalt)
# → ans LLM schicken (Ollama)
```

**BPMN-Besonderheit:** zwei Extraktionsebenen:
- **Parser-Layer** — XML direkt parsen: Datenspeicher, Service Tasks, Swimlanes → liefert starke Links
- **LLM-Layer** — Annotationen und Beschreibungsfelder semantisch auswerten → liefert schwache Links

| Format | Methode | v1 |
|---|---|---|
| BPMN | Parser + LLM | ✓ |
| PDF, DOCX, TXT | LLM (Ollama) | spätere Version |

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

**Leere Extraktion:** Liefert das LLM keine Anwendungen, wird das Dokument als `verarbeitet — keine Treffer` markiert und in Tab 2 sichtbar gemacht. Kein stillschweigendes Überspringen.

#### Matcher (`skills/match.py`)

Gleicht die extrahierten Anwendungsnamen gegen den CMDB-Export ab. Reihenfolge:

1. **Knowledge Base zuerst** — bereits validierte Entscheidungen haben Vorrang
2. **Fuzzy Matching** — Levenshtein-Score, Schwellenwert konfigurierbar in Tab 3 (Default: 0.85)
3. **LLM-Fallback** — für unklare Fälle, die noch nicht in der KB stehen

**CMDB-Agnostik:** Pflichtfelder sind UUID und Name. Die tatsächlichen Spaltennamen werden einmalig in Tab 3 gemappt (z.B. `app_id` → UUID, `application_name` → Name). Der Matcher arbeitet intern immer mit den gemappten Feldern.

#### Konfidenz-Level

| Level | Bedeutung | Beispiel |
|---|---|---|
| ⬛ Stark | Explizit im Text / strukturiert im BPMN | "Daten werden in SAP SD erfasst" |
| ▨ Schwach | Implizit / interpretiert | "das System schickt eine Bestätigung" |
| □ Kein Match | Keine Softwarereferenz gefunden | — |

#### Knowledge Base (`knowledge_base/kb.json`)

Persistiert alle menschlichen Entscheidungen über Läufe hinweg.

```json
{
  "confirmed": [
    {
      "prozess": "Auftragsabwicklung",
      "anwendung_name": "SAP SD",
      "cmdb_id": "uuid-1234",
      "bestaetigt_am": "2026-05-23",
      "quelle": "manuell"
    }
  ],
  "rejected": [
    {
      "prozess": "Reklamation",
      "anwendung_name": "das Planungssystem",
      "abgelehnt_am": "2026-05-23"
    }
  ],
  "disambiguation": [
    {
      "name": "Adobe",
      "prozess": "Lieferscheindruck",
      "resolved_to": "Adobe Reader",
      "cmdb_id": "uuid-5678"
    }
  ]
}
```

> **Wiederholte Ablehnung:** Ein einmal abgelehnter Link gilt dauerhaft als abgelehnt und landet nicht erneut im Review. Er kann in Tab 2 reaktiviert werden.

> **Lerneffekt:** Bei jedem Folgelauf wird die KB zuerst konsultiert. Das System wird mit der Zeit treffsicherer — nicht durch Modelltraining, sondern durch akkumuliertes menschliches Wissen.

#### Graph Writer (`skills/graph_writer.py`)

Schreibt das validierte Inventar als Knoten und Kanten in Neo4j (lokal oder Docker):

```cypher
(:OrgEinheit)-[:VERANTWORTET]->(:Prozess)
(:Prozess)-[:FOLGT_AUF]->(:Prozess)
(:Prozess)-[:NUTZT {konfidenz: "stark"}]->(:Anwendung {cmdb_id: "...", name: "..."})
```

Die technische Infrastruktur wird **nicht** in den Graphen kopiert — die Anwendung trägt nur die CMDB-ID als Attribut. Die technische Sicht bleibt in der CMDB als Single Source of Truth.

---

## 6. Graph-Datenmodell

```
(OrgEinheit) -[:VERANTWORTET]-> (Prozess)
(Prozess)    -[:FOLGT_AUF]->    (Prozess)
(Prozess)    -[:NUTZT]->        (Anwendung)
(Anwendung)                     { cmdb_id, name }
```

| Beziehung | Quelle |
|---|---|
| OrgEinheit → Prozess | BPMN Swimlane |
| Prozess → Prozess | BPMN Sequenzfluss |
| Prozess → Anwendung | LLM-Extraktion + KB |
| Anwendung → Infrastruktur | CMDB (nur Referenz via cmdb_id) |

---

## 7. Abfrage-Layer

```
Benutzer → Web-UI (Streamlit, 3 Tabs) → LLM / Neo4j
```

Das Web-UI ist in drei Tabs gegliedert — von Anfang an als Web-Oberfläche, kein CLI.

---

### Tab 1 — Kommunikation

Der Benutzer stellt Fragen in natürlicher Sprache. Das LLM (dasselbe Modell wie für die Extraktion) übersetzt die Frage via `cypher_gen.md`-Prompt in eine Cypher-Query, holt die Daten aus Neo4j und formuliert eine verständliche Antwort.

```
[ Frage eingeben                    ] [Senden]

──────────────────────────────────────────────
Antwort:

SAP SD wird in 4 Prozessen genutzt:
Auftragsabwicklung, Retoure, Fakturierung
und Gutschriftverfahren.
```

Fehlerhafte oder leere Query-Ergebnisse werden dem Benutzer transparent kommuniziert ("Keine Treffer gefunden" / "Abfrage konnte nicht ausgeführt werden").

---

### Tab 2 — Link Editing

Übersicht aller schwachen Links, offenen Matches und Dokumente ohne Treffer. Der Benutzer kann:

- ✓ bestätigen (schwach → stark, wird in KB geschrieben)
- ✗ ablehnen (dauerhaft, reaktivierbar)
- ✎ korrigieren (falsch erkannte Anwendung anpassen)
- \+ manuellen Link anlegen (Prozess → Anwendung, die das LLM nicht erkannt hat)

---

### Tab 3 — Anwendungskonfig

Konfiguration der Anwendung — kein Anfassen von Config-Files nötig.

**Input**
- Pfad zum Prozessdok-Ordner
- Pfad zur CMDB-Datei
- CMDB-Spaltenmapping: UUID-Spalte, Name-Spalte (einmalig konfigurieren)

**LLM**
- Ollama-URL (z.B. `http://localhost:11434`)
- Modell-Auswahl — Dropdown, dynamisch befüllt via `GET /api/tags`
- Refresh-Button — aktualisiert die Modellliste zur Laufzeit (z.B. nach `ollama pull`)
- Fuzzy-Matching-Schwellenwert (Default: 0.85)

**Graph-DB**
- Neo4j-URL
- User / Passwort

**Pipeline**
- Lauf-Modus: Initial / Full Update / Delta Update
- Pipeline starten

---

## 8. Lauf-Modi

### Initial
Erster Lauf, Knowledge Base leer. Alle Dokumente werden verarbeitet.

- Link stark → automatisch bestätigt
- Link schwach → ins Review (Tab 2)

### Full Update
Alle Dokumente werden neu verarbeitet, Graph wird neu aufgebaut. KB-Einträge fließen in die Bewertung ein.

- Link war bestätigt + LLM findet ihn wieder → automatisch bestätigt
- Link war bestätigt + LLM findet ihn nicht mehr → ins Review mit Hinweis "war bestätigt, nicht mehr gefunden"
- Link neu + stark → automatisch bestätigt
- Link neu + schwach → ins Review

### Delta Update
Nur die übergebenen Dokumente werden neu verarbeitet. Der Rest des Graphen bleibt unangetastet. Gleiche Bewertungslogik wie Full Update, aber nur für die betroffenen Prozesse.

---

## 9. Betrieb

- **Ollama:** lokal auf dem Rechner des Nutzers; empfohlene Mindest-VRAM: 8 GB
- **Neo4j:** lokal oder Docker Compose; kein Cloud-Deployment für v1
- **Pipeline:** idempotent — abgebrochene Läufe können sicher neu gestartet werden (Datei-Hash-basiertes Tracking)

---

## 10. Differenzierung

> **vs. Discovery-Tools:** Discovery-Tools (ServiceNow, Dynatrace etc.) kennen die IT-Landschaft — Systeme, Verbindungen, Abhängigkeiten. Sie wissen aber nicht, warum ein System existiert oder welchen Prozess es unterstützt. Dieser Business-Kontext steckt in Prozessdokumentationen und ist nur durch menschliches Lesen zugänglich.

> **Qualitätsspiegel:** Fehlende Links im Output zeigen direkt, wo die Prozessdokumentation löchrig ist. Das Tool liefert damit nicht nur ein Inventar, sondern auch eine Dokumentationsqualitäts-Analyse als Nebenprodukt.

> **Lernender Layer:** Im Gegensatz zu reinen Scan-Tools lernt dieses System durch menschliche Eingabe. Disambiguation-Regeln und bestätigte Links akkumulieren sich über Zeit — der manuelle Review-Aufwand nimmt mit jedem Lauf ab.

---

## 11. Offene Punkte

- LLM-Modellvergleich: Gemma vs. Qwen vs. Mistral für Extraktion und Cypher-Generierung — Qualitätsvergleich ausstehend (separates Modell für Cypher möglich, aber nicht in v1)
- BPMN-Testdaten: werden extern beschafft, nicht synthetisch generiert

---

*Bridgr | Architektur v0.6 | Stand Mai 2026*

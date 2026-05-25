# Bridgr
**Architektur & Konzept** | Stand: Mai 2026 | v0.11

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
│  Matching → Review → Graph-DB          │
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
| Deployment | Lokal / Docker | Cloud-Deployment der Anwendung |

---

## 5. Domänenmodell

### Prozess
Ein Prozess in Bridgr entspricht einem BPMN `<process>`-Element — nicht einer einzelnen Aktivität oder Task. Bei unstrukturierten Formaten (spätere Versionen) wird der Prozessname als Identifikator verwendet.

### folgt_auf
Drückt aus, dass Prozess A Prozess B auslösen kann — abgeleitet aus dem BPMN-Sequenzfluss zwischen zwei Prozess-Elementen. Bridgr wertet ausschließlich die Verbindung zwischen Prozessen aus, nicht den internen Ablauf von Tasks innerhalb eines Prozesses.

### Anwendung
Eine Anwendung ist ein in der CMDB geführtes System. Pflichtfelder in Bridgr: UUID und Name. Alle weiteren CMDB-Attribute bleiben in der CMDB — Bridgr speichert nur die Referenz (`cmdb_id`).

---

## 6. Pipeline

Der Ablauf ist sequenziell — kein Agent-Framework, keine Parallelisierung. EA-Inventarisierung ist nicht zeitkritisch; Korrektheit und Nachvollziehbarkeit sind wichtiger als Geschwindigkeit.

Die Pipeline ist **idempotent** — ein abgebrochener Lauf kann jederzeit sicher neu gestartet werden. Bereits verarbeitete Dokumente werden anhand eines Datei-Hashes erkannt und übersprungen.

### 6.1 Projektstruktur

```text
bridgr/
├── prompts/
│   ├── extract_bpmn.md         # Prompt für BPMN-Extraktion (XML als Rohtext)
│   ├── extract_generic.md      # für PDF, DOCX, TXT (spätere Versionen)
│   ├── match_fuzzy.md          # Fuzzy-Matching-Entscheidung
│   ├── process_identity.md     # LLM-Prompt für Prozess-Namens-Matching
│   └── cypher_gen.md           # Prompt für LLM → Cypher-Übersetzung
├── skills/
│   ├── extract/
│   │   ├── extract_base.py     # gemeinsames Interface + Output-Schema
│   │   ├── extract_bpmn.py     # v1: XML als Rohtext an OpenAI-kompatibles API
│   │   ├── extract_pdf.py      # spätere Version
│   │   ├── extract_docx.py     # spätere Version
│   │   └── extract_txt.py      # spätere Version
│   ├── match.py                # JSON → CMDB-Abgleich
│   ├── identity.py             # Prozess-Identitäts-Matching (ID oder LLM-Name)
│   ├── review.py               # schwache Links für Tab 2 aufbereiten
│   └── graph_writer.py         # schreibt Knoten und Kanten in Neo4j
├── knowledge_base/
│   └── kb.json                 # persistierte menschliche Entscheidungen
├── config.json                 # technische Konfiguration (persistiert über Neustarts)
├── Input/                      # gemeinsamer Eingabeordner für BPMN/XML und CMDB-Dateien
├── Output/                     # Laufartefakte und spätere Exportziele
├── data/                       # optionale lokale Beispieldaten
├── app.py                      # Streamlit Web-UI
└── main.py                     # orchestriert die Pipeline sequenziell
```

### 6.2 Komponenten

#### Extractor (`skills/extract/`)

Pro Dateiformat ein eigener Extractor-Skill. Alle teilen dasselbe Output-Schema (`extract_base.py`), so dass `main.py` nur die Dateiendung prüft und zum richtigen Extractor routet.

Die eigentliche Intelligenz steckt nicht im Python-Code, sondern in den Prompts. Python liest die Datei, lädt den passenden Prompt aus `prompts/`, befüllt den Platzhalter mit dem Dokumentinhalt und schickt alles an ein **OpenAI-kompatibles API**.

**BPMN-Extraktion:** Das rohe XML wird direkt an das Modell übergeben. BPMN ist strukturierter Text mit sprechenden Tags — ein LLM erkennt `<process>`, `<lane>`, `<task>` und Softwarereferenzen gleichermaßen zuverlässig. Kein separater Parser-Layer nötig.

**Extraktionssichten:** Bridgr hält für Anwendungen zwei Sichten vor. Die **Rohsicht** enthält die vom Modell extrahierten Varianten unverändert und dient Transparenz, Debugging und UI-Hinweisen zu uneinheitlicher Prozessnotation. Die **arbeitsfähige Sicht** wird direkt nach der Extraktion bereinigt und dedupliziert; nur sie fließt in Matching, Review und Graph-Schreiben ein.

**LLM-Laufzeit:** Bridgr koppelt sich nicht fest an Ollama. Stattdessen wird eine OpenAI-kompatible HTTP-Schnittstelle genutzt, die sowohl auf ein lokales Modell als auch auf einen Webprovider zeigen kann.

Konfidenz ergibt sich aus dem Inhalt des LLM-Outputs:
- Explizite Nennung im Task-Namen oder einer Annotation → `stark`
- Implizite Referenz ("das System", "die Datenbank") → `schwach`
- Keine Softwarereferenz im Dokument → kein Match (Problem der Prozessmodellierung, nicht von Bridgr)

| Format | Methode | v1 |
|---|---|---|
| BPMN | LLM (OpenAI-kompatibles API, XML als Rohtext) | ✓ |
| PDF, DOCX, TXT | LLM (OpenAI-kompatibles API) | spätere Version |

LLM-Output-Schema (JSON) pro Dokument:

```json
{
  "prozess": "Auftragsabwicklung",
  "prozess_id": "proc_001",
  "org_einheit": "Vertrieb",
  "folgt_auf": ["Angebotserstellung"],
  "anwendungen": [
    { "name": "SAP SD",             "konfidenz": "stark"   },
    { "name": "das Planungssystem", "konfidenz": "schwach" }
  ]
}
```

**Leere Extraktion:** Liefert das LLM keine Anwendungen, wird das Dokument als `verarbeitet — keine Treffer` markiert und in Tab 2 sichtbar gemacht. Kein stillschweigendes Überspringen.

**Post-Processing nach der Extraktion:** Nach dem LLM-Output werden offensichtliche Operations- und Task-Artefakte aus der arbeitsfähigen Sicht entfernt. Varianten derselben modellierten Anwendung werden zusammengeführt, während die Rohsicht für Nachvollziehbarkeit erhalten bleibt.

**Fehlerbehandlung:** Kaputte oder ungültige BPMN-Dateien werden übersprungen, geloggt und in Tab 2 als Fehler angezeigt. Ungültiges LLM-JSON wird mit bis zu 2 Retry-Versuchen behandelt, danach Fehlermarkierung.

#### Prozess-Identität (`skills/identity.py`)

Stabile Identifikation von Prozessen über Läufe hinweg — zukunftsfähig für strukturierte und unstrukturierte Formate:

- **BPMN:** `process id`-Attribut aus dem XML → stabile, maschinenlesbare ID
- **Unstrukturierte Formate (spätere Versionen):** LLM-basiertes Namens-Matching via `process_identity.md`-Prompt. Das LLM bewertet ob zwei Prozessnamen denselben Prozess beschreiben (z.B. "Stammdatenänderung" ↔ "Anpassung Anschrift"). Bei hoher Konfidenz automatisches Mapping, bei niedriger → ins Review. Dasselbe Konfidenz-Modell wie für Anwendungs-Links.

#### Matcher (`skills/match.py`)

Gleicht die extrahierten Anwendungsnamen gegen den CMDB-Export ab. Reihenfolge:

1. **Knowledge Base zuerst** — bereits validierte Entscheidungen haben Vorrang
2. **Fuzzy Matching** — Levenshtein-Score, Schwellenwert konfigurierbar in Tab 3 (Default: 0.85)
3. **LLM-Fallback** — für unklare Fälle, die noch nicht in der KB stehen

**CMDB-Agnostik:** Pflichtfelder sind UUID und Name. Die tatsächlichen Spaltennamen werden einmalig in Tab 3 gemappt. Der Matcher arbeitet intern immer mit den gemappten Feldern.

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
  ],
  "process_identity": [
    {
      "name_a": "Stammdatenänderung",
      "name_b": "Anpassung Anschrift",
      "gleicher_prozess": true,
      "konfidenz": 0.91,
      "bestaetigt_am": "2026-05-23"
    }
  ]
}
```

> **Wiederholte Ablehnung:** Ein einmal abgelehnter Link gilt dauerhaft als abgelehnt. Er kann in Tab 2 reaktiviert werden.

> **Lerneffekt:** Bei jedem Folgelauf wird die KB zuerst konsultiert. Das System wird mit der Zeit treffsicherer — nicht durch Modelltraining, sondern durch akkumuliertes menschliches Wissen.

#### Konfiguration (`config.json`)

Technische Konfiguration — persistiert über Neustarts hinweg. Wird von Tab 3 gelesen und geschrieben.

```json
{
  "llm_base_url": "http://localhost:11434/v1",
  "llm_model": "gemma3:12b",
  "llm_api_key_env": "",
  "llm_context_window": 131072,
  "neo4j_url": "bolt://localhost:7687",
  "neo4j_user": "neo4j",
  "fuzzy_threshold": 0.85,
  "cmdb_uuid_column": "app_id",
  "cmdb_name_column": "application_name",
  "last_run_mode": "delta"
}
```

**Beispiele:**
- Lokales Modell: `llm_base_url = "http://localhost:11434/v1"` oder anderes lokales OpenAI-kompatibles Gateway
- Webprovider: `llm_base_url = "https://provider.example.com/v1"` plus `llm_api_key_env`

**API-Key-Verhalten:** Für lokale Endpoints darf `llm_api_key_env` leer sein. Für Webprovider verweist `llm_api_key_env` auf den Namen einer Umgebungsvariable, aus der Bridgr den Schlüssel liest. Der API-Key selbst wird in v1 nicht im Prompt- oder Review-Layer gespeichert.

**Modellwahl:** Kein Default-Modell beim ersten Start — der Benutzer wählt aus dem dynamischen Dropdown. Ab dem zweiten Start wird das zuletzt verwendete Modell aus `config.json` vorausgewählt.

#### Graph Writer (`skills/graph_writer.py`)

Schreibt das validierte Inventar als Knoten und Kanten in Neo4j (lokal oder Docker).

**Neo4j-Constraints:**
```cypher
CREATE CONSTRAINT prozess_id IF NOT EXISTS FOR (p:Prozess) REQUIRE p.prozess_id IS UNIQUE;
CREATE CONSTRAINT anwendung_id IF NOT EXISTS FOR (a:Anwendung) REQUIRE a.cmdb_id IS UNIQUE;
CREATE CONSTRAINT orgeinheit_name IF NOT EXISTS FOR (o:OrgEinheit) REQUIRE o.name IS UNIQUE;
```

**Graph-Schema:**
```cypher
(:OrgEinheit)-[:VERANTWORTET]->(:Prozess)
(:Prozess)-[:FOLGT_AUF]->(:Prozess)
(:Prozess)-[:NUTZT {konfidenz: "stark"}]->(:Anwendung {cmdb_id: "...", name: "..."})
```

**Schreibregel:** In Neo4j werden nur `starke` oder durch die Knowledge Base bestätigte Prozess-Anwendungs-Links geschrieben. Schwache fuzzy-Kandidaten bleiben reviewbar, bis ein Mensch sie bestätigt.

**Reconciliation-Regel:** Vor dem Neuschreiben der `NUTZT`-Beziehungen eines Prozesses werden bestehende `NUTZT`-Kanten dieses Prozesses gelöscht. So spiegelt der Graph immer den aktuellen Freigabestand und hält keine veralteten schwachen Altlinks.

**Gelöschte Dokumente / verwaiste Prozesse:** Prozesse deren Quelldokument nicht mehr im Input-Ordner vorhanden ist, werden als `orphaned: true` markiert — nicht gelöscht. Kein automatischer Löschmechanismus in v1.

---

## 7. Graph-Datenmodell

```text
(OrgEinheit) -[:VERANTWORTET]-> (Prozess)
(Prozess)    -[:FOLGT_AUF]->    (Prozess)
(Prozess)    -[:NUTZT]->        (Anwendung)
(Anwendung)                     { cmdb_id, name }
```

| Beziehung | Quelle |
|---|---|
| OrgEinheit → Prozess | BPMN Swimlane |
| Prozess → Prozess | BPMN Sequenzfluss zwischen `<process>`-Elementen |
| Prozess → Anwendung | LLM-Extraktion + KB |
| Anwendung → Infrastruktur | CMDB (nur Referenz via cmdb_id) |

---

## 8. Abfrage-Layer

```text
Benutzer → Web-UI (Streamlit, 3 Tabs) → LLM / Neo4j
```

Das Web-UI ist von Anfang an als Web-Oberfläche gebaut — kein CLI.

### Tab 1 — Kommunikation

Der Benutzer stellt Fragen in natürlicher Sprache. Das LLM übersetzt die Frage via `cypher_gen.md`-Prompt in eine **read-only Cypher-Query** (Neo4j read-only User, kein WRITE erlaubt), holt die Daten aus Neo4j und formuliert eine verständliche Antwort.

```text
[ Frage eingeben                    ] [Senden]

──────────────────────────────────────────────
Antwort:

SAP SD wird in 4 Prozessen genutzt:
Auftragsabwicklung, Retoure, Fakturierung
und Gutschriftverfahren.
```

Fehlerhafte oder leere Ergebnisse werden transparent kommuniziert ("Keine Treffer gefunden" / "Abfrage konnte nicht ausgeführt werden").

### Tab 2 — Link Editing

Übersicht aller schwachen Links, offenen Matches, Dokumente ohne Treffer und Fehler. Der Benutzer kann:

- ✓ bestätigen (schwach → stark, wird in KB geschrieben)
- ✕ ablehnen (dauerhaft, reaktivierbar)
- + manuellen Link anlegen (Prozess → Anwendung, die das LLM nicht erkannt hat)

Die primäre Arbeitsfläche ist eine aktionsfähige Review-Liste mit direkten Aktionen pro Zeile. Der Detailbereich bleibt für Prozesskontext und technische Rohdaten erhalten, ist aber nicht mehr der zwingende Bedienpfad.

Schwache Kandidaten dürfen mehrfach pro Prozessanwendung nebeneinander stehen. Eindeutigkeit wird in v1 nicht automatisch erzwungen.

Wenn in der Rohsicht dieselbe Anwendung in einem Prozess mehrfach in unterschiedlicher Schreibweise auftaucht, zeigt Tab 2 einen Hinweis auf uneinheitliche Prozessnotation. Es erfolgt in v1 keine automatische Zusammenführung auf UI-Ebene.

### Tab 3 — Anwendungskonfig

Konfiguration der Anwendung — liest und schreibt `config.json`.

**Input**
- gemeinsamer Input-Pfad für BPMN/XML und CMDB-Dateien
- aktive CMDB-Datei innerhalb des Input-Pfads
- CMDB-Spaltenmapping: UUID-Spalte, Name-Spalte

**LLM**
- Base-URL eines OpenAI-kompatiblen Endpoints
- Modell-Auswahl — Dropdown, dynamisch befüllt via `GET /v1/models`; wenn der Endpoint keine Modellliste liefert, manuelle Eingabe als Fallback
- API-Key-Umgebungsvariable für Webprovider
- Refresh-Button — aktualisiert die Modellliste zur Laufzeit
- Kontextfenster des gewählten Modells
- Fuzzy-Matching-Schwellenwert (Default: 0.85)

**Graph-DB**
- Neo4j-URL
- User / Passwort

**Pipeline**
- Lauf-Modus: Initial / Full Update / Delta Update
- Teilimport-Flag (bei manuell aufgeteilten Dateien)
- Pipeline starten

Der Laufmodus ist zusätzlich direkt am Startpunkt der Pipeline im Import-Bereich auswählbar.

**Datei-Upload**
- Token-Schätzung beim Upload: Zeichenanzahl → geschätzte Token-Zahl → Vergleich mit Kontextfenster des gewählten Modells
- Warnung wenn Datei das Kontextfenster voraussichtlich sprengt
- Benutzer entscheidet: Risiko eingehen oder Datei manuell aufteilen und mit Teilimport-Flag einlesen

---

## 9. Lauf-Modi

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

**Prozess-Identifikation im Delta:**
- BPMN: stabile `process id` aus dem XML
- Unstrukturierte Formate: LLM-basiertes Namens-Matching mit Konfidenz-Score (siehe `identity.py`)

### Teilimport (Flag)
Wenn der Benutzer eine große Datei manuell aufteilt und in mehreren Läufen einspielt, kann der Lauf mit dem Flag `teilimport: true` markiert werden. In diesem Modus gilt:

- Fehlende Prozesse werden **nicht** als gelöscht interpretiert
- Keine Orphaned-Markierung für Prozesse die in diesem Lauf nicht vorkommen
- Die Löschlogik greift erst bei einem vollständigen Full Update ohne Teilimport-Flag

---

## 10. Betrieb

- **LLM:** OpenAI-kompatibler Endpoint; kann lokal oder bei einem Webprovider betrieben werden
- **Neo4j:** lokal oder Docker Compose; kein Cloud-Deployment der Anwendung für v1; read-only User für den Query-Layer
- **Pipeline:** idempotent — abgebrochene Läufe können sicher neu gestartet werden
- **Logging:** lokal, kein Cloud-Logging
- **Datenschutz:** Bei lokalem LLM-Endpoint bleiben Prompts und Dokumente lokal. Bei Nutzung eines Webproviders verlassen Prompts und Dokumente das System und unterliegen dessen Datenschutz- und Betriebsmodell

---

## 11. Akzeptanzkriterien (v1 / PoC)

1. Über die Weboberfläche können korrekte Informationen aus den Quelldaten abgefragt werden
2. Das Mapping ist über die Weboberfläche pflegbar — schwache Links können bestätigt, abgelehnt und korrigiert werden
3. Informationen zu gemappten Anwendungen und Prozessen können über die Weboberfläche abgerufen werden
4. Die Pipeline läuft stabil durch einen vollständigen Importzyklus (BPMN + CMDB) ohne manuellen Eingriff

---

## 12. Differenzierung

> **vs. Discovery-Tools:** Discovery-Tools (ServiceNow, Dynatrace etc.) kennen die IT-Landschaft — Systeme, Verbindungen, Abhängigkeiten. Sie wissen aber nicht, warum ein System existiert oder welchen Prozess es unterstützt. Dieser Business-Kontext steckt in Prozessdokumentationen und ist nur durch menschliches Lesen zugänglich.

> **Qualitätsspiegel:** Fehlende Links im Output zeigen direkt, wo die Prozessdokumentation löchrig ist. Das Tool liefert damit nicht nur ein Inventar, sondern auch eine Dokumentationsqualitäts-Analyse als Nebenprodukt.

> **Lernender Layer:** Im Gegensatz zu reinen Scan-Tools lernt dieses System durch menschliche Eingabe. Disambiguation-Regeln und bestätigte Links akkumulieren sich über Zeit — der manuelle Review-Aufwand nimmt mit jedem Lauf ab.

---

## 13. Offene Punkte

- BPMN-Testdaten: werden extern beschafft; Entwickler kann sich Mock-Daten anhand der frei zugänglichen BPMN-Spezifikation erstellen
- Wissenslöschung: gezieltes Entfernen von Prozessen, Anwendungen oder ganzen Import-Batches aus dem Graph — Feature-Scope und UI-Platzierung (Tab 2 oder Tab 3) noch offen

---

## 14. Getroffene Entscheidungen

| Entscheidung | Gewählt | Verworfen | Begründung |
|---|---|---|---|
| BPMN-Extraktion | LLM liest XML als Rohtext | Dedizierter XML-Parser + LLM-Layer | BPMN ist strukturierter Text — ein LLM identifiziert relevante Informationen zuverlässig ohne tiefes Format-Verständnis. Einfacher zu bauen, einfacher zu warten, robuster gegenüber BPMN-Varianten. |
| Konfidenz-Quelle | Inhalt des LLM-Outputs | Extraktionsmethode (Parser = stark, LLM = schwach) | Ob eine Softwarereferenz explizit oder implizit ist, ergibt sich aus dem Text — nicht daraus, womit er gelesen wurde. |
| Große Eingabedateien | Token-Warnung + manuelle Aufteilung durch Benutzer | Automatisches Chunking durch Bridgr | Benutzer behält Kontrolle über Prozessgrenzen. Automatisches Chunking riskiert Kontextverlust an Schnittgrenzen. Teilimport-Flag verhindert fehlerhafte Löschlogik. |
| LLM-Anbindung (PoC) | OpenAI-kompatible Schnittstelle mit frei konfigurierbarer Base-URL | Feste Ollama-Kopplung | Dieselbe Anwendung kann auf lokales Modell oder Webprovider zeigen, ohne dass Prompt- oder Pipeline-Logik umgebaut werden muss. |
| Zugangsdaten für Webprovider | Verweis auf Umgebungsvariable in `config.json` | Klartext-API-Key in Prompt- oder Review-Daten | Credentials bleiben aus fachlichen Artefakten heraus und können pro Umgebung unterschiedlich gesetzt werden. |
| Modellgröße vs. Qualität | Größeres Modell bevorzugen | Kleinste funktionierende Variante | Modellgröße hat messbaren Einfluss auf Extraktionsqualität — insbesondere bei SubProzessen, Hierarchien und impliziten Systemreferenzen. In stärkeren Environments kann ein größeres Modell bevorzugt werden. |
| LLM-Anbindung | Um dem Anwender größtmögliche Freiheit zu geben, wird statt local-only ein OpenAI-kompatibler Endpoint geschaffen, der es ermöglicht sowohl lokale Modelle anzubinden als auch web-basierte Modelle, die eine OpenAI-kompatible API anbieten | Feste lokale Laufzeitkopplung | Prompt- und Pipeline-Logik bleiben gleich, unabhängig davon, ob lokal oder über einen Webprovider gearbeitet wird. |
| Extrahierte Anwendungen | Zwei Sichten: `raw_applications` und deduplizierte `applications` | Frühes Verwerfen der Rohvarianten | Die Rohsicht macht uneinheitliche Notation im BPMN sichtbar. Die deduplizierte Sicht stabilisiert Matching und verhindert, dass Task-/Operationsrauschen mehrfach als Anwendung verarbeitet wird. |
| Schwache Matches im Graph | Nicht automatisch schreiben; erst nach Bestätigung oder KB-Eintrag | Sofortiges Schreiben aller fuzzy-Kandidaten | Der Query-Layer soll nur freigegebenes Wissen sehen. Review-Kandidaten bleiben von Graph-Wissen getrennt, bis ein Mensch sie bestätigt. |

---

*Bridgr | Architektur v0.10 | Stand Mai 2026*

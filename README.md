# BRIDGR

BRIDGR verbindet Prozessdokumentation mit CMDB-Daten, um einen EA-Wissensgraphen aufzubauen und spaeter ueber eine natuerlichsprachliche Oberflaeche abfragbar zu machen.

Der aktuelle Architektur-Referenzstand fuer die Umsetzung ist:
- `Specs/Bridgr_Architektur_v10.md`

## Zielbild

BRIDGR soll fuer v1:
- BPMN-Dateien einlesen
- Anwendungsreferenzen per LLM extrahieren
- gegen eine CMDB matchen
- unsichere oder offene Links im UI reviewbar machen
- bestaetigte Ergebnisse spaeter in Neo4j schreiben

## Aktueller Stand

Das Projekt ist noch im Aufbau, hat aber bereits ein erstes funktionsfaehiges Scaffold:
- OpenAI-kompatibler LLM-Client
- BPMN-Extraktion ueber Prompt + JSON-Output
- CMDB-Matching mit KB-First-Logik und Fuzzy Matching
- persistente Knowledge Base
- Streamlit-UI mit 3 Tabs
- persistente Laufartefakte in `Output/`
- Review-Aktionen fuer `Bestaetigen`, `Ablehnen`, `Korrigieren` und `manuellen Link anlegen`

Noch nicht umgesetzt:
- Neo4j-Schreiblogik als echter Datenbank-Write
- Query-Layer fuer Tab 1
- vollstaendige Laufmodus- und Importhistorienlogik gemaess spaeterem Zielausbau

## Projektstruktur

```text
BRIDGR/
├── Input/                  # BPMN-Eingaben des Benutzers
├── Output/                 # erzeugte Laufartefakte und spaetere Exportziele
├── prompts/                # LLM-Prompts
├── skills/                 # Fachlogik fuer Extract, Match, Review, Graph
├── knowledge_base/         # persistente Review-Entscheidungen
├── data/                   # lokale Beispieldaten, z.B. CMDB-CSV
├── app.py                  # Streamlit-UI
├── main.py                 # CLI-Einstieg fuer Pipeline-Laeufe
├── pipeline.py             # orchestriert den aktuellen Happy Path
└── config.json             # technische Konfiguration
```

## Input und Output

Reservierte Ordner:
- `Input/`: Hier legt der Benutzer zu importierende BPMN-Dateien ab.
- `Output/`: Hier legt BRIDGR erzeugte Artefakte ab. Aktuell sind das vor allem Laufartefakte; spaeter soll der Ordner auch fuer menschenlesbare Exporte verwendet werden.

Aktuell relevante Output-Dateien:
- `Output/import_state.json`: Dateihashes und letzter bekannter Dokumentzustand
- `Output/latest_run.json`: letzter gespeicherter Preview-/Importlauf fuer die UI

## Konfiguration

Die Standardkonfiguration liegt in `config.json`.

Wichtige Felder:
- `llm_base_url`: OpenAI-kompatibler Endpoint
- `llm_model`: zu verwendendes Modell
- `llm_api_key_env`: Name der Umgebungsvariable fuer den API-Key
- `process_input_path`: Standardpfad fuer BPMN-Dateien
- `cmdb_path`: Pfad zur CMDB-Datei
- `output_path`: Ziel fuer Laufartefakte

Beispiel:

```json
{
  "llm_base_url": "http://localhost:11434/v1",
  "llm_model": "",
  "llm_api_key_env": "OPENAI_API_KEY",
  "process_input_path": "Input",
  "cmdb_path": "data/cmdb.csv",
  "output_path": "Output"
}
```

## Secrets und `.env`

Lokale Secrets werden nicht im Code abgelegt.

Unterstuetzte Pfade fuer `.env`-Dateien:
- `.env`
- `Specs/.env`

Aktuell erwartet das Projekt fuer Webprovider typischerweise:
- `OPENAI_API_KEY`

Eine Vorlage liegt in:
- `Specs/.env.example`

## Lokale Nutzung

### 1. Abhaengigkeiten

Das Projekt ist aktuell fuer Python `>=3.10` vorbereitet.

Empfohlener Weg fuer die lokale Nutzung:

```powershell
python -m pip install -r requirements-dev.txt
```

Hinweis:
- Eine editable Installation ueber `python -m pip install -e .[dev]` ist fuer BRIDGR aktuell nicht noetig.
- Da das Projekt in einem OneDrive-Pfad liegen kann, ist die direkte Installation ueber `requirements*.txt` robuster als ein Packaging-Setup im Editable-Modus.
- `streamlit` ist aktuell bewusst unter `1.57` gehalten. Die 1.57er-Linie fuehrt durch die neue Starlette-basierte Serverumstellung lokal zu Import-/Kompatibilitaetsproblemen.

### 2. Streamlit starten

```powershell
streamlit run app.py
```

### 3. Pipeline per CLI starten

Gesamten konfigurierten Input-Ordner verarbeiten:

```powershell
python main.py
```

Einzelne BPMN-Datei testen:

```powershell
python main.py --file Input\beispiel.bpmn
```

## Aktuelle UI-Funktionen

### Tab 1 - Kommunikation

Aktuell nur Platzhalter fuer den spaeteren Query-Layer.

### Tab 2 - Link Editing

Aktuell verfuegbar:
- Pipeline-Preview starten
- letzten gespeicherten Lauf aus `Output/latest_run.json` anzeigen
- Statusfilter fuer Dokumente
- Dokumentdetails mit Anwendungen, Matches und Review-Kontext
- Match-Vorschlag bestaetigen
- Match-Vorschlag ablehnen
- Match-Vorschlag auf anderes CMDB-Ziel korrigieren
- manuellen Link fuer einen Prozess anlegen

### Tab 3 - Anwendungskonfig

Aktuell verfuegbar:
- LLM-Endpoint konfigurieren
- Modellnamen setzen
- API-Key-Umgebungsvariable setzen
- Input-, CMDB- und Output-Pfade setzen
- Fuzzy-Threshold setzen
- Modus speichern
- Modellliste ueber `/v1/models` abrufen

## Tests

Testlauf:

```powershell
python -m pytest
```

Der aktuelle Teststand deckt unter anderem ab:
- `.env`-Loading
- BPMN-Extraktion und XML-Fehlerfall
- Prozess-ID-Extraktion
- Matching inkl. abgelehnter Links
- Pipeline-Happy-Path, Delta-Skip und Laufartefakte
- Aufbereitung der UI-Statusdaten
- KB-Aktionen fuer Bestaetigen und Ablehnen

## Hinweise

- Die Spezifikationsdateien unter `Specs/` sind Referenzdokumente und werden nicht ungefragt umorganisiert.
- Der aktuelle Code folgt bewusst kleinen, inkrementellen Schritten und bildet noch nicht den kompletten Zielumfang aus der Architektur ab.
- Obwohl die Kommunikation und Spezifikation deutsch sind, bleiben Variablennamen und Code-Kommentare auf Englisch.

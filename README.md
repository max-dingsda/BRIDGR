# BRIDGR

BRIDGR verbindet Prozessdokumentation mit CMDB-Daten, um einen EA-Wissensgraphen aufzubauen und spaeter ueber eine natuerlichsprachliche Oberflaeche abfragbar zu machen.

Der aktuelle Architektur-Referenzstand fuer die Umsetzung ist:
- `Specs/Bridgr_Architektur_v12.md`

## Zielbild

BRIDGR soll fuer v1 bzw. den naechsten Ausbaupfad:
- Prozessdokumente in BPMN, TXT, DOCX und PDF einlesen
- formatabhaengig Text gewinnen und ueber denselben LLM-zentrierten Extraktionspfad verarbeiten
- Anwendungsreferenzen per LLM extrahieren
- gegen eine CMDB matchen
- unsichere oder offene Links im UI reviewbar machen
- bestaetigte oder starke Ergebnisse in Neo4j schreiben

## Aktueller Stand

Das Projekt ist noch im Aufbau, hat aber bereits einen funktionierenden vertikalen Schnitt:
- OpenAI-kompatibler LLM-Client
- BPMN-, TXT-, DOCX- und PDF-Verarbeitung ueber einen gemeinsamen semantischen Extraktionspfad
- BPMN-Transformer fuer sehr grosse BPMN/XML-Dateien als vorbereitender, LLM-freier Reduktionsschritt
- Rohsicht und deduplizierte Arbeitssicht fuer extrahierte Anwendungen
- CMDB-Matching mit KB-First-Logik, mehreren Kandidaten und Fuzzy Matching
- Neo4j-Write-Pfad fuer Prozesse, Orgeinheiten und bestaetigte bzw. starke Anwendungslinks
- natuerlichsprachlicher Query-Layer mit Session-Chat, LLM -> Cypher -> Neo4j -> Antwort und Rueckfrage bei Mehrdeutigkeiten
- persistente Knowledge Base
- Streamlit-UI mit 3 Tabs
- persistente Laufartefakte in `Output/`
- optionales `debug.log` fuer Query-/LLM-Diagnose im Output-Ordner
- aktionsfaehige Review-Liste fuer `Bestaetigen`, `Ablehnen` und `manuellen Link anlegen`
- Hinweise auf uneinheitliche Prozessnotation bei mehrfach extrahierten Rohvarianten

Wichtige Einordnung:
- Die Spezifikation `v0.12` oeffnet den Scope fuer unstrukturierte Prozessbeschreibungen.
- Die aktuelle Implementierung unterstuetzt bereits BPMN, TXT, DOCX und PDF ueber einen gemeinsamen semantischen Extraktionspfad.

Noch nicht umgesetzt:
- separate Read-only-DB-Identitaet fuer den Query-Layer
- robustere Query-Generierung und Antwortformulierung bei generischen Suchbegriffen
- vollstaendige Laufmodus- und Importhistorienlogik gemaess spaeterem Zielausbau

## Projektstruktur

```text
BRIDGR/
├── Input/                  # Prozessdokumente und CMDB-Dateien des Benutzers
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
- `Input/`: Hier legt der Benutzer zu importierende Prozessdokumente und CMDB-Dateien ab.
- `Output/`: Hier legt BRIDGR erzeugte Artefakte ab. Aktuell sind das vor allem Laufartefakte; spaeter soll der Ordner auch fuer menschenlesbare Exporte verwendet werden.

Aktuell relevante Output-Dateien:
- `Output/import_state.json`: Dateihashes und letzter bekannter Dokumentzustand
- `Output/latest_run.json`: letzter gespeicherter Preview-/Importlauf fuer die UI
- `Output/debug.log`: optionale JSONL-Diagnoseausgabe bei aktiviertem Debug-Modus

## Konfiguration

Die Standardkonfiguration liegt in `config.json`.

Wichtige Felder:
- `llm_base_url`: OpenAI-kompatibler Endpoint
- `llm_model`: zu verwendendes Modell
- `llm_api_key_env`: Name der Umgebungsvariable fuer den API-Key
- `llm_timeout_seconds`: Timeout fuer Requests an den LLM-Endpoint
- `neo4j_url`: Neo4j-Bolt-URL
- `neo4j_user`: Neo4j-Benutzer
- `neo4j_password`: Neo4j-Passwort
- `neo4j_database`: optionaler Neo4j-Datenbankname, fuer Aura typischerweise die Instanz-ID
- `input_path`: gemeinsamer Eingabeordner fuer Prozessdokumente und CMDB-Dateien
- `cmdb_filename`: aktive CMDB-Datei innerhalb des Eingabeordners
- `output_path`: Ziel fuer Laufartefakte
- `last_run_mode`: Standardlaufmodus fuer die Pipeline
- `debug_mode`: schreibt bei aktivierter Diagnose zusaetzliche Ereignisse nach `Output/debug.log`

Beispiel:

```json
{
  "llm_base_url": "http://localhost:11434/v1",
  "llm_model": "",
  "llm_api_key_env": "OPENAI_API_KEY",
  "llm_timeout_seconds": 900,
  "neo4j_url": "bolt://localhost:7687",
  "neo4j_user": "neo4j",
  "neo4j_password": "",
  "input_path": "Input",
  "cmdb_filename": "cmdb.csv",
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
- `NEO4J_URI`
- `NEO4J_USERNAME`
- `NEO4J_PASSWORD`
- `NEO4J_DATABASE`

Fuer Neo4j-Aura koennen die Zugangsdaten direkt ueber `.env` kommen. Wenn in `config.json` noch die lokalen Defaults (`bolt://localhost:7687`, `neo4j`) stehen, werden die gesetzten `NEO4J_*`-Variablen automatisch bevorzugt. Das Passwort aus `NEO4J_PASSWORD` wird in der UI verwendet, aber beim Speichern nicht stillschweigend nach `config.json` zurueckgeschrieben.

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

Einzelnes Prozessdokument testen:

```powershell
python main.py --file Input\beispiel.txt
```

## Aktuelle UI-Funktionen

### Tab 1 - Kommunikation

Aktuell verfuegbar:
- Session-Chat fuer natuerliche Fragen
- Rueckfrage bei mehrdeutigen Anwendungsreferenzen
- Cypher per LLM generieren
- Read-only-Validierung auf verbotene Write-Tokens
- Query gegen Neo4j ausfuehren
- Ergebnis in kurze natuerliche Sprache umformulieren
- generierten Cypher als technische Details anzeigen

### Tab 2 - Link Editing

Aktuell verfuegbar:
- Pipeline-Preview starten
- letzten gespeicherten Lauf aus `Output/latest_run.json` anzeigen
- Statusfilter fuer Dokumente
- aktionsfaehige Review-Liste mit `Bestaetigen`, `Ablehnen` und `Manuell anlegen`
- mehrere schwache CMDB-Kandidaten pro Prozessanwendung anzeigen
- Dokumentdetails mit Prozesskontext und technischen Rohdaten
- Hinweise auf moegliche Mehrfachnotation derselben Anwendung innerhalb eines Prozesses
- nur starke oder KB-bestaetigte Links in Neo4j schreiben; schwache fuzzy-Kandidaten bleiben im Review
- Knowledge Base gezielt leeren und danach konsistent neu einspielen

### Tab 3 - Anwendungskonfig

Aktuell verfuegbar:
- LLM-Endpoint konfigurieren
- Modellnamen setzen
- API-Key-Umgebungsvariable setzen
- LLM-Timeout konfigurieren
- Neo4j-URL, User, Passwort und optionalen Datenbanknamen setzen
- gemeinsamen Input- und Output-Pfad setzen
- aktive CMDB-Datei innerhalb des Input-Ordners waehlen
- Prozessdateien in BPMN, XML, TXT, DOCX und PDF importieren
- einzelne BPMN/XML-Dateien vor dem eigentlichen Import in kompakte Transform-Dateien ueberfuehren
- Fuzzy-Threshold setzen
- Debug-Modus aktivieren
- Importmodus direkt beim Starten der Pipeline waehlen
- Modellliste ueber `/v1/models` abrufen
- Neo4j-Erreichbarkeit anhand der aktuell wirksamen Konfiguration pruefen
- LLM-Erreichbarkeit und Modellverfuegbarkeit getrennt pruefen
- Laufzeit erfolgreicher Pipeline-Laeufe direkt in der UI anzeigen

## BPMN-Transformer fuer grosse Modelle

Der BPMN-Transformer ist ein vorbereitender Schritt fuer sehr grosse oder sehr technische BPMN/XML-Dateien.

Problem:
- grosse Gesamtprozessmodelle enthalten sehr viel XML-Rauschen
- lokale Modelle laufen bei Roh-BPMN leichter in Timeouts oder liefern kein gueltiges JSON
- fuer den Initialload in Unternehmen sind grosse BPMN-Dateien eher die Regel als die Ausnahme

Loesung:
- der Transformer liest die ausgewaehlte BPMN/XML-Datei ohne LLM
- er extrahiert daraus kompakte Prozesshinweise: Prozessnamen, Lane-Bezeichner und modellnahe Anwendungsreferenzen
- das Ergebnis wird als Textdatei unter `Input/transformed/` gespeichert

Dateiname:
- `<originalname>__bridgr_transform.txt`

Nutzung:
1. grosse BPMN/XML-Datei in den aktuellen `Input Path` legen
2. in Tab 3 unter `Import` die gewuenschte BPMN/XML-Datei bei `BPMN fuer Transformation` auswaehlen
3. `BPMN transformieren` ausloesen
4. den `Input Path` auf `Input/transformed/` umstellen oder die erzeugte Datei gezielt fuer weitere Imports nutzen

Ziel:
- weniger Kontext fuer das LLM
- deutlich kleinere Eingabedateien
- stabilere Extraktion bei lokal laufenden Modellen
- besser kontrollierbarer Initialload fuer grosse Unternehmens-BPMNs

Wichtige Einordnung:
- der Transformer ersetzt keine fachliche BPMN-Auswertung
- er ist bewusst eine pragmatische Vorreduktion fuer den LLM-zentrierten Importpfad
- Roh-BPMN und transformierte Datei koennen parallel im Projekt bestehen

## Debug-Modus

Wenn `Debug Mode` in Tab 3 aktiviert ist:
- schreibt BRIDGR Diagnoseereignisse nach `Output/debug.log`
- Query-Fehler enthalten Frage, Fehlermeldung und den erzeugten Cypher
- die Datei ist als JSONL aufgebaut und fuer lokale Fehlersuche gedacht

## Tests

Testlauf:

```powershell
python -m pytest
```

Der aktuelle Teststand deckt unter anderem ab:
- `.env`-Loading
- BPMN-Extraktion, Deduplizierung und XML-Fehlerfall
- TXT-, DOCX- und PDF-Textgewinnung
- Prozess-ID-Extraktion
- Matching inkl. Mehrfachkandidaten und abgelehnter Links
- Read-only-Cypher-Validierung
- Query-Layer-Happy-Path inkl. natuerlicher Antwort und Mehrdeutigkeitsbehandlung
- Pipeline-Happy-Path, Delta-Skip und Laufartefakte
- Aufbereitung der UI-Statusdaten und Warnhinweise
- KB-Aktionen fuer kandidatenspezifisches Bestaetigen und Ablehnen
- Graph-Write-Pfad inkl. Aufraeumen alter `NUTZT`-Kanten

## Hinweise

- Die Spezifikationsdateien unter `Specs/` sind Referenzdokumente und werden nicht ungefragt umorganisiert.
- Der aktuelle Code folgt bewusst kleinen, inkrementellen Schritten und bildet noch nicht den kompletten Zielumfang aus der Architektur ab.
- Obwohl die Kommunikation und Spezifikation deutsch sind, bleiben Variablennamen und Code-Kommentare auf Englisch.

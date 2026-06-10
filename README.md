# BRIDGR

BRIDGR verbindet Prozessdokumentation mit CMDB-Daten, um einen EA-Wissensgraphen aufzubauen und spaeter ueber eine natuerlichsprachliche Oberflaeche abfragbar zu machen.

Der aktuelle Architektur-Referenzstand fuer die Umsetzung ist:
- `Specs/Bridgr_Architektur_v22.md`

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
- Neo4j-Write-Pfad fuer Prozesse, Organisationseinheiten und bestaetigte bzw. starke Anwendungslinks
- normalisierte CMDB-Sicht fuer `Anwendung`, `Schnittstelle` und `Server`
- technischer CMDB-Write-Pfad fuer `USES_INTERFACE` und `RUNS_ON`
- erste CMDB-Ownership-Logik mit direktem 1:1-Match oder Kandidatenbildung fuer Organisationseinheiten
- natuerlichsprachlicher Chat-Layer: LLM als Orchestrator, generiert und fuehrt Cypher-Abfragen selbststaendig aus und formuliert die Antwort
- zwei Chat-Modi: `prompt-only` (LLM gibt Cypher als Textblock aus, kompatibel mit lokalen Modellen) und `tool-use` (formales Function Calling, LLM kann mehrere Queries pro Turn ausfuehren)
- vollstaendige Gesprächshistorie als Grundlage fuer Folgefragen, Praezisierungen und Kontextwechsel ohne imperativische Code-Zustandsverwaltung
- schema-konservativer System-Prompt mit Rollenbeschreibung, Graph-Schema und Cypher-Regeln; zentraler Prompt in `prompts/chat_system.md`
- kanonisches Query-Schema in `graph_schema.py` als gemeinsame Grundlage fuer Prompting und Validierung
- deterministische Alias-Anreicherung bei leeren Ergebnissen: Hinweise auf bekannte Alternativbegriffe werden dem LLM mitgegeben
- benutzerverstaendliche Uebersetzung technischer Query-/Validierungsfehler im Chat statt roher Cypher- oder Treibertexte
- persistente Knowledge Base
- persistente Knowledge Base inklusive expliziter Rollen-Markierungen in `knowledge_base/kb.json`
- Alias-Projektion nach Neo4j fuer kuratierte Kurzformen oder Fehlbezeichnungen aus manuellen App-Mappings und Org-Mappings
- deterministische Alias-Aufloesung im Query-Lookup, wenn direkte Namenssuche keinen Treffer liefert
- Streamlit-UI mit 4 Tabs
- persistente Laufartefakte in `Output/`
- optionales `debug.log` fuer Query-/LLM-Diagnose im Output-Ordner
- aktionsfaehige Review-Liste fuer `Bestaetigen`, `Ablehnen` und `manuellen Link anlegen`
- Hinweise auf uneinheitliche Prozessnotation bei mehrfach extrahierten Rohvarianten

Wichtige Einordnung:
- Die aktuelle Implementierung unterstuetzt BPMN, TXT, DOCX und PDF ueber einen gemeinsamen semantischen Extraktionspfad.
- Der Chat-Layer basiert seit v0.19 auf dem LLM-als-Orchestrator-Muster; imperativische Gesprächszustandsverwaltung (Disambiguierungslogik, Fokus-Entitaet) entfaellt aus dem Code.

Noch nicht umgesetzt:
- vollstaendige UI-/Review-Unterstuetzung fuer alle neuen CMDB-Objekttypen
- Unterstuetzung weiterer CMDB-Dateiformate jenseits von CSV
- separate Read-only-DB-Identitaet fuer den Query-Layer
- vollstaendige Abloesung der `knowledge_base/kb.json` als einzige Kurationsquelle; aktuell werden Alias-Informationen zusaetzlich nach Neo4j projiziert, die restliche Kuratierung bleibt dateibasiert
- ArchiMate Views/Viewpoints im Export; selektiver Export (setzt Views voraus)

## Projektstruktur

```text
BRIDGR/
├── core/                   # geteilte Grundbausteine: Config, Neo4j, LLM, Schema, Konstanten
├── processing/             # Pipeline, Import, KB, CMDB, Query-Layer, Artefakte
├── services/               # UI-ausgeloeste Seiteneffekte und Orchestrierung
├── ui/                     # Streamlit-Tabmodule
├── skills/                 # Fachlogik fuer Extract, Match, Review, Graph
├── prompts/                # LLM-Prompts
├── knowledge_base/         # persistente Review-Entscheidungen (kb.json)
├── data/                   # Archive, Hilfsdaten und archimate_mapping.json
├── Input/                  # Prozessdokumente und CMDB-Dateien des Benutzers
├── Output/                 # erzeugte Laufartefakte und spaetere Exportziele
├── scripts/                # Wartungsskripte (nicht fuer Produktion)
├── app.py                  # Streamlit-Entrypoint
├── main.py                 # CLI-Einstieg fuer Pipeline-Laeufe
└── config.json             # technische Konfiguration
```

## Input und Output

Reservierte Ordner:
- `Input/`: Hier legt der Benutzer zu importierende Prozessdokumente und CMDB-Dateien ab.
- `Output/`: Hier legt BRIDGR erzeugte Artefakte ab. Aktuell sind das vor allem Laufartefakte; spaeter soll der Ordner auch fuer menschenlesbare Exporte verwendet werden.
- `data/input_archive/`: Hierhin verschiebt BRIDGR nach erfolgreichem Import verarbeitete Prozessdateien aus der Inbox.

Aktuell relevante Output-Dateien:
- `Output/import_state.json`: letzter bekannter Dokumentzustand
- `Output/latest_run.json`: letzter gespeicherter Import-/Reviewlauf fuer die UI; wird nach Prozessimporten und nach einer CMDB-Synchronisation fuer die Neubewertung bestehender Zuordnungen aktualisiert
- `Output/debug.log`: optionale JSONL-Diagnoseausgabe bei aktiviertem Debug-Modus

Relevante Knowledge-Base-Bereiche:
- `knowledge_base/kb.json` enthaelt weiterhin die kuratierten Zuordnungen und Kandidaten.
- `org_unit_candidates` speichert offene, uebernommene, gemappte oder abgewiesene Organisationskandidaten.
- `role_decisions` speichert explizit als reine Rolle markierte Begriffe, damit sie im Organisations-Tab nicht dauerhaft als offene Zuordnung auftauchen.

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
- `cmdb_uuid_column`: technische ID-Spalte der CMDB-Entities-Datei
- `cmdb_name_column`: Namensspalte der CMDB-Entities-Datei
- `cmdb_entity_type_column`: Typ-Spalte fuer `application`, `interface`, `server`, optional `process`
- `cmdb_server_type_column`: Server-Untertyp `physical` oder `virtual`
- `cmdb_owner_name_column`: Owner-/Verantwortungsbezeichnung aus der CMDB
- `cmdb_relations_filename`: optionale zweite CSV-Datei fuer CMDB-Beziehungen
- `cmdb_relation_source_column`: Quell-ID-Spalte der Relations-Datei
- `cmdb_relation_type_column`: Beziehungstyp-Spalte der Relations-Datei
- `cmdb_relation_target_column`: Ziel-ID-Spalte der Relations-Datei
- `cmdb_multivalue_separator`: vorgesehener Trenner fuer spaetere Ein-Datei-CMDB-Exporte mit Mehrfachwerten
- `output_path`: Ziel fuer Laufartefakte
- `last_run_mode`: Standardlaufmodus fuer den Import (`full` oder `partial`)
- `chat_mode`: Chat-Betriebsmodus (`prompt-only` oder `tool-use`); Default: `prompt-only`
- `debug_mode`: schreibt bei aktivierter Diagnose zusaetzliche Ereignisse nach `Output/debug.log`

Hinweise zur UI:
- Im Konfigurations-Tab stehen LLM-Presets fuer `OpenAI` und `Ollama` zur Verfuegung.
- Das Feld `llm_api_key_env` bzw. `API-Schluessel (Umgebungsvariable)` erwartet den Namen
  der Umgebungsvariable, nicht den geheimen Schluesselwert selbst, zum Beispiel
  `OPENAI_API_KEY`.

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
  "cmdb_uuid_column": "id",
  "cmdb_name_column": "name",
  "cmdb_entity_type_column": "entity_type",
  "cmdb_server_type_column": "server_type",
  "cmdb_owner_name_column": "owner_name",
  "cmdb_relations_filename": "cmdb_relations.csv",
  "input_path": "Input",
  "cmdb_filename": "cmdb_entities.csv",
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
- Session-Chat fuer natuerlichsprachliche Fragen zur IT-Landschaft
- LLM als Orchestrator: entscheidet eigenstaendig, ob und welche Cypher-Abfrage benoetigt wird
- `prompt-only`-Modus: LLM gibt Cypher als Textblock aus, Code extrahiert und fuehrt aus (kompatibel mit lokalen Modellen)
- `tool-use`-Modus: formales Function Calling, LLM kann mehrere Queries pro Turn ausfuehren
- vollstaendige Gesprächshistorie fuer Folgefragen, Praezisierungen und Kontextwechsel
- deterministische Alias-Anreicherung: bei leeren Ergebnissen werden bekannte Alternativbegriffe als Hinweise an den LLM mitgegeben
- Cypher-Retry bei korrigierbaren Syntaxfehlern (bis zu 2 Versuche mit Fehlerfeedback an den LLM)
- Read-only-Validierung auf verbotene Write-Tokens sowie auf das kanonische Query-Schema aus `core/graph_schema.py`
- Query gegen Neo4j ausfuehren, Ergebnis in natuerliche Sprache umformulieren
- technische Query-/Validierungsfehler in benutzerverstaendliche Hinweise uebersetzen
- generierten Cypher als technische Details anzeigen

### Tab 2 - Zuordnungen

Aktuell verfuegbar:
- Review fuer den letzten Import oder eine manuell gewaehlte Teilmenge oeffnen
- letzten gespeicherten Lauf aus `Output/latest_run.json` anzeigen
- letzten Importkontext inklusive Archivpfad anzeigen
- Statusfilter fuer Dokumente
- aktionsfaehige Review-Liste mit `Bestaetigen`, `Ablehnen` und `Manuell anlegen`
- mehrere schwache CMDB-Kandidaten pro Prozessanwendung anzeigen
- Dokumentdetails mit Prozesskontext und technischen Rohdaten (reine Ansicht, keine Aktionen)
- Hinweise auf moegliche Mehrfachnotation derselben Anwendung innerhalb eines Prozesses
- nur starke oder KB-bestaetigte Links in Neo4j schreiben; schwache fuzzy-Kandidaten erscheinen im Review, sofern kein starker Match fuer dieselbe Anwendung existiert
- nach einer CMDB-Synchronisation koennen bisher offene oder schwache Faelle des letzten Laufs automatisch verschwinden, wenn die aktualisierte CMDB jetzt einen starken Match liefert

### Tab 3 - Konfiguration

Aktuell verfuegbar:
- LLM-Presets fuer `OpenAI` und `Ollama`
- LLM-Endpoint konfigurieren
- Modellnamen setzen
- API-Key-Umgebungsvariable setzen
- LLM-Timeout konfigurieren
- Neo4j-URL, User, Passwort und optionalen Datenbanknamen setzen
- gemeinsamen Input- und Output-Pfad setzen
- aktive CMDB-Datei innerhalb des Input-Ordners waehlen
- CMDB-Feldmapping fuer das erweiterte Entities-/Relations-Modell setzen
- CMDB nach Neo4j synchronisieren und dabei den letzten gespeicherten Lauf gegen die aktuelle CMDB neu bewerten
- Prozessdateien in BPMN, XML, TXT, DOCX und PDF importieren
- einzelne BPMN/XML-Dateien vor dem eigentlichen Import in kompakte Transform-Dateien ueberfuehren
- Fuzzy-Threshold setzen
- Debug-Modus aktivieren
- Chat-Modus `prompt-only` oder `tool-use` waehlen
- Importmodus `full` oder `partial` direkt beim Starten des Imports waehlen
- Modellliste ueber `/v1/models` abrufen
- Neo4j-Erreichbarkeit anhand der aktuell wirksamen Konfiguration pruefen
- LLM-Erreichbarkeit und Modellverfuegbarkeit getrennt pruefen
- Laufzeit erfolgreicher Pipeline-Laeufe direkt in der UI anzeigen
- verarbeitete Prozessdateien nach erfolgreichem Import transparent nach `data/input_archive/<timestamp>/` verschieben
- Wissensbasis gezielt zuruecksetzen: alle Eintraege, nur Bestaetigungen oder nur Ablehnungen leeren (inkl. Alias-Synchronisation nach Neo4j)

### Tab 4 - Organisation

Aktuell verfuegbar:
- bekannte Organisationseinheiten manuell pflegen
- Abschnitte als initial eingeklappte Bereiche fuer bessere Uebersicht
- Organisationseinheiten direkt als `:OrgEinheit` nach Neo4j synchronisieren
- offene Kandidaten aus unstrukturierten Dokumenten anzeigen
- offene Kandidaten aus CMDB-Owner-Bezeichnungen anzeigen
- Kandidaten auf bestehende Organisationseinheiten mappen
- Kandidaten als neue Organisationseinheit uebernehmen
- Kandidaten abweisen
- vorgeschlagene Prozess-Eigentuemer vor den manuell zu pflegenden Prozessen anzeigen
- Prozesse ohne Eigentuemer einzeln oder per Batch derselben Organisationseinheit zuordnen
- Rollen bestehenden Organisationseinheiten zuordnen oder direkt als neue Organisationseinheit anlegen
- Begriffe explizit als `Rolle` markieren, wenn bewusst keine Zuordnung zu einer Organisationseinheit erfolgen soll
- neu bestaetigte oder neu angelegte Organisationseinheiten nach dem UI-Rerun sofort in den folgenden Auswahllisten verfuegbar machen
- gemappte Kandidaten als `(:Alias)-[:KANN_MEINEN]->(:OrgEinheit)` nach Neo4j projizieren
- bei gemappten oder uebernommenen Kandidaten betroffene Prozesse im letzten Lauf gezielt neu bewerten und `VERANTWORTET`-Beziehungen in Neo4j nachziehen

Wichtige Einordnung:
- manuell angelegte Organisationseinheiten koennen zunaechst ohne Prozessbezug im Graph existieren
- CMDB-Owner mit sicherem 1:1-Match koennen direkt als `VERANTWORTET` auf CMDB-Objekte landen
- unsichere CMDB-Owner werden wie andere Org-Kandidaten ueber denselben Review-Pfad behandelt

### Tab 5 - EA-Modell

Aktuell verfuegbar:
- Import-Mapping konfigurieren: eine Zeile pro ArchiMate-Typ, beliebig viele Eintraege koennen auf dasselbe BRIDGR-Label zeigen (m:1); Zeilen einzeln loeschbar, neue Eintraege hinzufuegbar
- Export-Mapping konfigurieren: kanonischer ArchiMate-Typ pro BRIDGR-Label fuer Nodes ohne ArchiMate-Herkunft
- Beziehungs-Mapping konfigurieren (optional): akzeptierte Importtypen und kanonischer Exporttyp pro Label-Paar
- ArchiMate Exchange Format 3.x importieren; uebersprungene Typen mit Anzahl anzeigen
- Graphen als ArchiMate Exchange Format 3.x exportieren (vollstaendiger Graph, keine Views/Viewpoints)
- Export-Precheck: vor dem Export werden Nodes ohne archimate_type angezeigt (nach Label gruppiert), vorgeschlagene Typen koennen per Gruppe oder individuell pro Node bestaetigt oder geaendert werden; Bestaetigung schreibt ausschliesslich archimate_type (Attribut-Eigentuemer-Prinzip)
- Roundtrip-Konsistenz: ArchiMate-importierte Nodes behalten ihren originalen archimate_type beim Export

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
- Pipeline-Happy-Path, partielle Imports und Laufartefakte
- CMDB-Normalisierung fuer Entities und Relations
- Aufbereitung der UI-Statusdaten und Warnhinweise
- KB-Aktionen fuer kandidatenspezifisches Bestaetigen und Ablehnen
- Graph-Write-Pfad inkl. Aufraeumen alter Prozesskanten und neuem `DIENT`-Modell
- ArchiMate-Import (Parser, Namenswahl, Identity Resolution, Beziehungen) und Export (Roundtrip, Typ-Mapping, XML-Validierung)
- Export-Precheck: Nodes ohne archimate_type abfragen, Typ-Schreiben mit Attribut-Eigentuemer-Semantik

## Hinweise

- Die Spezifikationsdateien unter `Specs/` sind Referenzdokumente und werden nicht ungefragt umorganisiert.
- Der aktuelle Code folgt bewusst kleinen, inkrementellen Schritten und bildet noch nicht den kompletten Zielumfang aus der Architektur ab.
- Obwohl die Kommunikation und Spezifikation deutsch sind, bleiben Variablennamen und Code-Kommentare auf Englisch.

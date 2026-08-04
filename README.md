# BRIDGR

BRIDGR verbindet Prozessdokumentation mit CMDB-Daten, um einen EA-Wissensgraphen aufzubauen und später über eine natürlichsprachliche Oberfläche abfragbar zu machen.

Der aktuelle Architektur-Referenzstand für die Umsetzung ist:

- `Specs/Bridgr_Architektur_v29.md`

## Zielbild

BRIDGR soll für v1 bzw. den nächsten Ausbaupfad:

- Prozessdokumente in BPMN, TXT, DOCX und PDF einlesen
- formatabhängig Text gewinnen und über denselben LLM-zentrierten Extraktionspfad verarbeiten
- Anwendungsreferenzen per LLM extrahieren
- gegen eine CMDB matchen
- unsichere oder offene Links im UI reviewbar machen
- bestätigte oder starke Ergebnisse in Neo4j schreiben

## Wie BRIDGR Dokumente verarbeitet

BRIDGR liest Prozessdokumente und überträgt deren Inhalte schrittweise in einen strukturierten Wissensgraphen.

```text
Prozessdokument (BPMN, TXT, DOCX, PDF)
        |
        v
Textgewinnung  (formatspezifisch, ohne LLM)
        |
        v
LLM-Extraktion
  "Prozess: Auftragserfassung
   gefundene Anwendungen: SAP SD, Outlook"
        |
        v
Matching gegen CMDB
  1. Kuratierte Entscheidungen (Neo4j) — bestaetigte Links, deterministisch
  2. Fuzzy Matching  — Score-basiert, Schwellwert konfigurierbar
  3. kein Match      — offen, zur manuellen Klaerung
        |
        v
Konfidenzbewertung
  "stark"   → direkter Schreibpfad nach Neo4j
  "schwach" → Review-Tab (Bestaetigen / Ablehnen / manuell verknuepfen)
  offen     → Review-Tab
        |
        v
Neo4j-Wissensgraph
```

Der LLM liest das Dokument und benennt, was er gefunden hat.
Der Code übernimmt Validierung, Matching und Entscheidung — der LLM
erfindet keine CMDB-Einträge und schreibt nie selbst in den Graphen.

---

## Aktueller Stand

Das Projekt ist noch im Aufbau, hat aber bereits einen funktionierenden vertikalen Schnitt:

- OpenAI-kompatibler LLM-Client
- BPMN-, TXT-, DOCX- und PDF-Verarbeitung über einen gemeinsamen semantischen Extraktionspfad
- BPMN-Transformer für sehr grosse BPMN/XML-Dateien als vorbereitender, LLM-freier Reduktionsschritt
- Rohsicht und deduplizierte Arbeitssicht für extrahierte Anwendungen
- CMDB-Matching mit Vorrang kuratierter Entscheidungen aus Neo4j, mehreren Kandidaten und Fuzzy Matching
- Neo4j-Write-Pfad für Prozesse, Organisationseinheiten und bestätigte bzw. starke Anwendungslinks als `DIENT`-Kanten mit `raw_name`- und `source`-Property
- schwache Fuzzy-Matches mit CMDB-Treffer werden als `KÖNNTE_DIENEN`-Kanten in Neo4j geschrieben und im Chat abfragbar
- Ablehnungen werden als `(:Ablehnung)`-Knoten in Neo4j persistiert; Pipeline liest bestätigt/abgelehnt direkt aus Neo4j
- Promote/Reject direkt in Neo4j: Bestätigung löscht `KÖNNTE_DIENEN` und schreibt `DIENT`; Ablehnung erzeugt `(:Ablehnung)`-Knoten
- normalisierte CMDB-Sicht für `Anwendung`, `Schnittstelle` und `Server`
- technischer CMDB-Write-Pfad für `USES_INTERFACE` und `RUNS_ON`
- erste CMDB-Ownership-Logik mit direktem 1:1-Match oder Kandidatenbildung für Organisationseinheiten
- natürlichsprachlicher Chat-Layer: LLM als Orchestrator, generiert und führt Cypher-Abfragen selbstständig aus und formuliert die Antwort
- zwei Chat-Modi: `prompt-only` (LLM gibt Cypher als Textblock aus, kompatibel mit lokalen Modellen) und `tool-use` (formales Function Calling, LLM kann mehrere Queries pro Turn ausführen)
- vollständigige Gesprächshistorie als Grundlage für Folgefragen, Präzisierungen und Kontextwechsel ohne imperativische Code-Zustandsverwaltung
- schema-konservativer System-Prompt mit Rollenbeschreibung, Graph-Schema und Cypher-Regeln; zentraler Prompt in `prompts/chat_system.md`
- kanonisches Query-Schema in `graph_schema.py` als gemeinsame Grundlage für Prompting und Validierung
- deterministische Alias-Anreicherung bei leeren Ergebnissen: Hinweise auf bekannte Alternativbegriffe werden dem LLM mitgegeben
- benutzerverständliche Übersetzung technischer Query-/Validierungsfehler im Chat statt roher Cypher- oder Treibertexte
- Organisationseinheiten-Kandidaten aus Prozessimport und CMDB-Sync als `(:OrgKandidat)`-Knoten in Neo4j; Rollen-Markierungen als `role_only`-Property auf `(:Rolle)`
- Alias-Projektion nach Neo4j für kuratierte Kurzformen oder Fehlbezeichnungen aus manuellen App-Mappings und Org-Mappings
- deterministische Alias-Auflösung im Query-Lookup, wenn direkte Namenssuche keinen Treffer liefert
- Streamlit-UI mit 6 Tabs (`Kommunikation`, `Import`, `Zuordnungen`, `Organisation`, `EA-Modell`, `Konfiguration`)
- BRIDGR-Wordmark im App-Header sowie optionaler Darkmode-Umschalter (pro Sitzung gemerkt)
- Rollen-Dropdown im App-Header (`Benutzer`, `Experte`, `Architekt`, `Konfigurator`) blendet sichtbare Tabs zur Komplexitätsreduktion ein/aus (pro Sitzung gemerkt, keine Zugriffskontrolle)
- persistente Laufartefakte in `Output/`
- optionales `debug.log` für Query-/LLM-Diagnose im Output-Ordner
- aktionsfähige Review-Liste für `Bestaetigen`, `Ablehnen` und `manuellen Link anlegen`
- Hinweise auf uneinheitliche Prozessnotation bei mehrfach extrahierten Rohvarianten
- ArchiMate Exchange Format 3.0 und 3.1 als vollständigige Import- und Export-Quelle
- vollständigiger ArchiMate-Motivation-Layer: `Stakeholder`, `Kontext`, `Anforderung` als eigene BRIDGR-Labels; Relationen `BEEINFLUSST`, `IST_VERBUNDEN_MIT`
- quellübergreifende Identitätsauflösung: Prozess- und Anwendungs-Nodes werden beim Nachimport (z.B. ArchiMate nach CMDB oder umgekehrt) per Namensabgleich zusammengeführt statt dupliziert
- ArchiMate-Kandidaten werden direkt als Nodes angelegt; Beziehungen können importiert werden ohne auf Kandidatenbestätigung zu warten
- Fuzzy-Matching im ArchiMate-Import arbeitet nur gegen einen Pre-Import-Snapshot; Elemente desselben Imports erkennen einander nicht als Kandidaten
- Tab 4 (Organisation) zeigt OrgEinheiten direkt aus Neo4j inkl. ArchiMate-importierter `BusinessActor`-Elemente
- manuelle fachliche Eingriffe werden als `ManualDecision` in Neo4j protokolliert
- Rücknahme-Logik für manuelle Entscheidungen inklusive Merge-Rücknahme
- Konsolidierung von Organisationseinheiten und Prozessen per Merge inklusive Alias-Fortführung des Quellnamens auf den Zielknoten
- Merge-Precheck mit Beziehungszählung, Dublettenhinweis, Alias-Übernahme und kompakter Wirkungszusammenfassung
- automatische, validierte Graph-Snapshots vor Prozessimport, expliziter CMDB-Synchronisation und Merge
- Wiederherstellung validierter Snapshots im Tab `Konfiguration` mit Pre-Restore-Snapshot und expliziter Bestätigung

Hinweis zur Wiederherstellung: Sie ersetzt den gesamten Inhalt der konfigurierten
Neo4j-Datenbank. Verwenden Sie dafür ausschließlich eine dedizierte BRIDGR-Datenbank
und konfigurieren Sie deren Namen über `neo4j_database`.

Wichtige Einordnung:

- Die aktuelle Implementierung unterstützt BPMN, TXT, DOCX und PDF über einen gemeinsamen semantischen Extraktionspfad.
- Der Chat-Layer basiert seit v0.19 auf dem LLM-als-Orchestrator-Muster; imperativische Gesprächszustandsverwaltung (Disambiguierungslogik, Fokus-Entität) entfällt aus dem Code.

Noch nicht umgesetzt:

- vollständigige UI-/Review-Unterstützung für alle neuen CMDB-Objekttypen
- Unterstützung weiterer CMDB-Dateiformate jenseits von CSV
- separate Read-only-DB-Identität für den Query-Layer
- ArchiMate Views/Viewpoints im Export; selektiver Export (setzt Views voraus)
- Node-Merge beim Bestätigen eines ArchiMate-Fuzzy-Match-Kandidaten (Finding #25)

## Projektstruktur

```text
BRIDGR/
├── core/                   # geteilte Grundbausteine: Config, Neo4j, LLM, Schema, Konstanten
├── processing/             # Pipeline, Import, CMDB, Query-Layer, Artefakte
├── services/               # UI-ausgeloeste Seiteneffekte und Orchestrierung
├── ui/                     # Streamlit-Tabmodule
├── skills/                 # Fachlogik fuer Extract, Match, Review, Graph
├── prompts/                # LLM-Prompts
├── data/                   # Archive, Hilfsdaten und archimate_mapping.json
├── Input/                  # Prozessdokumente und CMDB-Dateien des Benutzers
├── Output/                 # erzeugte Laufartefakte und spaetere Exportziele
├── scripts/                # Wartungsskripte (nicht fuer Produktion)
├── app.py                  # Streamlit-Entrypoint
├── main.py                 # CLI-Einstieg fuer Pipeline-Laeufe
└── config.example.json     # Vorlage für die technische Konfiguration
```

## Input und Output

Reservierte Ordner:

- `Input/`: Hier legt der Benutzer zu importierende Prozessdokumente und CMDB-Dateien ab.
- `Output/`: Hier legt BRIDGR erzeugte Artefakte ab. Aktuell sind das vor allem Laufartefakte; später soll der Ordner auch für menschenlesbare Exporte verwendet werden.
- `data/input_archive/`: Hierhin verschiebt BRIDGR nach erfolgreichem Import verarbeitete Prozessdateien aus der Inbox.

Aktuell relevante Output-Dateien:

- `Output/import_state.json`: letzter bekannter Dokumentzustand
- `Output/latest_run.json`: letzter gespeicherter Import-/Reviewlauf für die UI; wird nach Prozessimporten und nach einer CMDB-Synchronisation für die Neubewertung bestehender Zuordnungen aktualisiert
- `Output/debug.log`: optionale JSONL-Diagnoseausgabe bei aktiviertem Debug-Modus

Entscheidungspersistenz:

- Bestätigte Anwendungslinks leben als `DIENT`-Kanten in Neo4j (mit `raw_name`- und `source`-Property).
- Schwache Kandidaten leben als `KÖNNTE_DIENEN`-Kanten in Neo4j.
- Ablehnungen leben als `(:Ablehnung)`-Knoten in Neo4j.
- Offene Organisationseinheiten-Kandidaten leben als `(:OrgKandidat)`-Knoten in Neo4j.

## Konfiguration

Erstellen Sie die lokale Laufzeitkonfiguration einmalig aus der veröffentlichten Vorlage:

```powershell
Copy-Item config.example.json config.json
```

`config.json` enthält lokale Verbindungs- und Laufzeiteinstellungen und wird nicht
versioniert.

Wichtige Felder:

- `llm_base_url`: OpenAI-kompatibler Endpoint
- `llm_model`: zu verwendendes Modell
- `llm_api_key_env`: Name der Umgebungsvariable für den API-Key
- `llm_timeout_seconds`: Timeout für Requests an den LLM-Endpoint
- `neo4j_url`: Neo4j-Bolt-URL
- `neo4j_user`: Neo4j-Benutzer
- `neo4j_password`: Neo4j-Passwort
- `neo4j_database`: optionaler Neo4j-Datenbankname, für Aura typischerweise die Instanz-ID
- `input_path`: gemeinsamer Eingabeordner für Prozessdokumente und CMDB-Dateien
- `cmdb_type_files`: Mapping von Objektart auf CSV-Dateiname, z. B. `{"application": "Anwendungen.csv", "server": "Server.csv", "interface": "Schnittstellen.csv"}`; wenn leer, wird das Legacy-Format verwendet
- `cmdb_uuid_column`: ID-Spalte aller CMDB-Typ-Dateien
- `cmdb_name_column`: Namensspalte aller CMDB-Typ-Dateien
- `cmdb_server_type_column`: Server-Untertyp `physical` oder `virtual` (nur in der Server-Datei)
- `cmdb_owner_name_column`: Owner-/Verantwortungsbezeichnung aus der CMDB
- `cmdb_runs_on_column`: Spaltenname für Server-IDs in der Anwendungsdatei (Standard: `runs_on`)
- `cmdb_uses_interfaces_column`: Spaltenname für Schnittstellen-IDs in der Anwendungsdatei (Standard: `uses_interfaces`)
- `cmdb_multivalue_separator`: Trennzeichen für mehrere Ziel-IDs in einer Zelle (Standard: `|`, konfigurierbar für CMDB-Exporte wie Jira Asset Management)
- `cmdb_filename`: Legacy — aktive gemischte Entities-Datei (wird ignoriert wenn `cmdb_type_files` gesetzt)
- `cmdb_entity_type_column`: Legacy — Typ-Spalte in der gemischten Entities-Datei
- `cmdb_relations_filename`: Legacy — optionale separate Relations-Datei
- `cmdb_relation_source_column`: Legacy — Quell-ID-Spalte der Relations-Datei
- `cmdb_relation_type_column`: Legacy — Beziehungstyp-Spalte der Relations-Datei
- `cmdb_relation_target_column`: Legacy — Ziel-ID-Spalte der Relations-Datei
- `output_path`: Ziel für Laufartefakte
- `last_run_mode`: Standardlaufmodus für den Import (`full` oder `partial`)
- `chat_mode`: Chat-Betriebsmodus (`prompt-only` oder `tool-use`); Default: `prompt-only`
- `debug_mode`: schreibt bei aktivierter Diagnose zusätzliche Ereignisse nach `Output/debug.log`
- `snapshot_retention_count`: Anzahl gültiger Graph-Snapshots unter `Output/snapshots/`, die nach erfolgreichen Schreiboperationen aufbewahrt werden (Standard: `10`)

Hinweise zur UI:

- Im Konfigurations-Tab stehen LLM-Presets für `OpenAI` und `Ollama` zur Verfügung.
- Das Feld `llm_api_key_env` bzw. `API-Schluessel (Umgebungsvariable)` erwartet den Namen
  der Umgebungsvariable, nicht den geheimen Schlüsselwert selbst, zum Beispiel
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
  "cmdb_server_type_column": "server_type",
  "cmdb_owner_name_column": "owner_name",
  "cmdb_type_files": {
    "application": "cmdb_applications.csv",
    "server": "cmdb_servers.csv",
    "interface": "cmdb_interfaces.csv"
  },
  "cmdb_runs_on_column": "runs_on",
  "cmdb_uses_interfaces_column": "uses_interfaces",
  "cmdb_multivalue_separator": "|",
  "input_path": "Input",
  "output_path": "Output"
}
```

## LLM-Modell-Empfehlungen

BRIDGR stellt zwei unterschiedliche Anforderungen an das LLM: strukturierte JSON-Extraktion
aus Prozessdokumenten und natürlichsprachliche EA-Analyse im Chat. Beide Aufgaben profitieren
von Modellen mit guter Instruction-Following-Qualität.

| Größenklasse | Eignung | Hinweis |
| --- | --- | --- |
| ~8B | Demo / einfache Tests | Deutliche Schwächen bei komplexer Extraktion und Analyse |
| 12B–14B | Eingeschränkt, stark modellabhängig | Sorgfältige Evaluation vor Produktiveinsatz empfohlen |
| 26B+ | Empfohlene Untergrenze für ernsthafte Nutzung | Konsistentere Ergebnisse, weniger manueller Review-Aufwand |
| Cloud (z.B. GPT-4o) | Beste Qualität | Datenschutz- und Kostenanforderungen beachten |

**Getestete Modelle:** DeepSeek-R1 8B, Ministral 8B, Gemma 4 12B, Qwen 2.5 14B, Gemma 4 26B, GPT-4o

**Erfahrungen aus der Praxis:**

- 8B-Modelle sind für einfache Chat-Interaktionen oft ausreichend, zeigen jedoch deutliche
  Schwächen bei komplexen Extraktions-, Matching- und Analyseaufgaben.
- 12B–14B-Modelle liefern stark schwankende Ergebnisse; das Ergebnis hängt stark vom
  konkreten Modell und der Quantisierung ab. Validiertes Modell für Extraktion und Chat
  auf einer RTX-GPU mit 16 GB VRAM: `qwen2.5:14b` (Q4_K_M, ~9 GB VRAM).
- Für ernsthafte Nutzung empfehlen wir mindestens die Größenklasse 26B. Größere Modelle
  reduzieren erfahrungsgemäß den manuellen Review-Aufwand und liefern konsistentere Ergebnisse.
- Eine größere Parameterzahl bedeutet nicht automatisch bessere Extraktion. Modelle, die bei
  JSON-Schema-Constraints instabil werden oder VRAM-bedingt auf CPU ausweichen, können trotz
  theoretisch höherer Kapazität schlechter abschneiden als kleinere, besser passende Modelle.
- Nach jedem Modellwechsel einen vollständigigen Import-Lauf durchführen, bevor der Wechsel
  als stabil gilt.

## Secrets und `.env`

Lokale Secrets werden nicht im Code abgelegt.

Unterstützte Pfade für `.env`-Dateien:

- `.env`
- `Specs/.env`

Aktuell erwartet das Projekt für Webprovider typischerweise:

- `OPENAI_API_KEY`
- `NEO4J_URI`
- `NEO4J_USERNAME`
- `NEO4J_PASSWORD`
- `NEO4J_DATABASE`

Für Neo4j-Aura können die Zugangsdaten direkt über `.env` kommen. Wenn in `config.json` noch die lokalen Defaults (`bolt://localhost:7687`, `neo4j`) stehen, werden die gesetzten `NEO4J_*`-Variablen automatisch bevorzugt. Das Passwort aus `NEO4J_PASSWORD` wird in der UI verwendet, aber beim Speichern nicht stillschweigend nach `config.json` zurückgeschrieben.

Eine Vorlage liegt in:

- `Specs/.env.example`

## Lokale Nutzung

### 1. Abhängigkeiten

Das Projekt ist aktuell für Python `>=3.10` vorbereitet.

Empfohlener Weg für die lokale Nutzung:

```powershell
python -m pip install -r requirements-dev.txt
```

Hinweis:

- Eine editable Installation über `python -m pip install -e .[dev]` ist für BRIDGR aktuell nicht nötig.
- `streamlit` ist aktuell bewusst unter `1.57` gehalten. Die 1.57er-Linie führt durch die neue Starlette-basierte Serverumstellung lokal zu Import-/Kompatibilitätsproblemen.

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

Aktuell verfügbar:

- Session-Chat für natürlichsprachliche Fragen zur IT-Landschaft
- LLM als Orchestrator: entscheidet eigenständig, ob und welche Cypher-Abfrage benötigt wird
- `prompt-only`-Modus: LLM gibt Cypher als Textblock aus, Code extrahiert und führt aus (kompatibel mit lokalen Modellen)
- `tool-use`-Modus: formales Function Calling, LLM kann mehrere Queries pro Turn ausführen
- vollständigige Gesprächshistorie für Folgefragen, Präzisierungen und Kontextwechsel
- deterministische Alias-Anreicherung: bei leeren Ergebnissen werden bekannte Alternativbegriffe als Hinweise an den LLM mitgegeben
- Cypher-Retry bei korrigierbaren Syntaxfehlern (bis zu 2 Versuche mit Fehlerfeedback an den LLM)
- Read-only-Validierung auf verbotene Write-Tokens sowie auf das kanonische Query-Schema aus `core/graph_schema.py`
- Query gegen Neo4j ausführen, Ergebnis in natürliche Sprache umformulieren
- technische Query-/Validierungsfehler in benutzerverständliche Hinweise übersetzen
- generierten Cypher als technische Details anzeigen
- sofortiges visuelles Feedback nach Fragenabsendung: Nutzerfrage und Verarbeitungs-Spinner erscheinen direkt im Chat-Bereich

### Tab 2 - Import

Aktuell verfügbar:

- Prozessdateien in BPMN, XML, TXT, DOCX und PDF importieren
- Importmodus `full` oder `partial` direkt beim Starten des Imports wählen
- einzelne BPMN/XML-Dateien vor dem eigentlichen Import in kompakte Transform-Dateien überführen
- aktive CMDB-Typ-Dateien innerhalb des Input-Ordners wählen
- CMDB nach Neo4j synchronisieren und dabei den letzten gespeicherten Lauf gegen die aktuelle CMDB neu bewerten
- Laufzeit erfolgreicher Pipeline-Läufe direkt in der UI anzeigen
- verarbeitete Prozessdateien nach erfolgreichem Import transparent nach `data/input_archive/<timestamp>/` verschieben

### Tab 3 - Zuordnungen

Aktuell verfügbar:

- Review für den letzten Import oder eine manuell gewählte Teilmenge öffnen
- letzten gespeicherten Lauf aus `Output/latest_run.json` anzeigen
- letzten Importkontext inklusive Archivpfad anzeigen
- Statusfilter für Dokumente
- Sortierung der Review-Liste nach Prozess oder nach Anwendungsbezeichner (umschaltbar)
- aktionsfähige Review-Liste mit `Bestaetigen`, `Ablehnen` und `Manuell anlegen`
- Checkbox-Spalte für Mehrfachauswahl: bei gültiger Selektion (gleicher normalisierter raw_name + gleiche cmdb_id) bestätigt ein Klick auf `Bestaetigen` alle markierten Einträge auf einmal
- bei ungültiger Mehrfachauswahl (gemischte Bezeichner oder CMDB-Ziele): rotes Banner + alle Aktionsbuttons der markierten Zeilen deaktiviert
- `Manuell anlegen`-Dropdown ist alphabetisch sortiert
- mehrere schwache CMDB-Kandidaten pro Prozessanwendung anzeigen
- Dokumentdetails mit Prozesskontext und technischen Rohdaten (reine Ansicht, keine Aktionen)
- Hinweise auf mögliche Mehrfachnotation derselben Anwendung innerhalb eines Prozesses
- starke und KB-bestätigte Links werden als `DIENT`-Kanten in Neo4j geschrieben; schwache fuzzy-Kandidaten als `KÖNNTE_DIENEN`-Kanten (im Review-Tab und im Chat abfragbar)
- Bestätigung im Review löscht `KÖNNTE_DIENEN` und schreibt `DIENT` direkt in Neo4j (kein Dokument-Re-Run als Träger)
- Ablehnungen im Review erzeugen `(:Ablehnung)`-Knoten in Neo4j; der nächste Import überspringt abgelehnte Bezeichnungen
- nach einer CMDB-Synchronisation können bisher offene oder schwache Fälle des letzten Laufs automatisch verschwinden, wenn die aktualisierte CMDB jetzt einen starken Match liefert
- Bereich `Datenpflege` mit `Prozesse konsolidieren` für den Merge fachlicher Prozess-Dubletten
- Bereich `Datenpflege` mit `Letzte manuelle Aenderungen` und rücknehmbaren Entscheidungen für sichere Fälle
- menschenlesbare Kontexte in der Änderungshistorie, z.B. Prozessname und Eigentümer statt nur technischer IDs

### Tab 4 - Organisation

Aktuell verfügbar:

- bekannte Organisationseinheiten manuell pflegen
- Abschnitte als initial eingeklappte Bereiche für bessere Übersicht
- Organisationseinheiten direkt als `:OrgEinheit` nach Neo4j synchronisieren
- offene Kandidaten aus unstrukturierten Dokumenten anzeigen
- offene Kandidaten aus CMDB-Owner-Bezeichnungen anzeigen
- Kandidaten auf bestehende Organisationseinheiten mappen
- Kandidaten als neue Organisationseinheit übernehmen
- Kandidaten abweisen
- vorgeschlagene Prozess-Eigentümer vor den manuell zu pflegenden Prozessen anzeigen
- Prozesse ohne Eigentümer einzeln oder per Batch derselben Organisationseinheit zuordnen
- Rollen bestehenden Organisationseinheiten zuordnen oder direkt als neue Organisationseinheit anlegen
- Begriffe explizit als `Rolle` markieren, wenn bewusst keine Zuordnung zu einer Organisationseinheit erfolgen soll
- neu bestätigte oder neu angelegte Organisationseinheiten nach dem UI-Rerun sofort in den folgenden Auswahllisten verfügbar machen
- gemappte Kandidaten als `(:Alias)-[:KANN_MEINEN]->(:OrgEinheit)` nach Neo4j projizieren
- bei gemappten oder übernommenen Kandidaten betroffene Prozesse im letzten Lauf gezielt neu bewerten und `VERANTWORTET`-Beziehungen in Neo4j nachziehen
- Abschnitte gruppiert in `Offene Aufgaben`, `Verwaltung` und `Historie`
- Bereich `Organisationseinheiten konsolidieren` für den Merge fachlicher Dubletten
- Merge übernimmt passende Beziehungen auf den Zielknoten, vermeidet Duplikate und führt den Quellnamen als Alias auf dem Zielobjekt weiter

Wichtige Einordnung:

- manuell angelegte Organisationseinheiten können zunächst ohne Prozessbezug im Graph existieren
- CMDB-Owner mit sicherem 1:1-Match können direkt als `VERANTWORTET` auf CMDB-Objekte landen
- unsichere CMDB-Owner werden wie andere Org-Kandidaten über denselben Review-Pfad behandelt
- `ManualDecision` ist ein interner Betriebs-Knotentyp und wird bewusst nicht für den Chat freigegeben
- Merge-Rücknahmen arbeiten snapshot-basiert aus dem Entscheidungs-Payload

### Tab 5 - EA-Modell

Aktuell verfügbar:

- Import-Mapping konfigurieren: eine Zeile pro ArchiMate-Typ, beliebig viele Einträge können auf dasselbe BRIDGR-Label zeigen (m:1); Zeilen einzeln löschbar, neue Einträge hinzufügbar
- Export-Mapping konfigurieren: kanonischer ArchiMate-Typ pro BRIDGR-Label für Nodes ohne ArchiMate-Herkunft
- Beziehungs-Mapping konfigurieren (optional): akzeptierte Importtypen und kanonischer Exporttyp pro Label-Paar
- ArchiMate Exchange Format 3.x importieren; übersprungene Typen mit Anzahl anzeigen
- Graphen als ArchiMate Exchange Format 3.x exportieren (vollständigiger Graph, keine Views/Viewpoints)
- Export-Precheck: vor dem Export werden Nodes ohne archimate_type angezeigt (nach Label gruppiert), vorgeschlagene Typen können per Gruppe oder individuell pro Node bestätigt oder geändert werden; Bestätigung schreibt ausschliesslich archimate_type (Attribut-Eigentümer-Prinzip)
- Roundtrip-Konsistenz: ArchiMate-importierte Nodes behalten ihren originalen archimate_type beim Export

### Tab 6 - Konfiguration

Aktuell verfügbar:

- LLM-Presets für `OpenAI` und `Ollama`
- LLM-Endpoint konfigurieren
- Modellnamen setzen
- API-Key-Umgebungsvariable setzen
- LLM-Timeout konfigurieren
- Neo4j-URL, User, Passwort und optionalen Datenbanknamen setzen
- gemeinsamen Input- und Output-Pfad setzen
- CMDB-Feldmapping für das erweiterte Entities-/Relations-Modell setzen
- Fuzzy-Threshold setzen
- Debug-Modus aktivieren
- Chat-Modus `prompt-only` oder `tool-use` wählen
- Modellliste über `/v1/models` abrufen
- Neo4j-Erreichbarkeit anhand der aktuell wirksamen Konfiguration prüfen
- LLM-Erreichbarkeit und Modellverfügbarkeit getrennt prüfen
- letzte validierte Snapshots anzeigen und einen Snapshot nach expliziter Bestätigung wiederherstellen

## BPMN-Transformer für grosse Modelle

Der BPMN-Transformer ist ein vorbereitender Schritt für sehr grosse oder sehr technische BPMN/XML-Dateien.

Problem:

- grosse Gesamtprozessmodelle enthalten sehr viel XML-Rauschen
- lokale Modelle laufen bei Roh-BPMN leichter in Timeouts oder liefern kein gültiges JSON
- für den Initialload in Unternehmen sind grosse BPMN-Dateien eher die Regel als die Ausnahme

Lösung:

- der Transformer liest die ausgewählte BPMN/XML-Datei ohne LLM
- er extrahiert daraus kompakte Prozesshinweise: Prozessnamen, Lane-Bezeichner und modellnahe Anwendungsreferenzen
- das Ergebnis wird als Textdatei unter `Input/transformed/` gespeichert

Dateiname:

- `<originalname>__bridgr_transform.txt`

Nutzung:

1. grosse BPMN/XML-Datei in den aktuellen `Input Path` legen
2. im Tab `Import` die gewünschte BPMN/XML-Datei bei `BPMN fuer Transformation` auswählen
3. `BPMN transformieren` auslösen
4. den `Input Path` auf `Input/transformed/` umstellen oder die erzeugte Datei gezielt für weitere Imports nutzen

Ziel:

- weniger Kontext für das LLM
- deutlich kleinere Eingabedateien
- stabilere Extraktion bei lokal laufenden Modellen
- besser kontrollierbarer Initialload für grosse Unternehmens-BPMNs

Wichtige Einordnung:

- der Transformer ersetzt keine fachliche BPMN-Auswertung
- er ist bewusst eine pragmatische Vorreduktion für den LLM-zentrierten Importpfad
- Roh-BPMN und transformierte Datei können parallel im Projekt bestehen

## Debug-Modus

Wenn `Debug Mode` im Tab `Konfiguration` aktiviert ist:

- schreibt BRIDGR Diagnoseereignisse nach `Output/debug.log`
- Query-Fehler enthalten Frage, Fehlermeldung und den erzeugten Cypher
- die Datei ist als JSONL aufgebaut und für lokale Fehlersuche gedacht

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
- Query-Layer-Happy-Path inkl. natürlicher Antwort und Mehrdeutigkeitsbehandlung
- Pipeline-Happy-Path, partielle Imports und Laufartefakte
- CMDB-Normalisierung für Entities und Relations
- Aufbereitung der UI-Statusdaten und Warnhinweise
- KB-Aktionen für kandidatenspezifisches Bestätigen und Ablehnen
- Graph-Write-Pfad inkl. `DIENT` (stark), `KÖNNTE_DIENEN` (schwach), Promote/Reject und `(:Ablehnung)`-Knoten
- ArchiMate-Import (Parser, Namenswahl, Identity Resolution, Beziehungen) und Export (Roundtrip, Typ-Mapping, XML-Validierung)
- Export-Precheck: Nodes ohne archimate_type abfragen, Typ-Schreiben mit Attribut-Eigentümer-Semantik

## Hinweise

- Die Spezifikationsdateien unter `Specs/` sind Referenzdokumente und werden nicht ungefragt umorganisiert.
- Der aktuelle Code folgt bewusst kleinen, inkrementellen Schritten und bildet noch nicht den kompletten Zielumfang aus der Architektur ab.
- Obwohl die Kommunikation und Spezifikation deutsch sind, bleiben Variablennamen und Code-Kommentare auf Englisch.

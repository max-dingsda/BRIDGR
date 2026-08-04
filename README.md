# BRIDGR

BRIDGR ist ein Helfer für Unternehmensarchitekten und ein Chatbot für alle, die an Unternehmensarchitekturthemen interessiert sind. Anwender müssen weder BPMN noch ArchiMate selbst beherrschen oder erstellen: Vorhandene Prozessdokumente und Architekturmodelle können importiert und gemeinsam in einem Wissensgraphen verknüpft werden. Ein LLM unterstützt die natürlichsprachliche Abfrage; der Code validiert und führt die zugrunde liegenden Graphabfragen kontrolliert aus.

Vorarbeiten beschränken sich auf die Bereitstellung der vorhandenen Informationen:

- Prozesse können als BPMN oder als unstrukturierte Textdokumente geliefert werden.
- Ein bestehendes Architekturmodell kann über ArchiMate-XML eingelesen werden, muss es aber nicht.
- CMDB-Informationen werden als CSV erwartet; die Spaltenzuordnung ist konfigurierbar.

## Wie funktioniert BRIDGR?

Eine detailliertere Beschreibung enthält die [Benutzeranleitung](Specs/Benutzeranleitung_BRIDGR.md).

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
  1. Kuratierte Entscheidungen (Neo4j) — bestätigte Links, deterministisch
  2. Fuzzy Matching  — Score-basiert, Schwellwert konfigurierbar
  3. kein Match      — offen, zur manuellen Klärung
        |
        v
Konfidenzbewertung
  "stark"   → direkter Schreibpfad nach Neo4j
  "schwach" → Review-Tab (Bestätigen / Ablehnen / manuell verknüpfen)
  offen     → Review-Tab
        |
        v
Neo4j-Wissensgraph
```

Das LLM identifiziert im aufbereiteten Dokumenttext relevante Informationen.
Der Code übernimmt Validierung, Matching und Entscheidung — der LLM
erfindet keine CMDB-Einträge und schreibt nie selbst in den Graphen.

---

## Aktueller Reifegrad

BRIDGR bietet bereits einen vollständigen Arbeitsfluss aus Import, Zuordnung,
Organisation, EA-Modell, Konfiguration und Kommunikation. Die sechs Tabs decken
Prozess- und CMDB-Import, den Review offener Zuordnungen, Organisationspflege,
ArchiMate-Import und -Export, Laufzeitkonfiguration sowie die Chat-Abfrage ab.

Für den Betrieb wird eine dedizierte Neo4j-Datenbank benötigt. Vor jedem
Prozessimport, jeder CMDB-Synchronisation und jedem Merge erstellt BRIDGR einen
validierten Snapshot. Noch nicht vorgesehen sind unter anderem ArchiMate
Views/Viewpoints im Export und eine vollständige UI-Unterstützung für alle
CMDB-Objekttypen.

Die fachlichen und technischen Details dokumentiert die
[Architekturbeschreibung](Specs/Bridgr_Architektur_v29.md).

---

## Projektstruktur

```text
BRIDGR/
├── core/                   # geteilte Grundbausteine: Config, Neo4j, LLM, Schema, Konstanten
├── processing/             # Pipeline, Import, CMDB, Query-Layer, Artefakte
├── services/               # UI-ausgelöste Seiteneffekte und Orchestrierung
├── ui/                     # Streamlit-Tabmodule
├── skills/                 # Fachlogik für Extract, Match, Review, Graph
├── prompts/                # LLM-Prompts
├── data/                   # Archive, Hilfsdaten und archimate_mapping.json
├── Input/                  # Prozessdokumente und CMDB-Dateien des Benutzers
├── Output/                 # erzeugte Laufartefakte und spätere Exportziele
├── scripts/                # Wartungsskripte (nicht für Produktion)
├── app.py                  # Streamlit-Entrypoint
├── main.py                 # CLI-Einstieg für Pipeline-Läufe
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

Mehr Informationen zur Architektur finden sich in der
[Architekturbeschreibung](Specs/Bridgr_Architektur_v29.md).

## Konfiguration

Alternativ zur nachfolgenden Beschreibung kann die Konfiguration auch vollständig über die Oberfläche erfolgen. Dazu einfach in das BRIDGR Verzeichnis wechseln und die Anwendung starten:

```powershell
streamlit run app.py
```

Danach als Rolle (Im Dropdownmenü oben rechts) "Konfigurator" auswählen, auf den "Konfigurations-Tab" wechseln und alle Informationen erfassen.

*Hinweis zur LLM-Auswahl*: Aktuell werden nur OpenAI-kompatible LLM-Anbindungen ermöglicht.

*Konfiguration via JSON-File:*

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
- `output_path`: Ziel für Laufartefakte
- `last_run_mode`: Standardlaufmodus für den Import (`full` oder `partial`)
- `chat_mode`: Chat-Betriebsmodus (`prompt-only` oder `tool-use`); Default: `prompt-only`
- `debug_mode`: schreibt bei aktivierter Diagnose zusätzliche Ereignisse nach `Output/debug.log`
- `snapshot_retention_count`: Anzahl gültiger Graph-Snapshots unter `Output/snapshots/`, die nach erfolgreichen Schreiboperationen aufbewahrt werden (Standard: `10`)

Hinweise zur UI:

- Im Konfigurations-Tab stehen LLM-Presets für `OpenAI` und `Ollama` zur Verfügung.
- Das Feld `llm_api_key_env` bzw. `API-Schlüssel (Umgebungsvariable)` erwartet den Namen
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
- Nach jedem Modellwechsel einen vollständigen Import-Lauf durchführen, bevor der Wechsel
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

## Tests

```powershell
python -m pytest
```

## Sonderfall BPMN-Transformer (auf dem Import-Tab)

Der BPMN-Transformer ist ein vorbereitender Schritt für sehr große oder sehr technische BPMN/XML-Dateien.

Problem:

- große Gesamtprozessmodelle enthalten sehr viel XML-Rauschen
- lokale Modelle laufen bei Roh-BPMN leichter in Timeouts oder liefern kein gültiges JSON
- für den Initialload in Unternehmen sind große BPMN-Dateien eher die Regel als die Ausnahme

Lösung:

- der Transformer liest die ausgewählte BPMN/XML-Datei ohne LLM
- er extrahiert daraus kompakte Prozesshinweise: Prozessnamen, Lane-Bezeichner und modellnahe Anwendungsreferenzen
- das Ergebnis wird als Textdatei unter `Input/transformed/` gespeichert

Dateiname:

- `<originalname>__bridgr_transform.txt`

Nutzung:

1. große BPMN/XML-Datei in den aktuellen `Input Path` legen
2. im Tab `Import` die gewünschte BPMN/XML-Datei bei `BPMN für Transformation` auswählen
3. `BPMN transformieren` auslösen
4. den `Input Path` auf `Input/transformed/` umstellen oder die erzeugte Datei gezielt für weitere Imports nutzen

Ziel:

- weniger Kontext für das LLM
- deutlich kleinere Eingabedateien
- stabilere Extraktion bei lokal laufenden Modellen
- besser kontrollierbarer Initialload für große Unternehmens-BPMNs

Wichtige Einordnung:

- der Transformer ersetzt keine fachliche BPMN-Auswertung
- er ist bewusst eine pragmatische Vorreduktion für den LLM-zentrierten Importpfad
- Roh-BPMN und transformierte Datei können parallel im Projekt bestehen

## Mitwirken

BRIDGR befindet sich in aktiver Entwicklung. Hinweise zu Fehlern, Ideen für
Verbesserungen und Pull Requests sind willkommen.

- Fehler oder Vorschläge bitte als Issue beschreiben.
- Vor einem Pull Request bitte `python -m pytest` ausführen.
- Besonders hilfreich sind Beiträge zu Importformaten, Tests, Benutzerführung und Architekturmodellierung.

Weitere Informationen zur Nutzung finden sich in der [LICENSE](LICENSE).

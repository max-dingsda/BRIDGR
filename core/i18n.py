from __future__ import annotations

from collections.abc import Mapping
from functools import wraps


SUPPORTED_LOCALES = ("de", "en")
DEFAULT_LOCALE = "de"

_MESSAGES: dict[str, Mapping[str, str]] = {
    "import.archive_pending": {"de": "Der Graph wurde gespeichert. Die Archivierung ist noch ausstehend; wiederholen Sie nur diesen Schritt.", "en": "The graph has been saved. Archiving is still pending; retry only this step."},
    "import.archive_retry": {"de": "Archivierung wiederholen", "en": "Retry archiving"},
    "import.archive_stop": {"de": "Archivierung beenden", "en": "Stop archiving"},
    "import.archive_stop_help": {"de": "Graph und Dateien bleiben erhalten. Bereits verschobene Dateien bleiben im Archiv, übrige Dateien im Eingabepfad. Das Protokoll wird aufbewahrt.", "en": "The graph and all files are retained. Moved files stay in the archive; remaining files stay in the input folder. The journal is kept."},
    "app.tagline": {
        "de": "Wissensgraph aus Prozessen, CMDB und Architekturwissen",
        "en": "Knowledge graph from processes, CMDB, and architecture knowledge",
    },
    "language": {"de": "Sprache", "en": "Language"},
    "locale.de": {"de": "Deutsch", "en": "German"},
    "locale.en": {"de": "Englisch", "en": "English"},
    "tab.chat": {"de": "Kommunikation", "en": "Chat"},
    "tab.import": {"de": "Import", "en": "Import"},
    "tab.review": {"de": "Zuordnungen", "en": "Mappings"},
    "tab.organization": {"de": "Organisation", "en": "Organization"},
    "tab.archimate": {"de": "EA-Modell", "en": "EA Model"},
    "tab.configuration": {"de": "Konfiguration", "en": "Configuration"},
    "role.user": {"de": "Benutzer", "en": "User"},
    "role.expert": {"de": "Experte", "en": "Expert"},
    "role.architect": {"de": "Architekt", "en": "Architect"},
    "role.configurator": {"de": "Konfigurator", "en": "Configurator"},
    "chat.title": {"de": "Kommunikation", "en": "Chat"},
    "chat.subtitle": {"de": "Stellen Sie Fragen zum Wissensgraphen und erhalten Sie nachvollziehbare Antworten mit optionalen Cypher-Details.", "en": "Ask questions about the knowledge graph and receive traceable answers with optional Cypher details."},
    "chat.meta": {"de": "LLM-gestützte Abfrage", "en": "LLM-powered query"},
    "chat.result": {"de": "Ergebnis", "en": "Result"},
    "chat.export_csv": {"de": "Als CSV exportieren", "en": "Export as CSV"},
    "chat.no_matches": {"de": "Keine Treffer gefunden.", "en": "No matches found."},
    "chat.technical_details": {"de": "Technische Details", "en": "Technical details"},
    "chat.new_conversation": {"de": "Neues Gespräch", "en": "New conversation"},
    "chat.input": {"de": "Frage an den Wissensgraphen", "en": "Ask the knowledge graph"},
    "chat.configure_llm": {"de": "Bitte zuerst ein LLM-Modell im Tab Konfiguration einrichten.", "en": "Please configure an LLM model in Configuration first."},
    "chat.configure_neo4j": {"de": "Bitte zuerst die Neo4j-Zugangsdaten im Tab Konfiguration einrichten.", "en": "Please configure Neo4j credentials in Configuration first."},
    "chat.getting_started": {"de": "Startpunkt: Konfigurieren Sie zuerst LLM und Neo4j im Tab **Konfiguration**, starten Sie dann einen Lauf im Tab **Import** — und stellen Sie hier Fragen zur IT-Landschaft.", "en": "Getting started: configure LLM and Neo4j in **Configuration**, run an import in **Import**, then ask questions about your IT landscape here."},
}

_SOURCE_TEXT_KEYS = {
    "Kommunikation": "chat.title",
    "Stellen Sie Fragen zum Wissensgraphen und erhalten Sie nachvollziehbare Antworten mit optionalen Cypher-Details.": "chat.subtitle",
    "LLM-gestützte Abfrage": "chat.meta",
    "Import": "tab.import",
    "Verarbeiten Sie Prozessdateien aus der Inbox und synchronisieren Sie die CMDB nach Neo4j.": "page.import.subtitle",
    "Pipeline und CMDB-Sync": "page.import.meta",
    "Zuordnungen": "tab.review",
    "Prüfen Sie offene Anwendungszuordnungen aus dem letzten Lauf, konsolidieren Sie Prozesse und nehmen Sie manuelle Änderungen zurück.": "page.review.subtitle",
    "Review, Dokumentstatus und Datenpflege": "page.review.meta",
    "Organisation": "tab.organization",
    "Verwalten Sie Organisationseinheiten, Eigentümer und Rollen und konsolidieren Sie Dubletten von Organisationseinheiten.": "page.organization.subtitle",
    "Kandidaten, Eigentümer und Merge": "page.organization.meta",
    "EA-Modell": "tab.archimate",
    "Konfigurieren Sie das ArchiMate-Mapping und führen Sie Import sowie Export des Architekturmodells kontrolliert aus.": "page.archimate.subtitle",
    "Mapping, Import und Export": "page.archimate.meta",
    "Konfiguration": "tab.configuration",
    "Pflegen Sie Laufzeitparameter, Pfade sowie LLM- und Neo4j-Einstellungen für den aktuellen Workspace.": "page.configuration.subtitle",
    "Einstellungen": "page.configuration.meta",
}

# Short UI labels which are reused directly by tab renderers.  Keeping them
# here avoids per-tab translation dictionaries while preserving the original
# German source text as the canonical lookup value.
_SOURCE_TRANSLATIONS: dict[str, str] = {
    "Dokumentstatus": "Document status",
    "Keine Dokumente für den aktuellen Filter gefunden.": "No documents found for the current filter.",
    "Der letzte Import hat folgendes gefunden": "The last import found",
    "Hinweise zur Prozessnotation": "Process notation notes",
    "Bestätigen": "Confirm",
    "Ablehnen": "Reject",
    "Manuell anlegen": "Create manually",
    "Zuordnung für {application} im Prozess {process} auswählen": "Select mapping for {application} in process {process}",
    "Aufgrund der Selektion nicht ausführbar": "Not available due to the selection",
    "CMDB-Ziel": "CMDB target",
    "Ausgewähltes CMDB-Ziel konnte nicht aufgelöst werden.": "The selected CMDB target could not be resolved.",
    "Offene Zuordnungen": "Open mappings",
    "Keine offenen Zuordnungen für den aktuellen Filter.": "No open mappings for the current filter.",
    "Sortierung": "Sort order",
    "Nach Prozess": "By process",
    "Nach Anwendungsbezeichner": "By application name",
    "Ausgewählte Einträge müssen denselben Bezeichner und dieselbe CMDB-Anwendung haben.": "Selected entries must have the same name and CMDB application.",
    "Prozess": "Process",
    "Anwendung im Prozess": "Application in process",
    "Anwendung in der CMDB": "Application in CMDB",
    "Bewertung": "Assessment",
    "Dokumentdetails ({count})": "Document details ({count})",
    "Keine Detaildaten für den aktuellen Filter vorhanden.": "No detailed data is available for the current filter.",
    "Technische Details": "Technical details",
    "Rohanwendungen": "Raw applications",
    "Anwendungen": "Applications",
    "Zuordnungen": "Mappings",
    "Nur letzter Import": "Last import only",
    "Dateien manuell wählen": "Select files manually",
    "Dateien anzeigen": "Show files",
    "Dateien für Überprüfung": "Files for review",
    "Statusfilter": "Status filter",
    "Datenpflege": "Data maintenance",
    "Noch kein gespeicherter Pipeline-Lauf vorhanden.": "No saved pipeline run is available yet.",
    "Es liegt noch keine gespeicherte Auswahl aus dem letzten Import vor.": "No saved selection from the last import is available yet.",
    "Bitte wählen Sie mindestens eine Prozessdatei für die Überprüfung aus.": "Please select at least one process file for review.",
    "Umfang": "Scope",
    "Hier bearbeiten Sie bereits bekannte schwache oder offene Zuordnungen. Es wird kein neuer Import aus der Inbox gestartet.": "Review known weak or open mappings here. No new import is started from the inbox.",
    "Die Ansicht liest den letzten gespeicherten Lauf aus `Output/latest_run.json` und zeigt offene bzw. schwache Zuordnungsfälle zur Bearbeitung.": "This view reads the last saved run from `Output/latest_run.json` and shows open or weak mappings for review.",
    "Letzte manuelle Änderungen": "Recent manual changes",
    "Noch keine manuellen Änderungen im Entscheidungslog vorhanden.": "No manual changes are recorded yet.",
    "Prozesse konsolidieren": "Consolidate processes",
    "Prozess-Quelle": "Source process",
    "Prozess-Ziel": "Target process",
    "Prozess-Merge ausführen": "Execute process merge",
    "Bitte Quelle und Ziel auswählen.": "Please select source and target.",
    "Zu übernehmende Kanten": "Relationships to transfer",
    "Noch keine manuellen Änderungen im Entscheidungslog vorhanden.": "No manual changes are recorded yet.",
    "Für einen Merge werden mindestens zwei Prozesse benötigt.": "At least two processes are required for a merge.",
    "Keine Kanten aus der Quelle gefunden.": "No relationships were found on the source.",
    "Zurücknehmen": "Revert",
    "Manuelle Änderungen konnten nicht geladen werden: {error}": "Manual changes could not be loaded: {error}",
    "Prozesse konnten nicht geladen werden: {error}": "Processes could not be loaded: {error}",
    "Offene Aufgaben": "Open tasks",
    "Verwaltung": "Management",
    "Historie": "History",
    "Organisationseinheiten": "Organizational units",
    "Kandidaten ({count})": "Candidates ({count})",
    "Vorgeschlagene Prozess-Eigentümer ({count})": "Suggested process owners ({count})",
    "Prozesse ohne Eigentümer ({count})": "Processes without an owner ({count})",
    "Nicht zugeordnete Rollen ({count})": "Unassigned roles ({count})",
    "Organisationseinheiten konsolidieren": "Consolidate organizational units",
    "Bereits entschiedene Kandidaten": "Previously decided candidates",
    "Organisation nach Neo4j synchronisieren": "Synchronize organization with Neo4j",
    "Prozesse verwalten": "Manage processes",
    "Neue Organisationseinheit": "New organizational unit",
    "Organisationseinheit hinzufügen": "Add organizational unit",
    "Keine Prozesse im Graphen gefunden.": "No processes found in the graph.",
    "Verantwortliche Prozesse": "Responsible processes",
    "Speichern": "Save",
    "Alle Prozesse haben einen Eigentümer.": "All processes have an owner.",
    "Mehrere Prozesse gleichzeitig zuweisen": "Assign multiple processes at once",
    "Gemeinsamer Eigentümer": "Shared owner",
    "Batch zuweisen": "Assign batch",
    "Eigentümer zuweisen": "Assign owner",
    "Zuweisen": "Assign",
    "Bestätigen": "Confirm",
    "Abweisen": "Reject",
    "Bestehende Organisationseinheit": "Existing organizational unit",
    "Zuordnen": "Map",
    "Als neue Organisationseinheit übernehmen": "Accept as a new organizational unit",
    "Übernehmen": "Accept",
    "Als neue Organisationseinheit anlegen": "Create as a new organizational unit",
    "Anlegen & zuordnen": "Create and assign",
    "Rolle": "Role",
    "Quelle": "Source",
    "Ziel": "Target",
    "Kandidat": "Candidate",
    "Gemappt auf": "Mapped to",
    "Zuletzt gesehen": "Last seen",
    "Merge ausführen": "Execute merge",
    "Aktuell liegen keine offenen Kandidaten vor.": "There are currently no open candidates.",
    "Aktuell liegen keine vorgeschlagenen Prozess-Eigentümer vor.": "There are currently no suggested process owners.",
    "Alle Rollen sind bereits einer Organisationseinheit zugeordnet oder wurden als reine Rolle markiert.": "All roles are already assigned to an organizational unit or marked as role-only.",
    "Noch keine Organisationseinheiten gepflegt.": "No organizational units have been maintained yet.",
    "Noch keine entschiedenen Kandidaten vorhanden.": "No decided candidates are available yet.",
    "Für einen Merge werden mindestens zwei Organisationseinheiten benötigt.": "At least two organizational units are required for a merge.",
    "Mapping konfigurieren": "Configure mapping",
    "Import: ArchiMate → BRIDGR": "Import: ArchiMate → BRIDGR",
    "Export: BRIDGR → ArchiMate": "Export: BRIDGR → ArchiMate",
    "BRIDGR-Label": "BRIDGR label",
    "Export: ArchiMate-Typ": "Export: ArchiMate type",
    "Beziehungs-Mapping bearbeiten": "Edit relationship mapping",
    "Beziehungen": "Relationships",
    "Label-Paar": "Label pair",
    "Import: akzeptierte AM-Typen": "Import: accepted AM types",
    "Export: AM-Typ": "Export: AM type",
    "BRIDGR-Relation": "BRIDGR relationship",
    "Änderungen werden erst nach dem Klick auf 'Mapping speichern' in archimate_mapping.json geschrieben.": "Changes are written to archimate_mapping.json only after clicking 'Save mapping'.",
    "Mapping speichern": "Save mapping",
    "Mapping gespeichert.": "Mapping saved.",
    "Fehler beim Speichern: {error}": "Error while saving: {error}",
    "ArchiMate-Typ": "ArchiMate type",
    "AM-Typ": "AM type",
    "+ Mapping hinzufügen": "+ Add mapping",
    "Offene Zuordnungen": "Open mappings",
    "Übersprungene Beziehungen ({count})": "Skipped relationships ({count})",
    "Import": "Import",
    "ArchiMate-Datei hochladen (.xml oder .archimate)": "Upload ArchiMate file (.xml or .archimate)",
    "Importieren": "Import",
    "Import abgeschlossen: {elements} Elemente importiert{candidate_note}, {skipped_elements} übersprungen, {relations} Beziehungen importiert, {skipped_relations} Beziehungen übersprungen.": "Import completed: {elements} elements imported{candidate_note}, {skipped_elements} skipped, {relations} relationships imported, {skipped_relations} relationships skipped.",
    ", davon {count} zur Prüfung markiert": ", including {count} marked for review",
    "Import fehlgeschlagen: {error}": "Import failed: {error}",
    "Export": "Export",
    "Der Export umfasst immer den vollständigen BRIDGR-Graphen. Teilexporte sind ohne Views/Viewpoints nicht möglich.": "Export always covers the complete BRIDGR graph. Partial exports are not possible without views/viewpoints.",
    "Als ArchiMate exportieren": "Export as ArchiMate",
    "Datenbankabfrage fehlgeschlagen: {error}": "Database query failed: {error}",
    "Bitte Exporttypen prüfen und bestätigen.": "Please review and confirm export types.",
    "Node": "Node",
    "Export-Typ": "Export type",
    "Vorschläge übernehmen und exportieren": "Apply suggestions and export",
    "Fehler beim Schreiben der ArchiMate-Typen: {error}": "Error while writing ArchiMate types: {error}",
    "Abbrechen": "Cancel",
    "Export abgeschlossen: {elements} Elemente, {relations} Beziehungen. Datei: `{path}`": "Export completed: {elements} elements, {relations} relationships. File: `{path}`",
    "Export fehlgeschlagen: {error}": "Export failed: {error}",
    "Konfiguration konnte nicht geladen werden: {error}": "Configuration could not be loaded: {error}",
    "{count} ArchiMate-Element(e) konnten nicht eindeutig zugeordnet werden.": "{count} ArchiMate element(s) could not be mapped unambiguously.",
    "Neo4j-Merge fehlgeschlagen: {error}": "Neo4j merge failed: {error}",
    "{count} Node(s) ohne ArchiMate-Typ gefunden. Bitte Exporttypen prüfen und bestätigen.": "{count} node(s) without an ArchiMate type found. Please review and confirm export types.",
}

_ENGLISH_WORDS = {
    "Aufgrund der Selektion nicht ausführbar": "Not available due to the selection",
    "Ausgewähltes CMDB-Ziel konnte nicht aufgelöst werden.": "The selected CMDB target could not be resolved.",
    "Keine offenen Zuordnungen für den aktuellen Filter.": "No open mappings for the current filter.",
    "Keine Dokumente für den aktuellen Filter gefunden.": "No documents found for the current filter.",
    "Keine Detaildaten für den aktuellen Filter vorhanden.": "No detailed data is available for the current filter.",
    "Noch kein gespeicherter Pipeline-Lauf vorhanden.": "No saved pipeline run is available yet.",
    "Bitte wählen Sie mindestens eine Prozessdatei für die Überprüfung aus.": "Please select at least one process file for review.",
    "Noch keine Snapshots vorhanden. Sie werden vor Import, CMDB-Synchronisation und Merge automatisch erstellt.": "No snapshots are available yet. They are created automatically before import, CMDB synchronization, and merge operations.",
    "Die Wiederherstellung ersetzt den gesamten Inhalt der konfigurierten Neo4j-Datenbank. Verwenden Sie dafür ausschließlich eine dedizierte BRIDGR-Datenbank.": "Restore replaces the entire contents of the configured Neo4j database. Use a dedicated BRIDGR database only.",
    "Änderungen": "Changes", "Aktuelle": "Current", "Aktuell": "Currently", "Alle": "All", "alle": "all",
    "Abbrechen": "Cancel", "Abweisen": "Reject", "anlegen": "create", "Anzahl": "Number", "anzeigen": "show",
    "Änderungen": "Changes", "Aktuelle": "Current", "Alle": "All", "Anwendung": "Application",
    "Anwendungen": "Applications", "Ausgabe": "Output", "auswählen": "select", "Bestätigen": "Confirm",
    "Bestätigte": "Confirmed", "Beziehungen": "Relationships", "bereits": "already", "Bereits": "Already",
    "Datei": "File", "Dateien": "Files", "Datenpflege": "Data maintenance", "Details": "Details",
    "Dokument": "Document", "Dokumente": "Documents", "Eigentümer": "Owner", "Eingabe": "Input",
    "entfernt": "removed", "Fehler": "Error", "gefunden": "found", "gesamten": "entire", "geladen": "loaded",
    "gespeichert": "saved", "Hinzufügen": "Add", "Historie": "History", "konnte": "could", "Kandidaten": "Candidates", "keine": "no", "Keine": "No",
    "Knoten": "Nodes", "Konfiguration": "Configuration", "können": "can", "laden": "load", "letzten": "last", "Letzte": "Recent",
    "manuell": "manual", "Mehrere": "Multiple", "mindestens": "at least", "neu": "new", "Neu": "New", "nicht": "not", "Noch": "No",
    "offene": "open", "Offene": "Open", "Organisation": "Organization", "Organisationseinheit": "organizational unit",
    "Organisationseinheiten": "organizational units", "Prozess": "Process", "Prozesse": "Processes",
    "Quelle": "Source", "Quellen": "Sources", "Rolle": "Role", "Rollen": "Roles", "Sichern": "Save", "sind": "are",
    "Speichern": "Save", "Status": "Status", "übernehmen": "apply", "Übersicht": "Overview", "Verantwortliche": "Responsible",
    "Verwaltung": "Management", "vorhanden": "available", "wählen": "choose", "wurde": "was", "Zurücknehmen": "Revert",
    "zugeordnet": "assigned", "Zuordnen": "Map", "Zuordnungen": "Mappings", "zuerst": "first",
}

_MESSAGES.update({
    "page.import.subtitle": {"de": "Verarbeiten Sie Prozessdateien aus der Inbox und synchronisieren Sie die CMDB nach Neo4j.", "en": "Process files from the inbox and synchronize CMDB data with Neo4j."},
    "page.import.meta": {"de": "Pipeline und CMDB-Sync", "en": "Pipeline and CMDB sync"},
    "page.review.subtitle": {"de": "Prüfen Sie offene Anwendungszuordnungen aus dem letzten Lauf, konsolidieren Sie Prozesse und nehmen Sie manuelle Änderungen zurück.", "en": "Review open application mappings from the last run, consolidate processes, and revert manual changes."},
    "page.review.meta": {"de": "Review, Dokumentstatus und Datenpflege", "en": "Review, document status, and data maintenance"},
    "page.organization.subtitle": {"de": "Verwalten Sie Organisationseinheiten, Eigentümer und Rollen und konsolidieren Sie Dubletten von Organisationseinheiten.", "en": "Manage organizational units, owners, and roles, and consolidate duplicate organizational units."},
    "page.organization.meta": {"de": "Kandidaten, Eigentümer und Merge", "en": "Candidates, owners, and merge"},
    "page.archimate.subtitle": {"de": "Konfigurieren Sie das ArchiMate-Mapping und führen Sie Import sowie Export des Architekturmodells kontrolliert aus.", "en": "Configure the ArchiMate mapping and control the import and export of the architecture model."},
    "page.archimate.meta": {"de": "Mapping, Import und Export", "en": "Mapping, import, and export"},
    "page.configuration.subtitle": {"de": "Pflegen Sie Laufzeitparameter, Pfade sowie LLM- und Neo4j-Einstellungen für den aktuellen Workspace.", "en": "Manage runtime parameters, paths, and LLM and Neo4j settings for the current workspace."},
    "page.configuration.meta": {"de": "Einstellungen", "en": "Settings"},
    "ui.configured_output_path": {"de": "Konfigurierter Ausgabepfad: `{path}`", "en": "Configured output path: `{path}`"},
    "ui.output_path_fallback": {"de": "Der konfigurierte Ausgabepfad ist aktuell nicht beschreibbar. Artefakte werden nach `{path}` geschrieben.", "en": "The configured output path is currently not writable. Artifacts are written to `{path}`."},
    "import.last_run": {"de": "Letzter Lauf: {summary}.", "en": "Last run: {summary}."},
    "import.summary.imported": {"de": "{count} importiert", "en": "{count} imported"},
    "import.summary.no_matches": {"de": "davon {count} ohne erkannte Anwendungen", "en": "including {count} without recognized applications"},
    "import.summary.skipped": {"de": "{count} übersprungen", "en": "{count} skipped"},
    "import.summary.errors": {"de": "{count} mit Fehler", "en": "{count} with errors"},
    "import.not_imported": {"de": "Nicht importierte Dateien ({count})", "en": "Files not imported ({count})"},
    "import.file": {"de": "Datei", "en": "File"},
    "import.reason": {"de": "Grund", "en": "Reason"},
    "import.reason_unchanged": {"de": "Unverändert seit letztem Lauf – übersprungen", "en": "Unchanged since the last run – skipped"},
    "import.reason_error": {"de": "Fehler bei der Verarbeitung", "en": "Processing error"},
    "import.process_import": {"de": "Prozessimport", "en": "Process import"},
    "import.process_intro": {"de": "Der Import verarbeitet neue Prozessdateien aus der Inbox `Input/`; verarbeitete Dateien werden anschließend archiviert. Legen Sie neue Prozessdateien und die aktiven CMDB-Dateien direkt im aktuellen Eingabepfad ab.", "en": "The import processes new process files from the `Input/` inbox; processed files are then archived. Place new process files and active CMDB files directly in the current input path."},
    "import.mode": {"de": "Importmodus", "en": "Import mode"},
    "import.mode_help": {"de": "`full` verarbeitet alle Prozessdateien im aktuellen Eingabepfad. `partial` verarbeitet nur die hier explizit ausgewählten Dateien.", "en": "`full` processes all process files in the current input path. `partial` processes only the files explicitly selected here."},
    "import.start": {"de": "Pipeline starten", "en": "Start pipeline"},
    "import.partial_files": {"de": "Dateien für Teilimport", "en": "Files for partial import"},
    "import.llm_required": {"de": "Bitte zuerst ein LLM-Modell konfigurieren.", "en": "Please configure an LLM model first."},
    "import.partial_required": {"de": "Bitte wählen Sie mindestens eine Prozessdatei für den Teilimport aus.", "en": "Select at least one process file for partial import."},
    "import.success": {"de": "Importlauf abgeschlossen in {duration}. Ergebnisse liegen im Ausgabe-Ordner.", "en": "Import completed in {duration}. Results are in the output folder."},
    "import.input_path": {"de": "Aktueller Eingabepfad: `{path}`", "en": "Current input path: `{path}`"},
    "import.no_process_files": {"de": "Noch keine Prozessdateien im Eingabepfad vorhanden.", "en": "No process files are available in the input path yet."},
    "import.bpmn_transform": {"de": "BPMN-Transformation", "en": "BPMN transformation"},
    "import.bpmn_intro": {"de": "Optional: Reduziert große BPMN/XML-Dateien vor dem eigentlichen Import auf kompakte Prozessdateien.", "en": "Optional: reduces large BPMN/XML files to compact process files before import."},
    "import.bpmn_files": {"de": "BPMN für Transformation", "en": "BPMN for transformation"},
    "import.transform": {"de": "BPMN transformieren", "en": "Transform BPMN"},
    "import.no_bpmn_files": {"de": "Keine BPMN/XML-Dateien im aktuellen Eingabepfad gefunden.", "en": "No BPMN/XML files found in the current input path."},
    "import.select_bpmn": {"de": "Bitte wählen Sie mindestens eine BPMN/XML-Datei für die Transformation aus.", "en": "Select at least one BPMN/XML file for transformation."},
    "import.transform_success": {"de": "{count} transformed file(s) created. The new files are in `{path}`.", "en": "{count} transformed file(s) created. The new files are in `{path}`."},
    "import.cmdb_sync": {"de": "CMDB-Synchronisation", "en": "CMDB synchronization"},
    "import.cmdb_intro": {"de": "Weisen Sie jeder CMDB-Objektart eine CSV-Datei aus dem Eingabepfad zu und übertragen Sie die Daten nach Neo4j.", "en": "Assign a CSV file from the input path to each CMDB object type and transfer the data to Neo4j."},
    "import.no_cmdb_files": {"de": "Noch keine CMDB-Dateien im Eingabepfad vorhanden.", "en": "No CMDB files are available in the input path yet."},
    "import.none": {"de": "(keine)", "en": "(none)"},
    "import.applications": {"de": "Anwendungen", "en": "Applications"},
    "import.servers": {"de": "Server", "en": "Servers"},
    "import.interfaces": {"de": "Schnittstellen", "en": "Interfaces"},
    "import.apply_type_files": {"de": "Typ-Dateien übernehmen", "en": "Apply type files"},
    "import.type_files_saved": {"de": "CMDB-Typ-Dateien gespeichert: {label}.", "en": "CMDB type files saved: {label}."},
    "import.sync_cmdb": {"de": "CMDB nach Neo4j synchronisieren", "en": "Synchronize CMDB with Neo4j"},
    "import.cmdb_sync_error": {"de": "CMDB konnte nicht nach Neo4j synchronisiert werden: {error}", "en": "CMDB could not be synchronized with Neo4j: {error}"},
    "import.cmdb_sync_success": {"de": "CMDB synchronisiert: {entities} Eintrag/Einträge, {relations} Relation(en), {owners} Eigentümer-Zuordnung(en), {documents} Dokument(e) im letzten Lauf neu bewertet.", "en": "CMDB synchronized: {entities} record(s), {relations} relationship(s), {owners} owner assignment(s), {documents} document(s) from the last run reassessed."},
    "import.cmdb_structure_error": {"de": "CMDB-Strukturfehler in `{file_name}` ({type_label}):", "en": "CMDB structure error in `{file_name}` ({type_label}):"},
    "import.message": {"de": "Meldung", "en": "Message"},
    "import.line_message": {"de": "Zeile {line} {message}", "en": "Line {line}: {message}"},
    "runtime.neo4j_password_missing": {"de": "Neo4j-Verbindung nicht pruefbar: Passwort fehlt.", "en": "Neo4j connection cannot be checked: password is missing."},
    "runtime.neo4j_unavailable": {"de": "Neo4j nicht erreichbar: {error}", "en": "Neo4j is not reachable: {error}"},
    "runtime.neo4j_available": {"de": "Neo4j erreichbar ({url}, DB: {database}).", "en": "Neo4j is reachable ({url}, database: {database})."},
    "runtime.llm_url_missing": {"de": "LLM nicht prüfbar: Base URL fehlt.", "en": "LLM cannot be checked: base URL is missing."},
    "runtime.llm_model_missing": {"de": "LLM-Endpoint erreichbar noch nicht geprueft: Modellname fehlt.", "en": "LLM endpoint has not been checked yet: model name is missing."},
    "runtime.llm_unavailable": {"de": "LLM nicht erreichbar: {error}", "en": "LLM is not reachable: {error}"},
    "runtime.llm_available": {"de": "LLM erreichbar. Modell `{model}` ist verfuegbar; der erste Aufruf kann bei Ollama trotzdem Ladezeit haben.", "en": "LLM is reachable. Model `{model}` is available; the first Ollama request may still need time to load."},
    "runtime.llm_model_unavailable": {"de": "LLM-Endpoint erreichbar, aber Modell `{model}` ist nicht verfuegbar.{available_note}", "en": "LLM endpoint is reachable, but model `{model}` is not available.{available_note}"},
    "runtime.available_models": {"de": " Verfuegbar: {models}.", "en": " Available: {models}."},
    "runtime.import_progress": {"de": "{completed} von {total} Dateien bearbeitet. Aktuell/zuletzt: `{source}` ({status}).", "en": "{completed} of {total} files processed. Current/latest: `{source}` ({status})."},
    "runtime.import_starting": {"de": "Lauf gestartet. Die Anzahl der zu bearbeitenden Dateien wird ermittelt.", "en": "Run started. Determining the number of files to process."},
    "runtime.document_status.unknown": {"de": "unbekannt", "en": "unknown"},
    "runtime.document_status.processed": {"de": "verarbeitet", "en": "processed"},
    "runtime.document_status.no_matches": {"de": "keine Zuordnung", "en": "no matches"},
    "snapshot.schema_version_mismatch": {"de": "Snapshot verwendet Graph-Schema-Version {actual}; BRIDGR benötigt Version {required}.", "en": "Snapshot uses graph schema version {actual}; BRIDGR requires version {required}."},
})


def normalize_locale(value: str | None) -> str:
    return value if value in SUPPORTED_LOCALES else DEFAULT_LOCALE


def translate(key: str, locale: str | None = None, **values: object) -> str:
    selected = normalize_locale(locale)
    message = _MESSAGES.get(key, {}).get(selected, key)
    return message.format(**values)


def translate_source(text: str, locale: str | None = None) -> str:
    """Translate an explicitly catalogued UI source string.

    Arbitrary text must remain untouched: it can be user input, a business-object
    name, or an LLM answer in a language that differs from the UI locale.
    """
    selected = normalize_locale(locale)
    key = _SOURCE_TEXT_KEYS.get(text)
    if key:
        return translate(key, selected)
    if selected == "en" and text in _SOURCE_TRANSLATIONS:
        return _SOURCE_TRANSLATIONS[text]
    return text


def translate_snapshot_error(error: str, locale: str | None = None) -> str:
    """Localize known snapshot-validation errors without changing service APIs."""
    prefix = "Snapshot uses graph schema version "
    suffix = "; BRIDGR requires version "
    if error.startswith(prefix) and suffix in error:
        actual, required = error[len(prefix):].split(suffix, maxsplit=1)
        return translate(
            "snapshot.schema_version_mismatch",
            locale,
            actual=actual,
            required=required.rstrip("."),
        )
    return translate_source(error, locale)


def install_streamlit_localization() -> None:
    """Apply central catalogue lookups to Streamlit labels and short messages.

    This keeps existing tab code readable while ensuring all standard Streamlit
    controls, including controls rendered from columns and expanders, resolve
    their visible text through the same catalogue.
    """
    import streamlit as st
    from streamlit.delta_generator import DeltaGenerator

    if getattr(DeltaGenerator, "_bridgr_i18n_installed", False):
        return

    def localize(value: object) -> object:
        if not isinstance(value, str) or "<" in value:
            return value
        try:
            locale = st.session_state.get("bridgr_locale", DEFAULT_LOCALE)
        except Exception:
            locale = DEFAULT_LOCALE
        if value.startswith("**") and value.endswith("**"):
            return f"**{translate_source(value[2:-2], locale)}**"
        if value.startswith("#") and " " in value:
            prefix, text = value.split(" ", maxsplit=1)
            return f"{prefix} {translate_source(text, locale)}"
        return translate_source(value, locale)

    methods = (
        "button", "caption", "checkbox", "error", "expander", "file_uploader", "form_submit_button",
        "info", "markdown", "metric", "multiselect", "number_input", "popover", "radio", "selectbox",
        "success", "text_input", "warning", "write",
    )
    for name in methods:
        original = getattr(DeltaGenerator, name)

        @wraps(original)
        def localized_method(self, *args, __original=original, **kwargs):
            if args:
                args = (localize(args[0]), *args[1:])
            elif "label" in kwargs:
                kwargs["label"] = localize(kwargs["label"])
            return __original(self, *args, **kwargs)

        setattr(DeltaGenerator, name, localized_method)
    DeltaGenerator._bridgr_i18n_installed = True

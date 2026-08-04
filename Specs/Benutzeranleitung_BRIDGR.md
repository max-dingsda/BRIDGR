# Benutzeranleitung BRIDGR

## 1. Zweck der Anwendung

BRIDGR verbindet Prozessdokumente mit Daten aus einer CMDB und baut daraus einen Wissensgraphen auf. Ziel ist es, fachliche Prozesse, Anwendungen, Schnittstellen, Server und organisatorische Zuständigkeiten gemeinsam sichtbar zu machen.

Für Benutzer bedeutet das:

- Prozessdokumente können eingelesen und ausgewertet werden.
- CMDB-Daten können mit den Prozessen verknüpft werden.
- unklare Zuordnungen können manuell geprüft und entschieden werden.
- vorhandene Informationen können anschließend per natürlicher Sprache abgefragt werden.

Die Leitfrage der Anwendung lautet:

> Welche IT-Bausteine unterstützen welche Geschäftsprozesse, und wie sicher wissen wir das?

---

## 2. Für wen ist BRIDGR gedacht?

Diese Anleitung richtet sich an Benutzer ohne Entwicklungswissen und ohne Vorwissen zu BRIDGR.

Sie ist besonders geeignet für:

- Enterprise-Architecture-Teams
- Fachbereiche mit Prozessverantwortung
- IT-Architektur, IT-Betrieb oder CMDB-verantwortliche Personen
- Anwender, die Importläufe prüfen und offene Zuordnungen freigeben sollen

---

## 3. Voraussetzungen

Vor der ersten Nutzung sollten folgende Voraussetzungen erfüllt sein:

- BRIDGR ist lokal installiert und startbar.
- die benötigten Python-Pakete aus `requirements.txt` beziehungsweise für eine vollständige lokale Entwicklungs- und Testumgebung aus `requirements-dev.txt` sind installiert
- Ein Neo4j-System ist erreichbar.
- Ein LLM-Endpunkt mit OpenAI-kompatibler API ist erreichbar.
- Die benötigten Zugangsdaten liegen vor.
- Prozessdateien und CMDB-Dateien sind fachlich vorbereitet.

### 3.1 Benötigte Daten

BRIDGR arbeitet mit folgenden Eingaben:

- Prozessdokumente als `.bpmn`, `.txt`, `.docx` oder `.pdf`
- optional große BPMN/XML-Dateien zur Vortransformation
- CMDB-Dateien als `.csv`, je eine Datei pro Objektart (Anwendungen, Server, Schnittstellen)
- optional ArchiMate-Datei als `.xml` oder `.archimate`

### 3.2 Benötigte technische Angaben

Vor dem Setup sollten Sie diese Informationen bereithalten:

- URL des LLM-Endpunkts
- Modellname des LLM
- Name der Umgebungsvariable für den API-Schlüssel
- Neo4j-URL
- Neo4j-Benutzer
- Neo4j-Passwort
- Neo4j-Datenbankname

### 3.3 Wichtige Ordner

- `Input/`: Eingangsordner für neue Prozess- und CMDB-Dateien
- `Output/`: Ausgabedaten und Laufartefakte
- `data/input_archive/`: Archiv bereits verarbeiteter Prozessdateien

Wichtig:

- `Input/` ist eine Inbox, kein Dauerarchiv.
- Nach erfolgreichem Import werden verarbeitete Prozessdateien aus `Input/` entfernt und archiviert.

---

## 4. Initiales Setup

### 4.1 Anwendung starten

BRIDGR wird lokal als Streamlit-Anwendung gestartet.

Typischer Start:

```powershell
streamlit run app.py
```

Danach öffnet sich die Oberfläche im Browser.

Im App-Header oben rechts befindet sich ein optionaler Darkmode-Umschalter. Die Wahl gilt nur für die laufende Sitzung und wird bei einem Neustart der Anwendung zurückgesetzt.

Daneben befindet sich ein Rollen-Dropdown (`Benutzer`, `Experte`, `Architekt`, `Konfigurator`). Es blendet je nach gewählter Rolle nur die dafür relevanten Tabs ein und dient ausschließlich der Übersichtlichkeit — es ist keine Zugriffskontrolle, jede Rolle ist jederzeit frei wählbar. Wie beim Darkmode-Umschalter gilt die Wahl nur für die laufende Sitzung.

- `Benutzer` (Standard beim Start): nur `Kommunikation`
- `Experte`: `Kommunikation`, `Import`, `Zuordnungen`, `Organisation`
- `Architekt`: wie `Experte`, zusätzlich `EA-Modell`
- `Konfigurator`: `Kommunikation`, `Konfiguration`

Wenn Sie in dieser Anleitung Schritte in einem Tab vermissen, prüfen Sie zuerst, ob die aktuell gewählte Rolle diesen Tab überhaupt anzeigt.

Falls BRIDGR lokal noch nicht lauffähig ist, müssen vorher die Abhängigkeiten installiert werden, zum Beispiel:

```powershell
python -m pip install -r requirements.txt
```

Für eine vollständige lokale Entwicklungs- und Testumgebung:

```powershell
python -m pip install -r requirements-dev.txt
```

### 4.2 Grundkonfiguration in BRIDGR

Öffnen Sie den Tab `Konfiguration` (ganz rechts) und pflegen Sie dort die technischen Einstellungen.

Empfohlene Reihenfolge:

1. LLM konfigurieren
2. Neo4j konfigurieren
3. Eingabe- und Ausgabepfade prüfen
4. CMDB-Dateien festlegen
5. Verbindungen testen
6. Erst danach den ersten Import durchführen

### 4.3 Dateien vorbereiten

Legen Sie vor dem ersten Import Ihre Dateien in den Eingabeordner:

- Prozessdateien in `Input/`
- CMDB-Dateien (Anwendungen, Server, Schnittstellen) ebenfalls in `Input/`

Wenn sehr große BPMN/XML-Dateien verwendet werden, empfiehlt es sich, diese vor dem eigentlichen Import über die BPMN-Transformation zu reduzieren.

---

## 5. Empfohlener Arbeitsablauf

Auch wenn die Tabs in anderer Reihenfolge angezeigt werden, ist der typische Ablauf:

1. `Konfiguration`: technische Einstellungen prüfen
2. `Import`: Prozessdateien importieren und CMDB synchronisieren
3. `Zuordnungen`: offene Anwendungszuordnungen prüfen
4. `Organisation`: Organisationskandidaten, Prozesseigentümer und Rollen klären
5. `Zuordnungen > Datenpflege`: letzte manuelle Änderungen bei Bedarf zurücknehmen und Prozess-Dubletten konsolidieren; Dubletten von Organisationseinheiten konsolidieren Sie im Tab `Organisation`
6. `EA-Modell`: optional ArchiMate-Mapping pflegen sowie ArchiMate importieren/exportieren
7. `Kommunikation`: Fragen an den aufgebauten Wissensgraphen stellen

---

## 6. Tab `Kommunikation`

### 6.1 Zweck

In diesem Tab stellen Sie Fragen in natürlicher Sprache zum vorhandenen Wissensgraphen.

Beispiele:

- Welche Anwendungen unterstützen Prozess X?
- Welche Server hängen an Anwendung Y?
- Welche Organisationseinheit verantwortet Anwendung Z?
- Welche Anwendungen könnten für Prozess X relevant sein (noch nicht bestätigt)?

Hinweis zu Kandidaten: BRIDGR unterscheidet zwischen bestätigten Anwendungslinks und schwachen
Kandidaten (noch nicht im Review-Tab entschieden). Wenn Sie nach möglichen oder unbestätigten
Zuordnungen fragen, kennzeichnet BRIDGR die Antwort ausdrücklich als „möglicher Kandidat" oder
„nicht bestätigt". Bestätigte Informationen werden ohne diesen Hinweis ausgegeben.

### 6.2 Bereich und Elemente

#### `Neues Gespräch`

Setzt die aktuelle Gesprächshistorie zurück und startet einen neuen Chatkontext.

#### Chat-Eingabe `Frage an den Wissensgraphen`

Hier geben Sie Ihre Frage in normaler Sprache ein.

#### Chat-Antworten

Unmittelbar nach dem Absenden einer Frage erscheinen Ihre Eingabe und ein Verarbeitungs-Spinner direkt im Gesprächsverlauf — so ist jederzeit erkennbar, dass BRIDGR die Anfrage verarbeitet. Die Antwort des Systems folgt sobald die Verarbeitung abgeschlossen ist.

Mögliche zusätzliche Inhalte:

- tabellarische Ergebnisse
- technischer Cypher-Query unter `Technische Details`
- CSV-Export eines Ergebnisses

#### Button `Als CSV exportieren`

Erscheint bei tabellarischen Treffern und exportiert das sichtbare Ergebnis als CSV-Datei.

### 6.3 Wichtige Hinweise

- Ohne konfiguriertes LLM kann der Chat nicht verwendet werden.
- Ohne Neo4j-Zugangsdaten kann der Chat keine Graphabfragen ausführen.
- Wenn keine Treffer gefunden werden, heißt das nicht automatisch, dass keine Daten existieren; es kann auch an uneinheitlichen Bezeichnungen liegen.

---

## 7. Tab `Import`

Hier starten Sie den Prozessimport nach Neo4j und die CMDB-Synchronisation.

### Feld `Importmodus`

Werte:

- `full`: verarbeitet alle Prozessdateien im Eingabepfad
- `partial`: verarbeitet nur die explizit ausgewählten Dateien

### Feld `Dateien für Teilimport`

Erscheint nur im Modus `partial`. Hier wählen Sie die Prozessdateien aus, die importiert werden sollen.

### Feld `BPMN für Transformation`

Auswahl großer BPMN/XML-Dateien, die vor dem eigentlichen Import reduziert werden sollen.

### Button `BPMN transformieren`

Erzeugt aus den gewählten BPMN/XML-Dateien kompaktere Transform-Dateien. Das ist hilfreich bei sehr großen oder komplexen BPMN-Modellen.

### Button `Pipeline starten`

Startet den eigentlichen Prozessimport nach Neo4j.

Dabei werden Prozessdateien analysiert, mit der CMDB abgeglichen und Ergebnisse als Laufartefakte gespeichert.
Vor der ersten Änderung erstellt BRIDGR automatisch einen validierten Snapshot des gesamten
Wissensgraphen. Falls das nicht gelingt, wird der Import nicht gestartet.

### Tabelle `Aktueller Eingabepfad`

Zeigt die aktuell gefundenen Prozessdateien im Eingabepfad.

### Felder `Anwendungen`, `Server`, `Schnittstellen`

Weisen jeder CMDB-Objektart eine CSV-Datei aus dem Eingabeordner zu. Beziehungen (z. B. welcher Server eine Anwendung hostet) sind als Spalten in der Anwendungsdatei enthalten und werden beim Synchronisieren automatisch eingelesen.

### Button `Typ-Dateien übernehmen`

Speichert die aktuell gewählten Typ-Dateien als aktive Konfiguration.

### Button `CMDB nach Neo4j synchronisieren`

Überträgt die ausgewählten CMDB-Daten nach Neo4j.

Zusätzlich wird der letzte gespeicherte Lauf in `Output/latest_run.json` mit der aktuellen CMDB neu bewertet. Dadurch können offene oder schwache Zuordnungen im Tab `Zuordnungen` automatisch verschwinden, wenn die aktualisierte CMDB jetzt einen starken Treffer liefert.
Auch vor dieser Synchronisation erstellt BRIDGR automatisch einen validierten Graph-Snapshot.

### Tabellen zu `CMDB-...Strukturfehler`

Zeigen Probleme in der CSV-Struktur an, zum Beispiel fehlende Spalten oder unvollständige Zeilen.

---

## 8. Tab `Zuordnungen`

### 8.1 Zweck

Hier prüfen Sie offene oder unsichere Anwendungszuordnungen aus dem letzten Importlauf. Es wird in diesem Tab kein neuer Import gestartet.

### 8.2 Abschnitt `Umfang`

#### Radio-Option `Nur letzter Import`

Zeigt nur Dateien aus dem zuletzt importierten Lauf an.

#### Radio-Option `Dateien manuell wählen`

Erlaubt die gezielte Auswahl einzelner Dateien aus bereits vorhandenen Laufartefakten.

Wichtige Konsequenz:

Wenn Sie hier zum Beispiel nur 1 von 10 Dateien auswählen, bezieht sich die Anzeige in diesem Tab nur noch auf diese ausgewählte Datei beziehungsweise Dateimenge. Sie blenden damit die übrigen Dateien nur aus; deren Review-Fälle werden dadurch weder gelöscht noch automatisch entschieden. Offene Zuordnungen der nicht ausgewählten Dateien bleiben also weiterhin bestehen und müssen später separat geprüft werden.

#### Feld `Dateien für Überprüfung`

Multiselect für die manuelle Auswahl der Prozessdateien, die geprüft werden sollen.

### 8.3 Feld `Statusfilter`

Filtert die angezeigten Dokumente nach Status. So können Sie sich zum Beispiel nur problematische oder offene Fälle anzeigen lassen.

### 8.4 Bereich `Dokumentstatus`

Tabellarische Übersicht über die Dokumente im aktuellen Filter.

Typische Informationen:

- Dateistatus
- erkannte Prozesse
- Fehlerfälle

### 8.5 Bereich `Offene Zuordnungen`

#### Sortierung

Über den Sortierungsschalter oberhalb der Tabelle können Sie die Einträge wahlweise **nach Prozess** (Standard) oder **nach Anwendungsbezeichner** sortieren. Die Sortierung nach Anwendungsbezeichner erleichtert das Erkennen von Fällen, bei denen derselbe Begriff in mehreren Prozessen auftaucht und auf dieselbe CMDB-Anwendung verweist.

Hier sehen Sie pro Review-Fall:

- Checkbox (für Mehrfachauswahl)
- `Prozess`
- `Anwendung im Prozess`
- `Anwendung in der CMDB`
- `Bewertung`

Zu jedem Fall gibt es folgende Aktionen:

#### Button `Bestätigen`

Übernimmt die vorgeschlagene Zuordnung als korrekt.

**Batch-Bestätigung:** Wenn Sie mehrere Zeilen per Checkbox markieren und alle markierten Einträge denselben Anwendungsbezeichner (normalisiert) und dasselbe CMDB-Ziel haben, bestätigt ein Klick auf `Bestätigen` in einer der markierten Zeilen alle markierten Einträge auf einmal. Zeilen ohne Markierung sind davon nicht betroffen.

Bei ungültiger Mehrfachauswahl (unterschiedliche Bezeichner oder unterschiedliche CMDB-Ziele) werden alle Aktionsbuttons der markierten Zeilen deaktiviert und ein rotes Banner erklärt den Grund. Nicht markierte Zeilen bleiben weiterhin einzeln bedienbar.

#### Button `Ablehnen`

Lehnt die vorgeschlagene Zuordnung ab.

#### Popover `Manuell anlegen`

Öffnet eine manuelle Auswahl mit alphabetisch sortierter CMDB-Liste.

Darin enthalten:

- Feld `CMDB-Ziel`: alphabetisch sortierte Auswahl eines CMDB-Eintrags
- Button `Speichern`: speichert die manuell gewählte Zuordnung

### 8.6 Bereich `Dokumentdetails`

Zeigt pro Dokument technische und fachliche Details.

Enthalten sein können:

- Prozessname
- Prozess-ID
- erkannte Organisationseinheit
- Vorgängerprozess
- Dateihash
- Review-Items

#### Expander `Technische Details`

Zeigt Rohdaten aus der Extraktion:

- Rohanwendungen
- Anwendungen
- Zuordnungen

### 8.7 Wann Sie diesen Tab nutzen sollten

Nutzen Sie diesen Tab immer nach einem Import, wenn BRIDGR nicht sicher genug war, eine Anwendungszuordnung automatisch freizugeben.

### 8.8 Bereich `Datenpflege`

Am Ende des Tabs bündelt der Bereich `Datenpflege` zwei tabübergreifende Pflegefunktionen:
die Konsolidierung von Prozess-Dubletten und die Rücknahme manueller Änderungen.

### 8.9 Abschnitt `Prozesse konsolidieren`

Dieser Bereich dient zum Zusammenführen fachlicher Prozess-Dubletten.

Typischer Anwendungsfall:

- derselbe Prozess wurde aus unterschiedlichen Quellen mit leicht abweichendem Namen importiert
- ein Prozess liegt einmal als Text-/BPMN-Import und einmal aus einem anderen Modell vor

Felder:

- `Prozess-Quelle`: der aufzulösende Prozess
- `Prozess-Ziel`: der Prozess, der bestehen bleiben soll

Vor dem eigentlichen Merge zeigt BRIDGR auch hier einen Precheck mit Beziehungshinweisen,
Dublettenprüfung und einer kompakten Wirkungszusammenfassung.

#### Button `Prozess-Merge ausführen`

Führt den ausgewählten Quellprozess in den Zielprozess über.

Dabei geschieht:

- Anwendungsbeziehungen, Rollenbeteiligungen, Eigentümerbeziehungen und Prozessfolgekanten werden auf das Ziel übertragen
- bereits vorhandene gleichartige Beziehungen werden nicht doppelt erzeugt
- der Name der Quelle wird als Alias des Zielprozesses weitergeführt

Wichtig:

- Ein Prozess-Merge kann über `Letzte manuelle Änderungen` wieder zurückgenommen werden.

### 8.10 Abschnitt `Letzte manuelle Änderungen`

Hier sehen Sie die zuletzt ausgeführten manuellen Entscheidungen mit fachlichem Kontext.

Typische Inhalte:

- Art der Änderung
- Zeitpunkt
- betroffener Prozess, betroffene Anwendung oder Organisationseinheit
- bei Prozesseigentümern der Prozessname und der zugewiesene Eigentümer

Wichtig:

- Ältere Entscheidungen können noch technische Kennungen enthalten, wenn sie vor der UI-Erweiterung angelegt wurden.
- Neuere Prozesseigentümer-Zuordnungen werden mit einem menschenlesbaren Prozessnamen angezeigt.

#### Button `Zurücknehmen`

Macht eine unterstützte manuelle Entscheidung rückgängig.

Aktuell unterstützt:

- manuell angelegte Anwendungszuordnung
- bestätigter Anwendungskandidat
- manuelle Prozesseigentümer-Zuordnung
- manuelle Rollenzuordnung

Der Rücknahmevorgang erzeugt selbst wieder einen internen Nachweis im System.
Auch Merge-Entscheidungen können in der aktuellen Version über diese Liste zurückgenommen werden.
Rücknahmen gelten dabei fachlich als abgeschlossen und erscheinen nicht mehr als neue aktive manuelle Entscheidung.

---

## 9. Tab `Organisation`

### 9.1 Zweck

Hier verwalten Sie Organisationseinheiten, offene Organisationskandidaten, Prozesseigentümer und Rollenbeziehungen.

### 9.2 Abschnitt `Organisationseinheiten`

Zeigt alle bekannten Organisationseinheiten. Die Liste wird aus Neo4j geladen und enthält daher auch Organisationseinheiten, die durch einen ArchiMate-Import entstanden sind (aus `BusinessActor`-Elementen), ohne dass ein zusätzlicher Schritt notwendig ist.

Manuell in diesem Tab angelegte Organisationseinheiten erscheinen ebenfalls in der Liste, müssen aber über den Synchronisations-Button nach Neo4j übertragen werden, um im Graphen wirksam zu sein.

#### Button `Organisation nach Neo4j synchronisieren`

Schreibt manuell gepflegte Organisationseinheiten nach Neo4j.

Wichtig:

Diesen Schritt müssen Sie immer ausführen, wenn Sie in diesem Tab organisatorische Änderungen vorgenommen haben, die im Graphen wirksam werden sollen. Dazu gehören insbesondere neue Organisationseinheiten, Kandidatenentscheidungen, Prozesseigentümer-Zuordnungen und Rollenzuordnungen. Ohne die Synchronisation sind Änderungen zwar fachlich erfasst, aber noch nicht vollständig in Neo4j wirksam.

#### Button `Prozesse verwalten`

Öffnet für die jeweilige Organisationseinheit eine Bearbeitungsansicht.

Dort enthalten:

- Feld `Verantwortliche Prozesse`: Multiselect aller Prozesse
- Button `Speichern`: speichert die Prozesszuordnung

#### Formular `Neue Organisationseinheit`

Feld:

- `Neue Organisationseinheit`

Button:

- `Organisationseinheit hinzufügen`

### 9.3 Abschnitt `Kandidaten`

Zeigt offene Organisationskandidaten, die aus Dokumenten oder CMDB-Daten entstanden sind.

Zu jedem Kandidaten werden typischerweise angezeigt:

- betroffene Prozesse
- betroffene Rollen
- Quellen

Eingabefelder und Buttons:

- `Bestehende Organisationseinheit`: Auswahl einer vorhandenen OE
- `Zuordnen`: mappt den Kandidaten auf eine bestehende OE
- `Als neue Organisationseinheit übernehmen`: Textfeld für den Zielnamen
- `Übernehmen`: legt eine neue OE an bzw. übernimmt den Kandidaten
- `Abweisen`: verwirft den Kandidaten

### 9.4 Abschnitt `Vorgeschlagene Prozess-Eigentümer`

Zeigt Vorschläge für Prozesseigentümer aus der Extraktion.

Eingabefeld:

- `Organisationseinheit bestätigen`

Buttons:

- `Bestätigen`
- `Abweisen`

Mit `Bestätigen` wird der vorgeschlagene Prozesseigentümer übernommen.

### 9.5 Abschnitt `Prozesse ohne Eigentümer`

Hier sehen Sie Prozesse, denen noch keine Organisationseinheit als Eigentümer zugeordnet wurde.

#### Batch-Zuweisung

Felder:

- `Mehrere Prozesse gleichzeitig zuweisen`
- `Gemeinsamer Eigentümer`

Button:

- `Batch zuweisen`

#### Einzelzuweisung pro Prozess

Feld:

- `Eigentümer zuweisen`

Button:

- `Zuweisen`

### 9.6 Abschnitt `Nicht zugeordnete Rollen`

Zeigt Rollen aus Prozessmodellen, die noch keiner Organisationseinheit zugeordnet sind.

Felder und Buttons:

- `Bestehende Organisationseinheit`
- `Zuordnen`
- `Als neue Organisationseinheit anlegen`
- `Anlegen & zuordnen`
- `Rolle`

Bedeutung von `Rolle`:

Damit markieren Sie, dass ein Begriff bewusst nur eine Prozessrolle ist und keine Organisationseinheit darstellen soll.

### 9.7 Abschnitt `Bereits entschiedene Kandidaten`

Zeigt eine Historie bereits bearbeiteter Organisationskandidaten.

Typische Spalten:

- Kandidat
- Status
- Gemappt auf
- Zuletzt gesehen

### 9.8 Abschnitt `Organisationseinheiten konsolidieren`

Dieser Bereich dient zum Zusammenführen fachlicher Dubletten bei Organisationseinheiten.

Typischer Anwendungsfall:

- dieselbe Einheit wurde aus verschiedenen Quellen mit unterschiedlichen Namen importiert
- eine frühere Fehlzuordnung soll dauerhaft bereinigt werden

Felder:

- `Quelle`: die Organisationseinheit, die aufgelöst werden soll
- `Ziel`: die Organisationseinheit, die bestehen bleiben soll

Vor dem eigentlichen Merge zeigt BRIDGR einen Precheck mit:

- Anzahl eingehender und ausgehender Beziehungen der Quelle
- Hinweis auf bereits vorhandene gleichartige Beziehungen am Ziel
- Alias-Übernahme des Quellnamens
- kompaktem Hinweis, welche Wirkungen der Merge fachlich hat

#### Button `Merge ausführen`

Führt die ausgewählte Quell-Organisationseinheit in die Ziel-Organisationseinheit über.

Dabei geschieht:

- bestehende fachliche Beziehungen werden auf das Ziel umgehängt
- bereits vorhandene gleichartige Beziehungen werden nicht doppelt erzeugt
- der Name der Quelle wird als Alias des Ziels weitergeführt
- die Quell-Organisationseinheit verschwindet anschließend aus der fachlichen Sicht

Wichtig:

- Diese Funktion gilt nur für Organisationseinheiten. Prozess-Dubletten konsolidieren Sie im Tab `Zuordnungen` im Bereich `Datenpflege`.

---

## 10. Tab `EA-Modell`

### 10.1 Zweck

Dieser Tab ist für ArchiMate-bezogene Funktionen zuständig:

- Mapping zwischen BRIDGR und ArchiMate pflegen
- ArchiMate-Dateien importieren
- vollständigen BRIDGR-Graphen als ArchiMate exportieren

### 10.2 Abschnitt `Mapping konfigurieren`

#### Expander `Elemente`

Für jedes BRIDGR-Label gibt es zwei Auswahlfelder:

- `Import: ArchiMate-Typ`
- `Export: ArchiMate-Typ`

Damit legen Sie fest:

- welcher ArchiMate-Typ beim Import welchem BRIDGR-Label zugeordnet wird
- welcher ArchiMate-Typ beim Export für dieses BRIDGR-Label erzeugt wird

#### Checkbox `Beziehungs-Mapping bearbeiten`

Blendet die Bearbeitung der Beziehungs-Mappings ein.

#### Expander `Beziehungen`

Pro Label-Paar stehen zur Verfügung:

- `Import: akzeptierte AM-Typen`
- `Export: AM-Typ`
- `BRIDGR-Relation` — legt fest, welcher Kantentyp in Neo4j geschrieben wird

Wichtig: Alle drei Felder müssen konsistent gepflegt sein. Fehlt die BRIDGR-Relation für ein Label-Paar, werden Beziehungen dieses Typs beim Import still übersprungen, auch wenn der ArchiMate-Typ in der Import-Liste steht.

#### Button `Mapping speichern`

Speichert das ArchiMate-Mapping dauerhaft.

### 10.3 Abschnitt `Offene Zuordnungen`

Erscheint nur, wenn es unklare ArchiMate-Kandidaten gibt.

Buttons pro Kandidat:

- `✓`: Kandidat bestätigen
- `✗`: Kandidat verwerfen

### 10.4 Abschnitt `Import`

#### Feld `ArchiMate-Datei hochladen (.xml oder .archimate)`

Dateiupload für eine ArchiMate-Datei.

#### Button `Importieren`

Startet den ArchiMate-Import.

Nach erfolgreichem Import zeigt BRIDGR unter anderem an:

- importierte Elemente
- erzeugte Kandidaten
- übersprungene Elemente
- importierte Beziehungen
- übersprungene Beziehungen

### 10.5 Abschnitt `Export`

#### Button `Als ArchiMate exportieren`

Exportiert den vollständigen BRIDGR-Graphen als ArchiMate-Datei.

Wichtig:

- Der Export umfasst immer den gesamten Graphen.
- Teilexporte sind in der aktuellen Version nicht vorgesehen.

---

## 11. Tab `Konfiguration`

Dieser Tab bündelt alle technischen Einstellungen. Der Prozessimport selbst wird im Tab `Import` gestartet.

### Abschnitt `Pfade auswählen`

Buttons:

- `Eingabe-Ordner wählen`
- `Ausgabe-Ordner wählen`

Diese Buttons öffnen Dateiauswahl- oder Ordnerdialoge.

### Abschnitt `LLM`

Zusätzliche Hilfe:

- Über die Preset-Buttons `OpenAI` und `Ollama` können typische Standardwerte direkt vorbelegt werden.
- Das Feld `API-Schlüssel (Umgebungsvariable)` erwartet den Namen der Umgebungsvariable mit dem Schlüssel, nicht den geheimen Schlüsselwert selbst. Für OpenAI ist typischerweise `OPENAI_API_KEY` gemeint.

Felder:

- `LLM-Endpunkt`: URL des OpenAI-kompatiblen LLM-Dienstes
- `LLM-Modell`: Name des verwendeten Modells
- `API-Schlüssel (Umgebungsvariable)`: Name der Umgebungsvariable mit dem API-Key
- `Kontextfenster`: Anzahl von Kontextnachrichten für den Chat
- `LLM-Timeout (Sekunden)`: maximale Wartezeit auf LLM-Antworten
- `Chat-Modus`: Auswahl zwischen `prompt-only` und `tool-use`

Hinweis zu `Chat-Modus`:

- `prompt-only` ist der kompatiblere Fallback für einfache oder lokale Modelle.
- `tool-use` nutzt formales Function Calling und setzt Backend-Unterstützung voraus.

### Abschnitt `Neo4j`

Felder:

- `Neo4j-URL`
- `Neo4j-Benutzer`
- `Neo4j-Passwort`
- `Neo4j-Datenbank`

Diese Felder steuern die Verbindung zur Graphdatenbank.

### Abschnitt `Datei-Pfade`

Felder:

- `Eingabepfad`
- `Ausgabepfad`

#### Abschnitt `CMDB-Spaltenmapping — Beziehungsspalten (Typ-Datei-Format)`

Konfiguriert, welche Spalten in der Anwendungsdatei die Beziehungen zu Servern und Schnittstellen enthalten:

- `Spalte 'läuft auf'` — Spaltennamen für Server-IDs (Standard: `runs_on`)
- `Spalte 'nutzt Schnittstellen'` — Spaltennamen für Schnittstellen-IDs (Standard: `uses_interfaces`)
- `Mehrwert-Trennzeichen` — Trennzeichen bei mehreren Ziel-IDs in einer Zelle (Standard: `|`)

### Abschnitt `CMDB-Spaltenmapping — Entities`

Felder:

- `ID-Spalte`
- `Namensspalte`
- `Typ-Spalte`
- `Servertyp-Spalte`
- `Eigentümer-Spalte`

Diese Felder müssen zu den Spaltennamen Ihrer CMDB-CSV-Dateien passen.

Hinweis zum Dateiformat: BRIDGR erkennt das Trennzeichen der CSV-Dateien automatisch. Sowohl Komma (`,`) als auch Semikolon (`;`) werden unterstützt.

#### Abschnitt `CMDB-Spaltenmapping — Relationen (Legacy-Format)`

Gilt nur, wenn noch das ältere Zwei-Dateien-Format verwendet wird.

Felder:

- `Quell-ID-Spalte`
- `Relationstyp-Spalte`
- `Ziel-ID-Spalte`

#### Abschnitt `Import & Matching`

Felder:

- `Fuzzy-Schwellenwert`: bestimmt, wie tolerant BRIDGR bei unscharfen Namensähnlichkeiten ist
- `Standard-Importmodus`: Vorgabewert für `full` oder `partial`
- `Debug-Modus`: schreibt zusätzliche Diagnosedaten

#### Abschnitt `Sicherung und Wiederherstellung`

- `Aufbewahrung Snapshots`: Anzahl der gültigen Graph-Snapshots, die BRIDGR behält
  (Standard: `10`). Ein Snapshot wird vor Prozessimport, CMDB-Synchronisation und Merge
  automatisch erstellt.
- Die Tabelle zeigt Zeitpunkt, Auslöser, Operation sowie Anzahl der gesicherten Knoten und
  Beziehungen. Ungültige Snapshots können nicht wiederhergestellt werden.
- Für eine Wiederherstellung wählen Sie einen gültigen Snapshot, bestätigen die vollständige
  Wiederherstellung des BRIDGR-Graphen und klicken `Snapshot wiederherstellen`.

Vor der Wiederherstellung erstellt BRIDGR zusätzlich einen Pre-Restore-Snapshot. Dadurch kann
auch eine versehentlich gewählte Wiederherstellung wieder zurückgenommen werden.
Die Wiederherstellung ersetzt den gesamten Inhalt der konfigurierten Neo4j-Datenbank;
verwenden Sie dafür ausschließlich eine dedizierte BRIDGR-Datenbank und tragen Sie deren
Namen im Feld `Neo4j-Datenbank` ein.

#### Button `Konfiguration speichern`

Speichert alle Änderungen in der Konfiguration.

#### Button `Neo4j-Verbindung neu prüfen`

Prüft, ob die Graphdatenbank mit den aktuellen Angaben erreichbar ist.

#### Button `Modelle aktualisieren`

Fragt die am LLM-Endpunkt verfügbaren Modelle ab.

#### Button `LLM-Verbindung neu prüfen`

Prüft die Verbindung zum LLM und die Modellverfügbarkeit.

#### Bereich `Aktuelle Konfiguration`

Zeigt die derzeit wirksame Konfiguration als JSON an.

---

## 12. Typische Nutzungsszenarien

### 12.1 Erster Import

1. Im Tab `Konfiguration` LLM und Neo4j einrichten
2. Prozessdateien und CMDB-Dateien (Anwendungen, Server, Schnittstellen) in `Input/` ablegen
3. Im Tab `Import` die CMDB-Typ-Dateien den Objektarten zuweisen und mit `Typ-Dateien übernehmen` speichern
4. Falls nötig `CMDB nach Neo4j synchronisieren`
5. `Pipeline starten`
6. Danach `Zuordnungen` und `Organisation` prüfen

Hinweis:
Wenn Sie eine CMDB nachträglich erweitern oder korrigieren, kann Schritt 4 bereits ausreichen, um bestehende offene Zuordnungen aus dem letzten Lauf neu bewerten zu lassen. Ein erneuter Prozessimport ist dafür nicht zwingend erforderlich.

### 12.2 Offene Zuordnungen bereinigen

1. Tab `Zuordnungen` öffnen
2. Umfang und Statusfilter setzen
3. offene Fälle bestätigen, ablehnen oder manuell anlegen
4. anschließend Tab `Organisation` öffnen und offene Organisationsfragen klären
5. bei Bedarf im Bereich `Datenpflege` des Tabs `Zuordnungen` letzte manuelle Änderungen prüfen oder Prozesse konsolidieren; Organisationseinheiten konsolidieren Sie im Tab `Organisation`

### 12.3 Fragen an den Graph stellen

1. Sicherstellen, dass bereits Daten importiert wurden
2. Tab `Kommunikation` öffnen
3. Frage natürlichsprachlich eingeben
4. Ergebnisse bei Bedarf als CSV exportieren

---

## 13. Häufige Probleme

### Keine Chat-Antwort möglich

Mögliche Ursachen:

- kein LLM-Modell konfiguriert
- Neo4j-Zugangsdaten fehlen
- Verbindungen sind nicht erreichbar

### Kein sinnvoller Import

Mögliche Ursachen:

- Dateien liegen nicht im richtigen Eingabepfad
- CMDB-Spaltenmapping passt nicht zur CSV
- LLM ist nicht erreichbar
- BPMN-Datei ist sehr groß und sollte zuerst transformiert werden

### Keine oder wenige Treffer im Review

Mögliche Ursachen:

- es gab bereits starke automatische Zuordnungen
- die Prozessdatei wurde nicht erfolgreich verarbeitet
- Statusfilter oder Dateifilter schränken die Ansicht ein

---

## 14. Kurzfassung für neue Benutzer

Wenn Sie BRIDGR zum ersten Mal verwenden, reicht meist dieser Ablauf:

1. `Konfiguration` öffnen
2. LLM und Neo4j eintragen
3. Dateien in `Input/` legen
4. im Tab `Import` die Pipeline starten
5. offene Fälle in `Zuordnungen` prüfen
6. Zuständigkeiten in `Organisation` klären
7. im Tab `Kommunikation` Fragen an den Graphen stellen

Damit können Sie BRIDGR ohne Entwicklungskenntnisse produktiv nutzen.

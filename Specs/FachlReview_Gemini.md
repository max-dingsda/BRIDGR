# Fachliches Review — BRIDGR aus Sicht eines unbedarften Nutzers
**Erstellt durch Gemini (Antigravity) | Juni 2026**

---

## 1. Einleitung und Zielsetzung
Dieses Review bewertet die Benutzererfahrung und die funktionale Erfüllung von BRIDGR aus der Perspektive eines **technisch unbedarften Nutzers** (z. B. einer Fachkraft für Geschäftsprozesse, eines Business Analysts oder eines Enterprise Architects ohne Datenbank- und Programmierkenntnisse). 

Als Grundlage dient die [README.md](file:///f:/workspace/BRIDGR/README.md) sowie die darin beschriebene Vision und der aktuelle Implementierungsstand im Quellcode. Zur Inspiration wurden die in [independent_expectations.md](file:///f:/workspace/BRIDGR/Specs/independent_expectations.md) dokumentierten Erwartungen herangezogen.

---

## 2. Erwartungshaltung des Nutzers vs. Realität

Ein fachlicher Nutzer, der die `README.md` liest, erwartet ein Werkzeug, das ihm die mühsame Arbeit des manuellen Mappings von Geschäftsprozessen auf die IT-Landschaft (CMDB) abnimmt und ihm einen einfachen, dialogbasierten Zugriff auf dieses Wissen ermöglicht.

Hier ist die Gegenüberstellung der Erwartungshaltungen mit der tatsächlichen Umsetzung:

### Erwartung 1: "Ich lade ein Dokument hoch, und das System macht den Rest"
* **Erwartung:** Der Nutzer möchte Prozessbeschreibungen (PDF, Word, TXT) oder Diagramme (BPMN) einfach über die Weboberfläche hochladen. Das System extrahiert die Anwendungen und verknüpft sie mit der CMDB.
* **Ist-Zustand:** BRIDGR hat keinen klassischen Datei-Upload in der Streamlit-UI. Der Nutzer muss die Dateien manuell im lokalen Ordner `Input/` ablegen. Für lokale Testläufe ist das okay, im Unternehmensalltag aber eine Hürde.
* **Das Inbox-Prinzip:** Dass verarbeitete Dateien aus `Input/` verschwinden und nach `data/input_archive/` verschoben werden, kann fachliche Nutzer verwirren ("Wo ist meine Datei hin?"). Das erfordert eine klare visuelle Erklärung in der UI.

### Erwartung 2: "Ich kann Fehler einfach im UI korrigieren, und das System merkt sich das"
* **Erwartung:** Automatische Mappings können fehlerhaft sein. Der Nutzer erwartet eine Liste von unsicheren Zuordnungen, die er mit einem Klick bestätigen, ablehnen oder korrigieren kann. Diese Korrekturen müssen dauerhaft gespeichert werden.
* **Ist-Zustand (Zuordnungs-Tab):** Diese Erwartung wird im **Tab 2 (Zuordnungen)** hervorragend erfüllt. Die Oberfläche bietet eine übersichtliche Review-Tabelle mit Aktionen wie `Bestätigen`, `Ablehnen` und einem alphabetisch sortierten Dropdown für `Manuell anlegen`. Auch die Batch-Bestätigung per Checkbox funktioniert gut.
* **Kritischer fachlicher Bug im Hintergrund:** Beim Import-Lauf in der Pipeline werden neu gefundene Organisationseinheiten-Kandidaten zwar im Speicher identifiziert, aber **nicht** in der Datei `knowledge_base/kb.json` persistiert (die Funktion `save_knowledge_base` wird in `pipeline.py` nach dem Update der Kandidaten nicht aufgerufen). Startet der Nutzer die Anwendung neu, sind diese erkannten Kandidaten in der UI (Tab 4) wieder verschwunden! Dies verletzt die Erwartung der Konsistenz schwer.

### Erwartung 3: "Ein Chatbot, der mir wie ein Kollege antwortet und die Technik versteckt"
* **Erwartung:** Der Chatbot im **Tab 1 (Kommunikation)** soll Fragen wie *"Welche Prozesse sind vom Ausfall von Server X betroffen?"* in natürlicher Sprache beantworten. Technische Datenbankabfragen (Cypher) oder rohe Fehlermeldungen sollen unsichtbar bleiben.
* **Ist-Zustand:** Dies ist sehr gut gelöst. Der Chat-Tab zeigt direkt die Antwort an. Technische Cypher-Queries werden standardmäßig in einem eingeklappten Bereich ("Technische Details") versteckt. Tritt ein Fehler auf, wird dieser in eine verständliche deutsche Fehlermeldung übersetzt (z. B. bei fehlender Verbindung zum Graph-Server) statt dem Nutzer rohen Datenbankcode zu zeigen.
* **Ergebnisanzeige:** Die tabellarische Anzeige von Abfrageergebnissen inklusive eines direkten CSV-Downloads ist für Business-Nutzer extrem nützlich.

### Erwartung 4: "Ich kann Duplikate bereinigen (Konsolidierung)"
* **Erwartung:** Da in verschiedenen Dokumenten oft unterschiedliche Bezeichnungen für dieselbe Abteilung oder denselben Prozess verwendet werden (z. B. "Einkauf" vs. "Beschaffung"), erwartet der Nutzer eine einfache Merge-Funktion.
* **Ist-Zustand (Organisation-Tab):** Im **Tab 4 (Organisation)** gibt es dafür die Bereiche `Organisationseinheiten konsolidieren` und `Prozesse konsolidieren`. 
* **Merge-Precheck:** Der Precheck zeigt vor dem Zusammenführen genau an, welche Beziehungen übertragen werden und ob Konflikte bestehen. Das gibt dem Nutzer Sicherheit vor destruktiven Aktionen.
* **Undo-Funktion:** Der Bereich `Letzte manuelle Änderungen` ermöglicht die Rücknahme von Zuordnungen direkt im UI, was fachlichen Nutzern die Angst vor Fehlern nimmt.

---

## 3. Größte Hürden für fachlich unbedarfte Nutzer (UX-Gaps)

### Hürde 1: Die manuelle Transformation großer BPMN-Dateien
* **Das Problem:** Der "BPMN-Transformer" für große Modelle ist ein hochgradig technischer Hilfsschritt.
* **Der Ablauf laut README:** Nutzer muss die BPMN-Datei in `Input/` ablegen, in Tab 3 "BPMN transformieren" klicken. Anschließend muss er manuell den `Input Path` auf `Input/transformed/` umstellen oder die erzeugte TXT-Datei verschieben, um sie importieren zu können.
* **Kritik:** Für einen unbedarften Nutzer ist das unverständlich. Er erwartet, dass BRIDGR große BPMN-Dateien im Hintergrund automatisch erkennt, reduziert und verarbeitet, ohne dass er Pfade in der Konfiguration ändern oder Dateien verschieben muss.

### Hürde 2: Die CMDB-Konfiguration und Spaltenzuordnung
* **Das Problem:** Im **Tab 3 (Konfiguration)** muss der Nutzer technische CSV-Parameter festlegen.
* **Die Felder:** Spaltennamen wie `cmdb_uuid_column`, `cmdb_runs_on_column`, `cmdb_uses_interfaces_column` und das Trennzeichen `|` (`cmdb_multivalue_separator`) setzen tiefes Verständnis der CMDB-Exportstruktur voraus. 
* **Kritik:** Hier fehlen Tooltips oder Standard-Presets für bekannte Systeme (z. B. ServiceNow oder Jira Assets), um den Nutzer nicht mit Variablen zu überfordern.

### Hürde 3: Technische Modell-Empfehlungen in der README
* **Das Problem:** Der Abschnitt "LLM-Modell-Empfehlungen" in der `README.md` richtet sich primär an Entwickler oder Systemadministratoren (Diskussion über 8B vs. 14B/26B Modelle, RTX-GPUs, VRAM und Quantisierungen).
* **Kritik:** Ein rein fachlicher Anwender kann mit diesen Angaben wenig anfangen. Hier wäre eine klare Trennung zwischen einer "Anwenderdokumentation" und einer "Installations-/Admin-Anleitung" ratsam.

---

## 4. Fazit und Empfehlungen zur Verbesserung der Fachlichkeit

BRIDGR erfüllt die fachlichen Erwartungen bereits zu einem großen Teil (insbesondere durch die sehr gute Dialogführung im Chat und die geführte Merge- und Review-Logik). Um das Tool jedoch für technisch unbedarfte Nutzer vollständig nutzbar zu machen, sollten folgende Punkte angegangen werden:

1. **Bugfix der Kandidaten-Persistenz:** Es muss sichergestellt werden, dass im Import-Lauf (`pipeline.py`) die extrahierten Kandidaten über `save_knowledge_base` dauerhaft in `kb.json` gespeichert werden.
2. **Automatisierung des BPMN-Transformers:** Der Zwischenschritt der manuellen Transformation sollte wegfallen. Große BPMN-Dateien sollten beim Import automatisch vom System transformiert und nahtlos eingelesen werden.
3. **Echter Datei-Upload in der UI:** Statt Dateien manuell in lokale Ordner zu kopieren, sollte Streamlit-nativ eine Upload-Schaltfläche (`st.file_uploader`) für Prozessdokumente bereitgestellt werden.
4. **Erklärungen und Hilfestellungen in der UI:** Komplexe Einstellungen (wie der Fuzzy-Matching-Threshold von z. B. 0.85) sollten durch Schieberegler ("Tolerant" bis "Strikt") und Hilfetexte verständlicher gemacht werden.

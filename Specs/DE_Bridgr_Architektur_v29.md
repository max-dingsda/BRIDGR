# Bridgr

**EA-Wissensgraph mit Entscheidungs-, Konsolidierungs- und Sicherungsschicht** | Stand: August 2026 | v0.29

---

## 1. Ziel

BRIDGR führt Prozessdokumentation, CMDB-Exporte und ArchiMate-Modelle in einem
gemeinsamen Enterprise-Architecture-Wissensgraphen zusammen und macht diesen über
eine natürlichsprachliche Web-Oberfläche auswertbar.

Kernfrage:
Welche IT-Bausteine unterstützen welche Geschäftsprozesse und wie sicher wissen wir das?

### 1.1 Visionsziel: vollwertiger EA-Chatbot

Der Tab `Kommunikation` ist kein reiner Query-Editor, sondern ein vollwertiger
Unternehmens-Architektur-Chatbot. Benutzer stellen Fragen in natürlicher Sprache zu
Prozessen, Anwendungen, Verantwortlichkeiten, Risiken, Zielen und Abhängigkeiten.
BRIDGR beantwortet diese Fragen auf Basis des Wissensgraphen, nicht aus allgemeinem
Weltwissen.

Dieses Visionsziel ist der Massstab für alle Designentscheidungen im Abfrage-Layer.

### 1.2 Architekturleitlinien

- Neo4j ist die kanonische Laufzeitquelle für den EA-Graphen und für persistierte
  Entscheidungen.
- Der Importpfad bleibt sequentiell, nachvollziehbar und idempotent.
- Fachgraph, Review-/Korrekturlogik und UI-Orchestrierung bleiben sauber getrennt.
- Unsichere Informationen werden explizit als unsicher modelliert oder als offene
  Review-Fälle behandelt.
- Manuelle Korrekturen müssen gezielt rückabwickelbar sein.

---

## 2. Gesamtarchitektur

BRIDGR besteht aus vier logisch getrennten Schichten:

1. **Import- und Extraktionsschicht**
   Prozessdokumente, CMDB-Dateien und ArchiMate-Dateien werden gelesen, analysiert und
   in strukturierte Zwischenobjekte überführt.

2. **Schreib- und Konsolidierungsschicht**
   Der `GraphWriter` und zugehörige Services schreiben den Fachgraphen in Neo4j,
   führen Identitätsauflösung durch und pflegen persistente Review-Entscheidungen.

3. **Entscheidungs- und Korrekturschicht**
   Benutzerentscheidungen wie Bestätigung, Ablehnung, manuelle Zuordnung, Rücknahme
   und Dubletten-Merge werden als separate Betriebsmetadaten modelliert, damit sie
   nachvollziehbar und selektiv rückgängig gemacht werden können.

4. **Abfrage- und UI-Schicht**
   Streamlit rendert die Arbeitsoberfläche. Ein LLM fungiert im Chat als Orchestrator
   für read-only Cypher-Abfragen auf den Fachgraphen.

### 2.1 Hauptdatenfluss

```text
Prozessdokumente / CMDB / ArchiMate
        |
        v
Extraktion / Normalisierung / Matching
        |
        v
Review-Artefakte + Fachentscheidungen
        |
        v
Neo4j-Fachgraph + Neo4j-Entscheidungsgraph
        |
        v
Streamlit-UI + Chat-Layer
```

### 2.2 Kanonische Quellen

- **Neo4j-Fachgraph**
  enthält fachliche Objekte und Beziehungen, die für Analyse, Chat und Export relevant sind.
- **Neo4j-Entscheidungsgraph**
  enthält betriebliche Korrektur- und Auditobjekte für manuelle Entscheidungen.
- **`archimate_mapping.json`**
  enthält alle konfigurierbaren ArchiMate-Mappings.
- **`Output/latest_run.json`**
  ist ein UI-Artefakt für Review und Transparenz, nicht die kanonische Wahrheitsquelle.

---

## 3. Inputs und Dateifluss

### 3.1 Eingangsdateien

- Prozessdokumente als BPMN, TXT, DOCX oder PDF
- transformierte BPMN-TXT-Dateien aus grossen XML-Modellen
- CMDB-Exportdateien als CSV, eine Datei pro Objektart (Anwendungen, Server, Schnittstellen)
- ArchiMate-Modelle im Exchange Format 3.0 oder 3.1 als `.xml` oder `.archimate`

### 3.2 Inbox-Prinzip

`Input/` ist die Arbeits-Inbox für neue Dateien. Verarbeitete Prozessdateien bleiben
nicht dauerhaft dort liegen.

### 3.3 Archivierung

Verarbeitete Prozessdateien werden nach erfolgreichem Lauf nach
`data/input_archive/<timestamp>/` verschoben.

### 3.4 Laufmodi

- `full`: alle Prozessdateien in `Input/`
- `partial`: nur explizit ausgewählte Dateien

CMDB-Synchronisation und ArchiMate-Import/-Export werden separat ausgelöst.

---

## 4. Scope

| Bereich | In Scope | Out of Scope |
| --- | --- | --- |
| Eingabeformate | BPMN, TXT, DOCX, PDF, CSV-CMDB (pro Objektart), ArchiMate 3.0/3.1 | weitere Office-/CMDB-Formate |
| UI | Streamlit mit 6 Tabs (Kommunikation, Import, Zuordnungen, Organisation, EA-Modell, Konfiguration) | eigenständige CLI-Review |
| Chat | LLM-Orchestrierung mit Tool-Use und Prompt-Only-Fallback | Agenten-Orchestrierung |
| Graph | Neo4j als Fach- und Entscheidungsgraph | alternatives Graph-Backend |
| Review | manuelle Zuordnung, Ablehnung, Rücknahme, Merge | externes Ticketing |
| ArchiMate | Import, Export, Mapping-Konfiguration, Kandidaten-Review | Views/Viewpoints |
| Konsolidierung | Merge für `OrgEinheit` und `Prozess`, später erweiterbar | generischer Merge beliebiger Labels |

---

## 5. Domänenmodell

### 5.1 Fachknoten

#### Prozess

Geschäftsprozess aus Prozessdokumenten oder ArchiMate. Fachliche Primäridentität aus
`prozess_id`, sofern vorhanden. Zusätzlich kann `archimate_id` existieren.

#### Anwendung

CMDB-Anwendung oder ArchiMate-Anwendungsobjekt. Fachliche Primäridentität ist `cmdb_id`,
falls vorhanden.

#### Schnittstelle

Separat geführter Integrations- oder Übergabepunkt.

#### Server

Physischer oder virtueller Infrastrukturknoten mit `server_type`.

#### OrgEinheit

Reale organisatorische Einheit. Entsteht durch manuelle Pflege, bestätigte Kandidaten,
CMDB-Owner-Auflösung oder ArchiMate-Import.

#### Rolle

Prozessteilnehmer auf Prozessebene, typischerweise aus BPMN-Lanes. Eine Rolle ist keine
OrgEinheit und impliziert keine Verantwortung.

#### Alias

Deterministische alternative Bezeichnung für `Anwendung` oder `OrgEinheit`. Dient der
Identitätsauflösung in Pipeline und Chat.

#### Stakeholder

Interessengruppe oder Partei aus dem Motivation-Layer.

#### Fähigkeit

Strategische oder operative Fähigkeit.

#### Ressource

Genutzte Ressource.

#### Ziel

Explizit modelliertes Ziel, Outcome, Meaning oder Value.

#### Anforderung

Normative Vorgabe, Constraint oder Principle.

#### Kontext

Externer Einflussfaktor oder Assessment.

#### Risiko

Explizit modelliertes Risiko.

#### Datenobjekt

Daten- oder Informationsobjekt.

#### Infrastruktur

Technologische Infrastruktur unterhalb der Anwendungsschicht.

#### Ablehnung

Persistente Ablehnungsmarke für eine extrahierte Bezeichnung in einem konkreten Prozess.
Sie dient der Unterdrückung erneuter Vorschläge.

#### OrgKandidat

Interner Betriebsknoten für eine unaufgelöste OrgEinheit-/Rollen-Nennung aus Prozessimport
oder CMDB-Sync (`status`: `open`, `mapped` oder `rejected`; `mapped_org_unit` bei `mapped`).
Ersetzt seit der vollständigigen Ablösung von `kb.json` (Finding #15) den früheren
`org_unit_candidates`-Abschnitt der Wissensbasis-Datei. Wie `ManualDecision` und `Ablehnung`
bewusst nicht Teil des Query-Schemas für den Chat-Layer.

### 5.2 Fachbeziehungen

```text
(:Anwendung)-[:DIENT]->(:Prozess)
(:Anwendung)-[:KÖNNTE_DIENEN]->(:Prozess)
(:Rolle)-[:BETEILIGT_AN]->(:Prozess)
(:OrgEinheit)-[:KANN_EINNEHMEN]->(:Rolle)
(:OrgEinheit)-[:VERANTWORTET]->(:Prozess|:Anwendung|:Schnittstelle|:Server|:Infrastruktur)
(:Prozess)-[:FOLGT_AUF]->(:Prozess)
(:Anwendung)-[:USES_INTERFACE]->(:Schnittstelle)
(:Anwendung|:Schnittstelle)-[:RUNS_ON]->(:Server)
(:Alias)-[:KANN_MEINEN]->(:Anwendung|:OrgEinheit)
(:Risiko)-[:BETRIFFT]->(...)
(:Faehigkeit|:Anwendung)-[:MITIGIERT]->(:Risiko)
(:Faehigkeit|:Anforderung)-[:REALISIERT]->(...)
(:Prozess|:Anwendung)-[:BENOETIGT]->(:Ressource)
(:Prozess|:Anwendung)-[:UNTERSTUETZT]->(:Ziel|:Faehigkeit)
(:Prozess|:Anwendung)-[:VERARBEITET]->(:Datenobjekt)
(:Anwendung)-[:LAEUFT_AUF]->(:Infrastruktur)
(:Kontext|:Anforderung)-[:BEEINFLUSST]->(...)
(:Stakeholder|:OrgEinheit)-[:IST_VERBUNDEN_MIT]->(...)
```

### 5.3 Wichtige Properties

#### Auf `:DIENT`

- `konfidenz`
- `source`
- `raw_name`

#### Auf `:KÖNNTE_DIENEN`

- `score`

#### Auf ArchiMate-importierten Knoten

- `archimate_id`
- `archimate_source`
- `archimate_type`

#### Auf ArchiMate-importierten Relationen

- `archimate_rel_type`

#### Auf `:Rolle`

- `role_only`

---

## 6. Anwendungsschichten und Module

```text
bridgr/
├── core/          # Konfiguration, LLM-Client, Neo4j, Query-Schema
├── processing/    # Pipeline, CMDB, Import-Hilfen, Laufartefakte
├── prompts/       # Extraktions- und Chat-Prompts
├── skills/        # GraphWriter, Matching, Extraktion
├── services/      # UI-seitig aufgerufene Orchestrierung
├── ui/            # Streamlit-Tabs
├── data/          # archimate_mapping.json, Archive
├── Input/
├── Output/
├── config.json
├── app.py
└── main.py
```

### 6.1 Hauptverantwortlichkeiten

- `processing/pipeline.py`
  orchestriert Dokumentlauf, Matching und Schreibpayloads
- `skills/graph_writer.py`
  kapselt den fachlichen Schreibzugriff auf Neo4j
- `services/review_service.py`
  kapselt Review-Aktionen für Anwendungszuordnungen
- `services/organization_service.py`
  kapselt Org-, Owner- und Rollenpflege
- `services/query_service.py`
  baut den dynamischen Chat-Systemprompt und führt den Dialogturn aus
- `services/archimate_import_service.py` / `services/archimate_export_service.py`
  kapseln ArchiMate-Import und -Export

---

## 7. Importlogik

### 7.1 Prozessdokumente

Jedes Prozessdokument durchläuft diese Kette:

1. Dateityp-spezifische Textgewinnung
2. LLM-Extraktion oder BPMN-strukturelle Extraktion
3. Matching gegen CMDB und bestätigte Entscheidungen
4. Erzeugung von Review-Artefakten
5. Aufbau eines `GraphWritePayload`
6. Schreiben nach Neo4j

### 7.2 Matching-Reihenfolge

1. bestätigte Entscheidungen aus Neo4j
2. abgelehnte Entscheidungen aus Neo4j
3. Alias-Auflösung
4. Fuzzy Matching
5. offen / manuelle Klärung

### 7.3 Konfidenzmodell

- `stark`
  bestätigt oder sicher gematcht, wird als `DIENT` bzw. `VERANTWORTET` geschrieben
- `schwach`
  Anwendungskandidat mit Review-Bedarf, wird als `KÖNNTE_DIENEN` geschrieben; unsichere
  CMDB-Owner werden als `OrgKandidat` geführt (kein direkter Kanten-Schreibpfad)
- `offen`
  kein Match, nur Review-Artefakt

### 7.4 Re-Import-Verhalten

- fachliche Importkanten werden pro Prozess bzw. pro CMDB-Sync deterministisch aktualisiert
- persistente manuelle Entscheidungen müssen über Re-Importe hinweg erhalten bleiben
- bestätigte oder manuell angelegte Zuordnungen dürfen nicht durch blösses
  Verschwinden eines Rohbegriffs im Quelldokument verloren gehen

### 7.5 CMDB-Import-Format

#### 7.5.1 Eingabemodell

CMDB-Daten werden als eine CSV-Datei pro Objektart eingelesen:

- eine Datei für Anwendungen
- eine Datei für Server
- eine Datei für Schnittstellen

Jede Datei enthält nur Einträge eines einzigen Typs. Die Zuordnung von Dateinamen zu
Objektarten wird explizit in `config.json` unter `cmdb_type_files` konfiguriert.
Fehlt ein Eintrag für einen Typ, wird dieser Typ beim Sync übersprungen.

Beispielkonfiguration:

```json
"cmdb_type_files": {
  "application": "Anwendungen.csv",
  "server": "Server.csv",
  "interface": "Schnittstellen.csv"
}
```

#### 7.5.2 Beziehungen in Typ-Dateien

Beziehungen zwischen Objekten werden als Spalten in der Quelldatei des Quellobjekts
abgelegt. Mehrere Ziel-IDs werden durch den konfigurierten Mehrwert-Trennzeichen getrennt
(Standard: `|`, konfigurierbar über `cmdb_multivalue_separator` in `config.json`).

In der Anwendungsdatei stehen typischerweise:

- `runs_on`: semikolon- oder pipetrennte Liste von Server-IDs (konfigurierbar: `cmdb_runs_on_column`)
- `uses_interfaces`: semikolon- oder pipetrennte Liste von Schnittstellen-IDs (konfigurierbar: `cmdb_uses_interfaces_column`)

Server- und Schnittstellendateien enthalten keine Beziehungsspalten.

Beispiel Anwendungsdatei:

```csv
id;name;owner_name;runs_on;uses_interfaces
APP-001;SAP S/4HANA FI;Buchhaltung;SRV-001;IF-001|IF-015
```

#### 7.5.3 Gemeinsame Pflichtspalten

Alle Typ-Dateien teilen dieselben konfigurierbaren Spaltennamen für ID, Name und
Besitzer (`cmdb_uuid_column`, `cmdb_name_column`, `cmdb_owner_name_column`). Nur
Serverdateien verwenden zusätzlich `cmdb_server_type_column`.

#### 7.5.4 Internes Datenmodell

Der Loader erzeugt aus allen Typ-Dateien gemeinsam ein `NormalizedCmdb`-Objekt mit:

- `entities`: Liste aller `CmdbEntity`-Objekte aller Typen
- `relations`: Liste aller `CmdbRelation`-Objekte aus den Beziehungsspalten

Der `GraphWriter` bleibt unverändert und kennt nur das `NormalizedCmdb`-Interface.

#### 7.5.5 Rückwärtskompatibilität

Ist `cmdb_type_files` in `config.json` leer oder nicht gesetzt, fällt BRIDGR auf das
Legacy-Format zurück:

- eine gemischte Entities-Datei (konfiguriert über `cmdb_filename`) mit einer `entity_type`-Spalte
- eine optionale separate Relationsdatei (konfiguriert über `cmdb_relations_filename`)

Das Legacy-Format ist weiterhin voll funktionsfähig, aber als Entwicklungsformat
eingestuft. Produktive CMDB-Anbindungen sollen das Typ-Datei-Format verwenden.

---

## 8. Matching, Review und Persistenz

### 8.1 Bestätigen eines schwachen Anwendungskandidaten

Beim Bestätigen einer `KÖNNTE_DIENEN`-Kante:

1. wird die schwache Kante gelöscht
2. wird eine starke `DIENT`-Kante geschrieben
3. wird `raw_name` auf der `DIENT`-Kante gesetzt
4. wird bei abweichendem Begriff ein `Alias` auf die Anwendung geschrieben
5. wird die Anzeige in `latest_run.json` gezielt aktualisiert

### 8.2 Ablehnen eines Anwendungskandidaten

Beim Ablehnen:

1. wird die `KÖNNTE_DIENEN`-Kante gelöscht
2. wird ein `(:Ablehnung)`-Knoten geschrieben
3. wird der Begriff bei nächsten Läufen nicht erneut vorgeschlagen

### 8.3 Manuelle Zuordnung einer Anwendung

Bei manueller Zuordnung im Review-Tab:

1. wird direkt eine starke `DIENT`-Kante geschrieben
2. bleibt die Entscheidung über Re-Importe hinweg persistent
3. muss die Entscheidung später gezielt rücknehmbar sein

### 8.4 Owner- und Rollenzuordnungen

- `VERANTWORTET` für Prozesse und CMDB-Ziele wird nur explizit oder über exakte
  Owner-Auflösung geschrieben
- `KANN_EINNEHMEN` entsteht nur über Benutzeraktion

---

## 9. Graph Writer

### 9.1 Rolle

`GraphWriter` ist die einzige fachliche Schreibkomponente für Neo4j. Er:

- normalisiert Identitäten
- schreibt Prozess-, CMDB- und Review-Kanten
- kapselt Promote-/Reject-Operationen
- laedt persistente Entscheidungen für Re-Importe
- führt begrenzte Cross-Source-Identitätsauflösung durch

### 9.2 Idempotenz

Alle regulären Schreibpfade sind auf wiederholte Ausführung ausgelegt:

- `MERGE` für Knoten und stabile Fachbeziehungen
- prozessbezogene Löschung und Wiederaufbau für volatile Importkanten
- Erhalt persistenter manueller Entscheidungen über Wiedereinpielen

### 9.3 Cross-Source-Identitätsauflösung

Bereits heute existieren gezielte Anreicherungen statt blindem Duplikatbau:

- BPMN-/Dokumentprozess auf vorhandenen Prozess ohne `prozess_id`
- CMDB-Anwendung auf vorhandene ArchiMate-Anwendung ohne `cmdb_id`
- case-insensitive Kanonisierung für `OrgEinheit`

### 9.4 Grenzen des aktuellen Writers

Der aktuelle Writer schreibt Fachgraph und Teilentscheidungen, hat aber noch keine
vollständigige Korrekturschicht für:

- Undo manueller Entscheidungen
- Merge von Dubletten mit Auditspur
- Alias-Lifecycle bei Rücknahmen

Diese Fähigkeiten werden in Abschnitt 10 spezifiziert.

---

## 10. Entscheidungs- und Korrekturschicht

### 10.1 Ziel

Benutzer müssen manuelle Eingriffe nachvollziehbar, selektiv und sicher rückgängig
machen können. Gleichzeitig müssen fachliche Dubletten aus unterschiedlichen Quellen
gezielt konsolidierbar sein.

### 10.2 Grundprinzip

Der Fachgraph bleibt vom Entscheidungsgraph getrennt.

- Der **Fachgraph** enthält Objekte wie `Prozess`, `Anwendung`, `OrgEinheit`, `Alias`.
- Der **Entscheidungsgraph** enthält Betriebsmetadaten für manuelle Eingriffe.

### 10.3 Entscheidungsknoten

Neuer interner Knotentyp:

```text
(:ManualDecision)
```

Pflichtattribute:

- `decision_id`
- `decision_type`
- `status`
- `created_at`
- `payload_json`

Optionale Attribute:

- `supersedes_decision_id`
- `reverted_at`
- `notes`

### 10.4 Implementierter Umsetzungsstand (Ist-Zustand)

`ManualDecision` wird als isolierter Knoten ohne Kanten zu den betroffenen Fachobjekten
persistiert. Die Zuordnung betroffener Objekte (Prozess, Anwendung, OrgEinheit, Rolle usw.)
erfolgt ausschliesslich über das Feld `payload_json`, das die relevanten IDs und Namen
als JSON-String enthält.

Rücknahmen (`decision_revert`) referenzieren die ursprüngliche Entscheidung ebenfalls
über `supersedes_decision_id` im Payload, nicht über eine Graph-Kante.

Die Rücknahme-Logik parst das Payload im Speicher und setzt ad-hoc-Cypher-Statements ab,
um die ursprünglichen Graphänderungen rückgängig zu machen.

### 10.4a Zukunftsperspektive: Explizite Betriebsrelationen

Architektonisch vorgesehen, aber derzeit nicht implementiert sind explizite Kanten:

```text
(:ManualDecision)-[:AFFECTS]->(:Prozess)
(:ManualDecision)-[:AFFECTS]->(:Anwendung)
(:ManualDecision)-[:AFFECTS]->(:OrgEinheit)
(:ManualDecision)-[:AFFECTS]->(:Rolle)
(:ManualDecision)-[:CREATED_ALIAS]->(:Alias)
(:ManualDecision)-[:SUPERSEDES]->(:ManualDecision)
```

Diese Kanten würden rein betriebliche Metadaten abbilden und keine fachlichen EA-Beziehungen
darstellen. Eine Migration dorthin ist möglich, sobald die Payload-Variante nicht mehr
ausreicht (z. B. für komplexe Auditing-Anforderungen).

### 10.5 Entscheidungstypen

Geplante `decision_type`-Werte:

- `manual_link`
- `confirmed_candidate_link`
- `manual_process_owner_assignment`
- `manual_role_assignment`
- `candidate_owner_confirmation`
- `entity_merge`
- `decision_revert`

### 10.6 Sichtbarkeit im Chat-Layer

`ManualDecision` und zugehörige betriebliche Relationen sind **nicht Teil des
freigegebenen Query-Schemas**.

Konsequenzen:

- `core/graph_schema.py` bleibt allowlist-basiert
- `build_query_schema_reference()` nimmt `ManualDecision` nicht auf
- der dynamisch erzeugte Systemprompt erwähnt diese Knoten nicht
- das LLM kann den Entscheidungsgraph weder absichtlich noch versehentlich abfragen

Der Chat beantwortet nur fachliche Fragen auf Basis des Fachgraphen.

### 10.7 Undo manueller Entscheidungen

Jede manuelle Aktion mit fachlicher Wirkung erzeugt genau einen `ManualDecision`-Knoten.
Eine Rücknahme:

1. referenziert die ursprüngliche Entscheidung
2. entfernt nur die konkret von dieser Entscheidung verursachten Graphänderungen
3. aktualisiert abhängige UI-Artefakte gezielt
4. hinterlaesst selbst wieder eine persistente Auditspur

Aktueller Umsetzungsstand:

- Rücknahme ist für `manual_link`, `confirmed_candidate_link`,
  `manual_process_owner_assignment` und `manual_role_assignment` implementiert.
- Die Rücknahme arbeitet aktuell payload-basiert und setzt den ursprünglichen
  Entscheidungsknoten auf `status = reverted`.
- Zusätzlich wird eine neue `ManualDecision` vom Typ `decision_revert` geschrieben.
- Der Rücknahme-Eintrag dient als Auditspur und wird selbst nicht als neue aktive
  Fachentscheidung behandelt.

### 10.8 Rücknahmesichere Fälle

In Scope für die erste Ausbaustufe:

- manueller `DIENT`-Link
- bestätigter `KÖNNTE_DIENEN`-Link
- manuelle Prozess-Owner-Zuordnung
- manuelle Rollenzuordnung

### 10.9 Abgrenzung zu globaler Wiederherstellung

Das selektive Undo bleibt auf die Wirkungen einzelner manueller Entscheidungen
beschränkt. Die globale Wiederherstellung des Gesamtzustands ist eine getrennte
Sicherungsfunktion gemäß Kapitel 12 und wird nicht über `ManualDecision`
modelliert.

---

## 11. Konsolidierungsschicht für Dubletten

### 11.1 Ziel

BRIDGR muss fachliche Dubletten zusammenführen können, auch wenn kein manueller Fehler
den Zustand verursacht hat.

Typische Fälle:

- `OrgEinheit`: unterschiedliche Schreibweisen oder manuell falsch angelegte Einheiten
- `Prozess`: identischer Prozess aus TXT und BPMN unter leicht abweichenden Namen
- später optional `Anwendung`

### 11.2 Mergebare Labels

Erste Ausbaustufe:

- `OrgEinheit`
- `Prozess`

### 11.3 Merge-Ziele

Ein Merge soll:

1. einen Quellknoten in einen Zielknoten konsolidieren
2. alle relevanten Beziehungen auf den Zielknoten übertragen
3. doppelte Beziehungen vermeiden
4. die Quellbezeichnung als Alias auf dem Ziel bewahren
5. den Quellknoten löschen
6. den Merge als `ManualDecision` dokumentieren

### 11.4 Alias-Fortschreibung

Bei jedem Merge gilt:

- Die Quellbezeichnung wird als Alias des Zielknotens weitergeführt, sofern sie nach
  Normalisierung nicht identisch mit dem Zielnamen ist.
- Dadurch bleibt der Begriff aus den Quelldokumenten für spätere Re-Importe und
  Chat-Auflösung erhalten.

Ohne diese Alias-Fortschreibung würde derselbe Rohbegriff beim nächsten Import erneut
zu einer Dublette führen.

### 11.5 Beziehungsübernahme

Beim Merge werden eingehende und ausgehende Beziehungen des Quellknotens auf den Zielknoten
umgehängt, soweit der Typ für das betroffene Label fachlich erlaubt ist.

### 11.6 Beziehungsdeduplizierung

Beziehungsübernahme ist niemals blind.

Regel:

- Wenn am Ziel bereits eine gleichartige Beziehung mit identischem Gegenspieler und
  identischer Richtung existiert, wird keine zweite Kante erzeugt.
- Falls beide Beziehungen Properties tragen, gilt eine konfliktarme Konsolidierungsregel:
  - bestätigte/starke Information gewinnt vor schwacher
  - vorhandene IDs und ArchiMate-Metadaten bleiben erhalten
  - redundante Duplikate werden verworfen

### 11.7 Merge von `OrgEinheit`

Zu berücksichtigende Fachbeziehungen:

- ausgehend: `VERANTWORTET`, `KANN_EINNEHMEN`, `IST_VERBUNDEN_MIT`
- eingehend über Alias: `(:Alias)-[:KANN_MEINEN]->(:OrgEinheit)`
- betriebliche Metadaten aus `ManualDecision`

Aktueller Umsetzungsstand:

- Der Backend-Merge für `OrgEinheit` ist implementiert.
- Kantenübernahme erfolgt derzeit für `VERANTWORTET`, `KANN_EINNEHMEN`,
  ausgehendes `IST_VERBUNDEN_MIT` sowie bestehende eingehende Alias-Kanten.
- Die Deduplizierung erfolgt aktuell über `MERGE` auf den Zielkanten.
- Eine weitergehende Property-Konsolidierung ist für diese erste Ausbaustufe noch
  nicht erforderlich und daher noch nicht separat implementiert.

### 11.8 Merge von `Prozess`

Zu berücksichtigende Fachbeziehungen:

- eingehend: `DIENT`, `KÖNNTE_DIENEN`, `BETEILIGT_AN`, `VERANTWORTET`, `REALISIERT`,
  `UNTERSTUETZT`, `BENOETIGT`, `VERARBEITET`, `BETRIFFT`, `BEEINFLUSST`
- ausgehend: `FOLGT_AUF`, `UNTERSTUETZT`, `BENOETIGT`, `VERARBEITET`
- zusätzliche Konsolidierung von `prozess_id`, `archimate_id`, `archimate_type`

Aktueller Umsetzungsstand:

- Der Backend-Merge für `Prozess` ist implementiert.
- Bestehende gleichartige Beziehungen am Ziel werden nicht doppelt angelegt.
- Der Quellname wird als Alias des Zielprozesses weitergeführt.
- Die Rücknahme arbeitet snapshot-basiert über die im Merge-Payload gespeicherten
  Knoten- und Beziehungshinweise.

### 11.9 Merge-Precheck

Vor jedem Merge zeigt die UI:

- Quell- und Zielobjekt
- Quellenhinweise
- Anzahl eingehender/ausgehender Beziehungen
- potentielle Konflikte
- Alias, der entstehen würde

Erst danach darf der Merge explizit bestätigt werden.

Aktueller Umsetzungsstand:

- Im UI existieren Merge-Bereiche für `OrgEinheit` und `Prozess`.
- Der Precheck zeigt bereits Quell-/Zielobjekt, Anzahl ein- und ausgehender Kanten,
  Dubletten am Ziel, Alias-Übernahme sowie erkannte Property-Konflikte.
- Zusätzlich wird eine kompakte Wirkungszusammenfassung angezeigt
  (zu übertragende Kanten, nicht doppelt anzulegende Kanten, Verhalten bei Konflikten).
- Weitere Verfeinerungen der Visualisierung sind möglich, aber keine funktionale
  Voraussetzung mehr für die erste Ausbaustufe.

---

## 12. Sicherungs- und Wiederherstellungsschicht

### 12.1 Ziel

Vor jeder schreibenden, fachlich relevanten Operation muss ein vollständigiger,
wiederherstellbarer Stand des BRIDGR-Graphen vorliegen. Damit sind fehlerhafte
Importe, fehlerhafte CMDB-Importe und unerwartete Merge-Effekte auch dann
rückgängig zu machen, wenn sie nicht von einer einzelnen `ManualDecision`
abgedeckt sind.

Snapshots sind ein v1-Sicherheitsnetz. Sie ersetzen weder das gezielte Undo
manueller Entscheidungen noch die Idempotenz der Importlogik.

### 12.2 Auslöser und Sperrregel

Ein Snapshot wird unmittelbar vor der ersten Graph-Schreiboperation automatisch
erstellt für:

- Prozessimport (`run_pipeline`), einschliesslich des darin enthaltenen
  CMDB-Abgleichs
- explizite CMDB-Synchronisation
- Merge von `OrgEinheit` oder `Prozess`

Ein fehlgeschlagener oder nicht verifizierbarer Snapshot ist ein harter Gate:
Die auslösende Schreiboperation wird nicht gestartet und die UI zeigt einen
verständlichen Fehler mit dem technischen Detail im Debug-Log an. Reine
Chat-Abfragen, Prechecks, Review-Listen und gezieltes Undo erzeugen keinen
Snapshot.

### 12.3 Logisches Snapshot-Format

Ein Snapshot ist ein anwendungsverwalteter, logischer Export und keine
abhängige Neo4j-Server- oder Dateisystem-Sicherung. Er enthält in einem
konsistenten Lesezustand:

- alle fachlichen Knoten und Beziehungen
- interne Betriebsmetadaten (`ManualDecision`, `Ablehnung`, `OrgKandidat` und
  Alias-Projektionen)
- Knotenlabels, Properties, Beziehungstypen und Beziehungsproperties
- eine Manifestdatei mit Snapshot-ID, Zeitpunkt, Auslöser, Operation,
  Graph-Objektzählern, Quell-/Konfigurationshinweisen und Integritätsprüfsumme

Beziehungsendpunkte werden über fachlich stabile Schlüssel beziehungsweise die
im Snapshot enthaltene interne Knotenzuordnung referenziert; flüchtige Neo4j-
Element-IDs sind kein Restore-Vertrag. Zugangsdaten, LLM-Geheimnisse und die
Eingabedateien selbst werden nicht im Snapshot gespeichert.

### 12.4 Ablage, Aufbewahrung und Integrität

Snapshots liegen unter dem aktiven Laufzeit-Ausgabepfad,
`<output_path>/snapshots/<snapshot-id>/`, und bestehen mindestens aus dem
Graph-Export und dem Manifest. Erst nach erfolgreicher Vollständigigkeits- und
Prüfsummenprüfung gilt ein Snapshot als verwendbar.

Die Anzahl aufbewahrter, gültiger Snapshots ist über
`snapshot_retention_count` konfigurierbar und beträgt standardmäßig `10`.
Altere Snapshots werden erst nach erfolgreicher Erstellung eines neuen,
verifizierten Snapshots entfernt. Ein fehlgeschlagener Snapshot verändert den
vorhandenen Bestand nicht.

### 12.5 Wiederherstellung

Die Wiederherstellung ist im Tab `Konfiguration` verfügbar. Die UI zeigt vor
der expliziten Bestätigung mindestens Snapshot-ID, Zeitpunkt, Auslöser und
Objektzähler an.

Wiederherstellung ist nur bei explizit konfigurierter, dedizierter
BRIDGR-Neo4j-Datenbank erlaubt. Sie ersetzt deren gesamten Inhalt; fremde
Anwendungsdaten dürfen daher nicht in dieser Datenbank liegen.

Der Ablauf lautet:

1. aktuellen Zustand als Snapshot vor der Wiederherstellung sichern
2. Ziel-Snapshot gegen Manifest und Prüfsumme validieren
3. den BRIDGR-Graphen atomar auf den Snapshot-Zustand zurücksetzen
4. das Ergebnis anhand der im Manifest gespeicherten Objektzähler verifizieren
5. die Wiederherstellung als interne Betriebsoperation protokollieren

Schlägt die Wiederherstellung fehl, bleibt der unmittelbar zuvor erzeugte
Pre-Restore-Snapshot verfügbar. Snapshot-Operationen sind weder über den
Chat sichtbar noch Teil des freigegebenen Query-Schemas.

### 12.6 UI und Nachvollziehbarkeit

Der Konfigurations-Tab zeigt die letzten Snapshots mit Status, Zeitstempel,
Auslöser, Objektzählern und verfügbarem Speicherort. Nutzer können nur
validierte Snapshots wiederherstellen. Jede Erstellung, Bereinigung und
Wiederherstellung wird mit ausreichendem Kontext im Debug-Log protokolliert.

### 12.7 Nicht-Ziele

- Kein Ersatz für reguläre Infrastruktur-Backups von Neo4j oder des Hostsystems
- Keine Wiederherstellung externer Quelldateien, LLM-Konfiguration oder Secrets
- Keine teilweise Wiederherstellung einzelner Fachobjekte in v1
- Keine automatische Wiederherstellung ohne explizite Nutzerbestätigung

### 12.8 Implementierungsstand

Die Sicherungs- und Wiederherstellungsschicht ist implementiert in
`services/snapshot_service.py`. Sie verwendet `Neo4jClient.execute_write_batch()`
für die transaktionale Wiederherstellung, schreibt den logischen Export unter
`<output_path>/snapshots/` und wird in Pipeline, explizitem CMDB-Sync und Merge
als harter Gate aufgerufen. Der Konfigurations-Tab zeigt valide und invalide
Snapshots an und erlaubt nur nach Bestätigung die Wiederherstellung.

---

## 13. Abfrage-Layer

### 13.1 Architekturprinzip

Der LLM ist Orchestrator für fachliche Graphabfragen. Er erzeugt read-only Cypher auf
Basis eines dynamisch zusammengesetzten, aber allowlist-basierten Schemas.

### 13.2 Dynamischer Systemprompt

`services/query_service.py` baut den Chat-Prompt aus:

- `prompts/chat_system.md`
- Query-Protokoll (`tool-use` oder `prompt-only`)
- `build_archimate_mapping_reference()`
- `build_query_schema_reference()`

Das Schema ist nicht datenbankintrospektiv, sondern wird aus `core/graph_schema.py`
aufgebaut. Dadurch lassen sich interne Knotentypen wie `ManualDecision` ohne Verrenkungen
ausserhalb des Chat-Schemas halten.

Nach dem fachlichen Antwort-Call durchläuft die fertige Antwort einen zweiten, ausschließlich
sprachlichen LLM-Call. Dieser Sprach-Editor erhält die letzte natürliche Nutzerfrage, den
Antwortentwurf und die aus dem Query-Ergebnis abgeleiteten geschützten Objektbezeichnungen
und Identifikatoren. Er glättet Rechtschreibung, Grammatik und unbeabsichtigte
Sprachmischungen in der Sprache der Nutzerfrage, ohne Fakten, Zahlen, Unsicherheiten,
Markdown oder geschützte Namen zu verändern. Etablierter Business-Slang darf erhalten
bleiben. Schlägt dieser Call fehl oder liefert er keinen Text, wird der fachliche Entwurf
unverändert ausgegeben.

Die UI-Sprache steuert ausschließlich katalogisierte UI-Texte. Freie Inhalte wie
Chat-Nachrichten, Nutzereingaben und fachliche Objektbezeichnungen werden nach dem LLM-Call
nicht per Wortersetzung lokalisiert, damit die Antwortsprache der Nutzerfrage maßgeblich bleibt.

### 13.3 Query-Sicherheit

- nur read-only Cypher
- Validator prüft Labels, Relationen, Richtungen und Properties
- `IST_VERBUNDEN_MIT` ist als Ausnahme ohne Labelpaarbeschränkung erlaubt
- interne Knoten wie `Ablehnung`, `ManualDecision` und `OrgKandidat` sind nicht freigegeben

### 13.4 Alias-Nutzung im Chat

Alias-Knoten unterstützen:

- deterministische Auflösung alternativer Begriffe
- Rückgriff bei leeren Treffern
- Robustheit gegen unterschiedliche Schreibweisen und Merge-Folgen

### 13.5 Unsicherheit im Chat

Der Chat darf bestätigte Fakten und unbestätigte Kandidaten unterscheiden:

- `DIENT` / `VERANTWORTET` = bestätigte Fakten
- `KÖNNTE_DIENEN` = nicht bestätigte Kandidaten

Entscheidungsmetadaten selbst sind kein Chat-Gegenstand.

---

## 14. UI-Architektur

### 14.1 Tab `Kommunikation`

- Chat mit Verlauf
- LLM-Orchestrierung
- technische Fehlerübersetzung in Klartext

### 14.2 Tab `Import`

- Prozessimport aus der Inbox `Input/` im Modus `full` oder `partial`
- optionale BPMN-Transformation vor dem Import
- CMDB-Synchronisation nach Neo4j
- Archivierung verarbeiteter Prozessdateien

### 14.3 Tab `Zuordnungen`

- Review offener und schwacher Anwendungszuordnungen
- Bestätigen, Ablehnen, manuelle Zuordnung
- Rücknahme zuletzt getroffener manueller Entscheidungen
- Merge-Verwaltung für `Prozess`

### 14.4 Tab `Konfiguration`

- Pfade
- CMDB-Typ-Dateien-Mapping (`cmdb_type_files`): eine Datei pro Objektart
- CMDB-Spaltenmapping (ID, Name, Besitzer, Servertyp, Beziehungsspalten)
- Mehrwert-Trennzeichen für CMDB-Beziehungsspalten (`cmdb_multivalue_separator`)
- Import-/Matching-Einstellungen
- LLM- und Neo4j-Konfiguration
- Sicherungsverwaltung: validierte Snapshots anzeigen und Wiederherstellung
  nach expliziter Bestätigung auslösen

### 14.5 Tab `Organisation`

- Pflege von OrgEinheiten
- Kandidaten-Mapping
- Prozess-Owner-Zuordnung
- Rollenzuordnung
- Merge-Verwaltung für `OrgEinheit`

### 14.6 Tab `EA-Modell`

- ArchiMate-Mapping
- ArchiMate-Import
- ArchiMate-Export
- Review offener ArchiMate-Kandidaten

### 14.7 Korrekturschicht

Zusätzliche Bedienbereiche:

- `Letzte manuelle Änderungen`
- `Entscheidung zurücknehmen`
- `Objekte konsolidieren`
- Merge-Precheck mit Konfliktanzeige

Aktueller Umsetzungsstand:

- `Letzte manuelle Änderungen` und `Entscheidung zurücknehmen` sind im
  Tab `Zuordnungen` vorhanden.
- `Objekte konsolidieren` ist für `Prozess` im Tab `Zuordnungen` und für
  `OrgEinheit` im Tab `Organisation` vorhanden.
- Der Merge-Precheck zeigt bereits fachlich relevante Wirkungen und Konflikte.
- Offen bleiben nur mögliche spätere UX-Verfeinerungen oder die Erweiterung auf
  weitere Objektarten.

---

## 15. Konfiguration

### 15.1 `config.json`

Zentrale Laufzeitkonfiguration für:

- Pfade
- LLM
- Neo4j
- Matching-Schwellwerte
- CMDB-Konfiguration:
  - `cmdb_type_files`: Mapping von Objektart (`application`, `server`, `interface`) auf Dateinamen
  - `cmdb_uuid_column`, `cmdb_name_column`, `cmdb_owner_name_column`, `cmdb_server_type_column`: gemeinsame Spalten aller Typ-Dateien
  - `cmdb_runs_on_column`: Spaltenname für Server-IDs in der Anwendungsdatei (Standard: `runs_on`)
  - `cmdb_uses_interfaces_column`: Spaltenname für Schnittstellen-IDs in der Anwendungsdatei (Standard: `uses_interfaces`)
  - `cmdb_multivalue_separator`: Trennzeichen für Mehrfachwerte (Standard: `|`)
  - `cmdb_filename`, `cmdb_relations_filename`: Legacy-Felder für das Zwei-Dateien-Format, werden ignoriert wenn `cmdb_type_files` gesetzt ist
- Chat-Modus
- Sicherung:
  - `snapshot_retention_count`: Anzahl gültiger, anwendungsverwalteter
    Graph-Snapshots, die aufbewahrt werden (Standard: `10`)

### 15.2 `archimate_mapping.json`

Enthält:

- `elements.import`
- `elements.ignore`
- `elements.export`
- `relationships.import`
- `relationships.export`
- `relationships.bridgr_relation`
- `pending_candidates`

### 15.3 Konfigurationsprinzip

Organisationsspezifisches Mapping-Wissen gehoert in JSON-Konfiguration, nicht in den Code.

---

## 16. ArchiMate-Integration

### 16.1 Import

Der Import:

- erkennt 3.0 und 3.1 automatisch über den Root-Namespace
- mappt Elementtypen über `archimate_mapping.json`
- führt exakte Identitätsanreicherung oder Fuzzy-Kandidatenbildung durch
- schreibt Relationen nur bei konfiguriertem `bridgr_relation`
- protokolliert übersprungene Typen und Relationen

### 16.2 Export

Der Export:

- exportiert den vollständigigen BRIDGR-Graphen
- verwendet für importierte Knoten/Relationen deren originale ArchiMate-Typen
- verwendet für BRIDGR-native Knoten/Relationen die konfigurierten kanonischen Typen
- führt vor Export einen Typ-Precheck für untypisierte Knoten durch

### 16.3 ArchiMate und Konsolidierung

Merge- und Alias-Entscheidungen müssen so gestaltet sein, dass:

- ArchiMate-Importe keine bereits konsolidierten Fachobjekte wieder aufspalten
- Quellbezeichnungen als Alias erhalten bleiben
- `archimate_id` und `archimate_type` bei Konflikten bewusst konsolidiert werden

---

## 17. UML-Diagramme

### 17.1 Komponentendiagramm

Zeigt die logischen Komponenten und ihre Abhängigkeiten.

![BRIDGR Komponentendiagramm](BRIDGR_Komponentendiagramm.png)

### 17.2 Klassenmodell

Zeigt die zentralen konkreten Klassen und die modulbasierten Funktionsgrenzen, gegliedert nach Konfiguration,
Verarbeitung & Skills sowie Services und ArchiMate-Integration.

![BRIDGR Klassenmodell](BRIDGR_Klassenmodell.png)

### 17.3 Sequenzdiagramme

Zeigt die wichtigsten Abläufe als Sequenzdiagramme.

![Sequenz 1 – Dokument-Import-Pipeline](BRIDGR_Sequenzdiagramme_001.png)

![Sequenz 2 – Natürlichsprachige Graph-Abfrage](BRIDGR_Sequenzdiagramme_002.png)

![Sequenz 3 – CMDB-Synchronisation](BRIDGR_Sequenzdiagramme_003.png)

![Sequenz 4 – Review, Merge und Undo](BRIDGR_Sequenzdiagramme_004.png)

---

## 18. Nichtfunktionale Anforderungen

### 18.1 Nachvollziehbarkeit

Alle manuellen Eingriffe müssen auditierbar sein.

### 18.2 Idempotenz

Wiederholte Importe dürfen keine unkontrollierten Duplikate erzeugen.

### 18.3 Geringe Seiteneffekte

UI-Aktionen sollen gezielt nur die betroffenen Prozesse, Kandidaten oder Knoten aktualisieren.

### 18.4 Trennung von Fach- und Betriebsmetadaten

Der Chat darf nur den Fachgraphen sehen. Betriebsmetadaten bleiben intern.

### 18.5 Wiederherstellbarkeit

Jede v1-Schreiboperation, die einen globalen Graphzustand verändern kann,
benötigt vor ihrem Beginn einen validierten Snapshot. Der Snapshot darf keine
Secrets enthalten und eine Wiederherstellung muss vor Ausführung explizit
bestätigt werden.

---

## 19. Akzeptanzkriterien

1. Korrekte Informationen aus den Quelldaten können über die Weboberfläche abgefragt werden.
2. Mappings sind über die Weboberfläche pflegbar.
3. Informationen zu Prozessen, Anwendungen, Schnittstellen, Servern, Zielen und Risiken können abgerufen werden.
4. Die Pipeline läuft stabil durch einen vollständigigen Importzyklus.
5. TXT, DOCX und PDF folgen demselben semantischen Extraktionsschema.
6. Grosse BPMN/XML-Dateien können über den Transformationspfad verarbeitet werden.
7. `Input/` bleibt nach erfolgreichem Lauf frei von verarbeiteten Prozessdateien.
8. Verarbeitete Prozessdateien werden nachvollziehbar archiviert.
9. Der Chat-Layer fragt Fakten über die IT-Landschaft nur nach vorheriger Graphabfrage ab.
10. Schwache Kandidaten werden im Graphen explizit als unbestätigt modelliert.
11. Ablehnungen für Anwendungsbezeichnungen werden in Neo4j persistiert.
12. Bestätigte und manuelle Anwendungslinks überleben Re-Importe.
13. OrgEinheiten werden case-insensitiv kanonisiert.
14. `ManualDecision` wird nicht in das freigegebene Query-Schema aufgenommen.
15. Undo einer manuellen Zuordnung entfernt nur die konkret von dieser Entscheidung erzeugten Effekte.
16. Ein Merge von `OrgEinheit` führt den Quellnamen als Alias des Zielobjekts weiter.
17. Ein Merge von `Prozess` kann Dubletten aus unterschiedlichen Quellen konsolidieren.
18. Beim Merge werden gleichartige Beziehungen nicht doppelt angelegt.
19. Der Merge ist nur nach Precheck und expliziter Benutzerbestätigung ausführbar.
20. ArchiMate-Import und -Export bleiben trotz Korrekturschicht funktionsfähig.
21. CMDB-Daten können als eine CSV-Datei pro Objektart importiert werden, mit Beziehungen als Multi-Value-Spalten.
22. Das CMDB-Mehrwert-Trennzeichen ist für gängige CMDB-Export-Formate konfigurierbar.
23. Das bisherige Zwei-Dateien-Format bleibt als Legacy-Pfad funktionsfähig.
24. Vor Prozessimport, expliziter CMDB-Synchronisation und Merge wird ein
    vollständigiger, validierter Snapshot erstellt.
25. Bei fehlgeschlagener Snapshot-Erstellung wird die auslösende Schreiboperation
    nicht ausgeführt und ein nachvollziehbarer Fehler angezeigt.
26. Ein Snapshot beinhaltet Fachgraph und interne Betriebsmetadaten, aber keine
    Zugangsdaten oder Secrets.
27. Die Wiederherstellung eines validierten Snapshots stellt den gespeicherten
    BRIDGR-Graphzustand wieder her und wird anhand der Objektzähler verifiziert.
28. Vor jeder Wiederherstellung wird ein Pre-Restore-Snapshot erzeugt; die
    Wiederherstellung erfordert eine explizite Benutzerbestätigung.

---

## 20. Getroffene Architekturentscheidungen

| Entscheidung | Gewählt | Verworfen | Begründung |
| --- | --- | --- | --- |
| Kanonischer Fachspeicher | Neo4j | Dateibasierte Wahrheitsquelle | Query-, Review- und Chat-Fähigkeit |
| Persistenz manueller Korrekturen | interner Entscheidungsgraph in Neo4j | globale Snapshots als Ersatz für Undo | selektive Rücknahme einzelner Entscheidungen bleibt schnell und fachlich präzise |
| Sicherung vor globalen Schreiboperationen | anwendungsverwaltete logische Graph-Snapshots | ausschliesslich manuelle Neo4j-Backups | Wiederherstellbarkeit ist direkt im BRIDGR-Workflow verfügbar, ohne Server-Administration vorauszusetzen |
| Sichtbarkeit der Korrekturschicht im Chat | verborgen | im Query-Schema freigeben | trennt Fachdialog von Betriebsmetadaten |
| Merge-Strategie | labelspezifisch (`OrgEinheit`, `Prozess`) | generischer Merge beliebiger Nodes | geringeres Risiko, fachlich kontrollierbar |
| Alias-Fortschreibung nach Merge | verpflichtend | Quellname verwerfen | verhindert Wiederauftreten derselben Dublette beim Re-Import |
| Deduplizierung beim Merge | vor jeder Kantenanlage prüfen | blindes Umhängen | verhindert, dass der Merge selbst neuen Müll erzeugt |
| Fachgraph vs. Entscheidungsgraph | getrennt | ein gemeinsamer überladener Graph | klarere Verantwortlichkeiten und sicherer Chat-Layer |
| Sprachliche Endredaktion im Chat | separater, faktenbewahrender LLM-Polish-Call nach der fachlichen Antwort | UI-Locale als Antwortsprache oder wortweise UI-Nachübersetzung freier Texte | Antwortsprache folgt der Nutzerfrage; geschützte Objektbezeichnungen bleiben stabil und die UI verfälscht keine LLM-Ausgabe |
| CMDB-Import-Format | eine CSV-Datei pro Objektart mit Beziehungsspalten | gemischte Entities-Datei + separate Relationsdatei | entspricht realen CMDB-Export-Strukturen (z. B. ServiceNow, Jira Asset Management); konfigurierbarer Mehrwert-Separator unterstützt gängige Formate |

---

## 21. Bekannte Einschränkungen

- Die beschriebene Entscheidungs- und Korrekturschicht ist architektonisch festgelegt,
  aber noch nicht vollständigig implementiert.
- `ManualDecision` wird aktuell ohne explizite `AFFECTS`-, `CREATED_ALIAS`- oder
  `SUPERSEDES`-Kanten gespeichert; die Zuordnung erfolgt derzeit payload-basiert.
- Merge-Workflows für `Anwendung` sind bewusst noch nicht Teil der ersten Ausbaustufe.
- Ein generischer Merge für weitere Labels ausser `OrgEinheit` und `Prozess` ist noch
  nicht Teil der aktuellen Ausbaustufe.
- UML-Diagramme im Repository können dem beschriebenen Stand voraus- oder hinterherlaufen
  und sind vor Aktualisierung nicht die kanonische Referenz.
- Das Legacy-CMDB-Format (gemischte Entities-Datei + separate Relationsdatei) bleibt
  funktionsfähig, ist aber für produktive CMDB-Anbindungen nicht das Zielformat.

---

BRIDGR | Architektur v0.29 | Stand August 2026

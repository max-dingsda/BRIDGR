# ArchiMate — Konzeptionelle Planung

> Status: **Konzept abgeschlossen** — alle Designfragen (F1–F5) entschieden.
> Nächster Schritt: Architekturkapitel in `Bridgr_Architektur_v21.md` schreiben,
> dann Implementierung starten.

---

## Motivation

ArchiMate ist der Standard-Modellierungsrahmen für Enterprise Architecture (The Open Group).
Da BRIDGR sich an Enterprise-Architekten richtet, sollte es mit der natürlichen
Informationsstruktur dieser Zielgruppe umgehen können. ArchiMate ist dafür der primäre Kandidat.

Testdaten können bei Bedarf über ein Modellierungstool (z.B. Archi) schnell erzeugt werden.

---

## Grundsätzliche Entscheidungen (getroffen)

| Thema | Entscheidung |
|---|---|
| Import-Modus | **Ergänzung**, kein Ersatz für BPMN/CMDB |
| Graphmodell-Erweiterung | **Nein** — striktes Mapping auf bestehende BRIDGR-Labels |
| Export-Scope v1 | **Valides ArchiMate-XML ohne Views/Viewpoints** |
| Views (Export) | Spätere Version, nicht v1 |
| Mapping-Konfiguration | **Benutzer-konfigurierbares Mapping** über neuen Tab |

---

## Architekturprinzip: Konfigurierbares Mapping — zwei Richtungen, unterschiedliche Kardinalität

Das Mapping zwischen BRIDGR-Labels und ArchiMate-Typen ist für Import und Export **bewusst asymmetrisch**.

---

### Element-Mapping

#### Import (ArchiMate → BRIDGR): strikt 1:1

Jeder ArchiMate-Typ wird genau einem BRIDGR-Label zugeordnet — oder gar keinem (= überspringen).
Kein ArchiMate-Typ kann zwei BRIDGR-Labels ergeben. Keine Interpretationsspielräume zur Laufzeit.

```
ArchiMate-Typ          → BRIDGR-Label
──────────────────────   ────────────
BusinessProcess        → Prozess
ApplicationComponent   → Anwendung
ApplicationInterface   → Schnittstelle
Node                   → Server
BusinessActor          → OrgEinheit
BusinessRole           → Rolle
BusinessFunction       → (nicht gemappt, wird übersprungen)
Capability             → (nicht gemappt, wird übersprungen)
DataObject             → (nicht gemappt, wird übersprungen)
...
```

Nicht-gemappte Typen werden beim Import übersprungen (Log-Eintrag mit Typ und Anzahl).
Der Nutzer entscheidet in der Konfiguration, welche ArchiMate-Typen er berücksichtigen will.

#### Export (BRIDGR → ArchiMate): m:1 erlaubt

Mehrere BRIDGR-Labels können auf denselben ArchiMate-Typ zeigen.
Das erlaubt bewusste Vereinfachungen: wer den Technology Layer nicht granular braucht,
kann z.B. `Schnittstelle` und `Server` beide als `Node` exportieren.

```
BRIDGR-Label    → ArchiMate-Typ (konfigurierbar)
────────────────  ────────────────────────────────
Prozess         → BusinessProcess
Anwendung       → ApplicationComponent
Schnittstelle   → ApplicationInterface   ← oder z.B. ApplicationComponent
Server          → Node
OrgEinheit      → BusinessActor
Rolle           → BusinessRole
```

Jedes BRIDGR-Label hat genau einen konfigurierten Export-Typ.
Mehrere Labels können denselben Typ haben — das ist explizit erlaubt.

---

### Beziehungs-Mapping: m:1 auf Import, kanonisch auf Export

**Entscheidung (F3): konfigurierbar, m:1 auf Import.**

Begründung: Organisationen modellieren dieselbe semantische Beziehung mit verschiedenen
ArchiMate-Typen. `TriggeringRelationship` und `FlowRelationship` bedeuten beide
"Prozess A löst Prozess B aus" — BRIDGR macht daraus in beiden Fällen `FOLGT_AUF`.
Welche ArchiMate-Typen akzeptiert werden, ist konfigurierbar.

#### Import (ArchiMate → BRIDGR): m:1

Für jedes (Quell-Label, Ziel-Label)-Paar ist eine Liste akzeptierter ArchiMate-Typen
konfiguriert. Alle Typen in der Liste erzeugen dieselbe BRIDGR-Relation.

```
(Anwendung → Prozess)     : DIENT          ←  [ServingRelationship, RealizationRelationship]
(Rolle → Prozess)         : BETEILIGT_AN   ←  [AssignmentRelationship]
(OrgEinheit → Rolle)      : KANN_EINNEHMEN ←  [AssignmentRelationship]
(Prozess → Prozess)       : FOLGT_AUF      ←  [TriggeringRelationship, FlowRelationship]
(Anwendung → Schnittstelle): USES_INTERFACE ←  [CompositionRelationship, AggregationRelationship]
(Anwendung → Server)      : RUNS_ON        ←  [RealizationRelationship, AssignmentRelationship]
(Schnittstelle → Server)  : RUNS_ON        ←  [RealizationRelationship]
(OrgEinheit → Anwendung)  : VERANTWORTET   ←  [AssociationRelationship, AssignmentRelationship]
(OrgEinheit → Schnittstelle): VERANTWORTET ←  [AssociationRelationship]
(OrgEinheit → Server)     : VERANTWORTET   ←  [AssociationRelationship]
```

Beziehungen, deren Typ nicht in der akzeptierten Liste steht, werden übersprungen (Log).

#### Export (BRIDGR → ArchiMate): kanonischer Typ

Jede BRIDGR-Relation hat einen konfigurierten kanonischen ArchiMate-Typ für den Export.

```
(Anwendung → Prozess)     : DIENT          →  ServingRelationship      (kanonisch)
(Prozess → Prozess)       : FOLGT_AUF      →  TriggeringRelationship   (kanonisch)
...
```

---

### Roundtrip-Konsistenz via Original-Typ-Properties

Sowohl Nodes als auch Relationships erhalten beim Import Properties,
die den originalen ArchiMate-Typ sichern. Beim Export haben diese Vorrang
über den jeweils konfigurierten kanonischen Typ.

#### Properties an Nodes

```
Neo4j-Node-Property   Bedeutung
──────────────────────────────────────────────────────────
archimate_id          interner Identifier aus dem ArchiMate-Modell
archimate_source      Dateiname der Quelldatei
archimate_type        originaler ArchiMate-Elementtyp beim Import
```

#### Properties an Relationships

Neo4j-Relationships können Properties tragen — dieselbe Logik gilt:

```
Neo4j-Relation-Property   Bedeutung
──────────────────────────────────────────────────────────
archimate_rel_type        originaler ArchiMate-Beziehungstyp beim Import
```

#### Roundtrip-Verhalten

```
Elemente:

  Import:  BusinessProcess (ArchiMate)
           → :Prozess {archimate_type: "BusinessProcess"} (Neo4j)
  Export:  :Prozess {archimate_type: "BusinessProcess"}
           → BusinessProcess  (Original, nicht konfigurierter Export-Typ)

  Ohne ArchiMate-Herkunft (aus BPMN):
  Export:  :Prozess {}
           → BusinessProcess  (konfigurierter Export-Typ greift)

Beziehungen:

  Import:  FlowRelationship (Prozess->Prozess, ArchiMate)
           → [:FOLGT_AUF {archimate_rel_type: "FlowRelationship"}] (Neo4j)
  Export:  [:FOLGT_AUF {archimate_rel_type: "FlowRelationship"}]
           → FlowRelationship  (Original, nicht kanonisches TriggeringRelationship)

  Ohne ArchiMate-Herkunft (aus BPMN):
  Export:  [:FOLGT_AUF {}]
           → TriggeringRelationship  (kanonischer Export-Typ greift)
```

Das ArchiMate-Modell bleibt nach Import -> BRIDGR -> Export typgetreu,
unabhaengig davon, wie die Konfiguration des Nutzers aussieht.

---

### Mapping-Wissen als externe Datei: `archimate_mapping.json`

**Entscheidung:** Das Mapping-Wissen lebt nicht im Code und nicht in `config.json`,
sondern in einer eigenen Datei `archimate_mapping.json` (im Projekt-Root, neben `config.json`).

**Begründung:** Analogie zum bestehenden "Prompts over code"-Prinzip in BRIDGR.
Wissen, das sich unabhängig von Code ändert, gehört nicht in den Code.
Das ArchiMate-Mapping ist Organisations-Wissen, kein Laufzeit-Konfigurationswert.

| Datei | Zuständigkeit |
|---|---|
| `config.json` | Laufzeit-Konfiguration (DB, LLM, Dateinamen) |
| `knowledge_base/kb.json` | Kuratiertes Domain-Wissen (Aliases, Bestätigungen) |
| `archimate_mapping.json` | ArchiMate-Mapping-Konfiguration (Elementtypen, Beziehungstypen) |

**Beide Services lesen aus derselben Datei — kein dupliziertes Wissen:**

```
archimate_mapping.json
    │
    ├── services/archimate_import_service.py
    └── services/archimate_export_service.py
```

Der Mapping-Tab im UI liest und schreibt `archimate_mapping.json` direkt.

#### Dateistruktur `archimate_mapping.json`

```json
{
  "language_preference": ["de", "german", "en", "english"],
  "fuzzy_match_threshold": 0.85,
  "elements": {
    "import": {
      "BusinessProcess":      "Prozess",
      "ApplicationComponent": "Anwendung",
      "ApplicationInterface": "Schnittstelle",
      "Node":                 "Server",
      "BusinessActor":        "OrgEinheit",
      "BusinessRole":         "Rolle"
    },
    "export": {
      "Prozess":        "BusinessProcess",
      "Anwendung":      "ApplicationComponent",
      "Schnittstelle":  "ApplicationInterface",
      "Server":         "Node",
      "OrgEinheit":     "BusinessActor",
      "Rolle":          "BusinessRole"
    }
  },
  "relationships": {
    "import": {
      "Anwendung->Prozess":       ["ServingRelationship", "RealizationRelationship"],
      "Rolle->Prozess":           ["AssignmentRelationship"],
      "OrgEinheit->Rolle":        ["AssignmentRelationship"],
      "Prozess->Prozess":         ["TriggeringRelationship", "FlowRelationship"],
      "Anwendung->Schnittstelle": ["CompositionRelationship", "AggregationRelationship"],
      "Anwendung->Server":        ["RealizationRelationship", "AssignmentRelationship"],
      "Schnittstelle->Server":    ["RealizationRelationship"],
      "OrgEinheit->Anwendung":    ["AssociationRelationship", "AssignmentRelationship"],
      "OrgEinheit->Schnittstelle":["AssociationRelationship"],
      "OrgEinheit->Server":       ["AssociationRelationship"]
    },
    "export": {
      "Anwendung->Prozess":       "ServingRelationship",
      "Rolle->Prozess":           "AssignmentRelationship",
      "OrgEinheit->Rolle":        "AssignmentRelationship",
      "Prozess->Prozess":         "TriggeringRelationship",
      "Anwendung->Schnittstelle": "CompositionRelationship",
      "Anwendung->Server":        "RealizationRelationship",
      "Schnittstelle->Server":    "RealizationRelationship",
      "OrgEinheit->Anwendung":    "AssociationRelationship",
      "OrgEinheit->Schnittstelle":"AssociationRelationship",
      "OrgEinheit->Server":       "AssociationRelationship"
    }
  }
}
```

Die Datei wird beim ersten Start mit Standard-ArchiMate-Defaults angelegt.
Der Nutzer überschreibt nur, was von seiner Organisation abweicht.
Nicht-gemappte ArchiMate-Typen (fehlende Einträge im `import`-Block) werden
beim Import übersprungen und geloggt.

---

## Das zentrale technische Problem: Identity Resolution

ArchiMate-Elemente haben **interne UUIDs** (das `identifier`-Attribut im XML), aber diese
sind nur innerhalb eines Modells gültig — es gibt keine systemübergreifende Identität.

### Das Problem konkret

```
BPMN-Prozess:       name="Posteingang", process_id="proc_001_v3"
ArchiMate-Element:  name="Posteingang", identifier="id-abc123" (nur intern)
CMDB-Anwendung:     name="SAP SD", cmdb_id="APP-4711"
ArchiMate-Element:  name="SAP SD", identifier="id-def456" (nur intern)
```

Beim ArchiMate-Import muss BRIDGR entscheiden:
- Ist `"Posteingang"` (ArchiMate) dasselbe wie `"Posteingang"` (BPMN)?
- Ist `"SAP SD"` (ArchiMate) dieselbe Anwendung wie `"SAP SD"` (CMDB)?

### Lösungsansatz

Ähnlich wie bei bestehender CMDB-Erkennung: **name-based fuzzy matching** mit Konfidenz.

```
archimate_id bekannt (Re-Import)  → direkter Lookup auf archimate_id-Property (deterministisch)
Exakter Namensabgleich            → MERGE in Neo4j (anreichern, nicht duplizieren)
Fuzzy Match (hohe Konfidenz)      → Kandidat, manuell bestätigen (wie CMDB-Kandidaten)
Kein Match                        → neuer Knoten
```

ArchiMate-Import integriert sich in den **Review-Workflow** für unklare Matches —
analog zur bestehenden Behandlung von CMDB-Ownership-Kandidaten.

### Primäre Identität nach Fuzzy-Match-Bestätigung

Die **BRIDGR-native ID bleibt primär** (`process_id`, `cmdb_id` etc.).
`archimate_id` wird als zusätzliche Property am Knoten gespeichert.

Lookup-Reihenfolge bei jedem ArchiMate-Import:
1. `archimate_id`-Property vorhanden → exakter Treffer, kein Matching nötig
2. Exakter Namensabgleich → MERGE
3. Fuzzy Match → Kandidat
4. Kein Match → neuer Knoten

Das verhindert Duplikate bei wiederholtem Import und erhält die bestehende
Identitätslogik ohne Umbau.

### Übersprungene Beziehungen bei unaufgelösten Endpoints

Wenn ein Endpoint zum Importzeitpunkt noch unaufgelöst ist (pending Review),
wird die Beziehung übersprungen und im Import-Log festgehalten.

**v1-Policy:** Nach Bestätigung eines Kandidaten im Review-Tab werden betroffene
Beziehungen **nicht** automatisch nachgezogen. Der Nutzer muss die ArchiMate-Datei
erneut importieren, um übersprungene Beziehungen zu übernehmen.

Diese Einschränkung wird im Import-Log und in der UI sichtbar kommuniziert.
Ein automatischer Nachzug-Mechanismus ist für eine spätere Version vorgesehen.

### Properties an importierten Knoten

```
Neo4j-Node-Property   Bedeutung
──────────────────────────────────────────────────────────
archimate_id          interner Identifier aus dem ArchiMate-Modell
archimate_source      Dateiname der Quelldatei
archimate_type        originaler ArchiMate-Elementtyp beim Import
```

Alle drei Properties bleiben erhalten, auch wenn der Knoten mit einem
bestehenden BRIDGR-Knoten gemergt wird.

### Mehrsprachige Namen

ArchiMate Exchange Format erlaubt mehrere `<name>`-Elemente mit `xml:lang`-Attribut:

```xml
<element identifier="id-1" xsi:type="BusinessProcess">
  <name xml:lang="de">Posteingang</name>
  <name xml:lang="en">Incoming Mail</name>
</element>
```

**Sprachauswahl-Logik:**

Der Parser wählt den Namen nach einer konfigurierten Präferenzliste.
Default in `archimate_mapping.json`:

```json
"language_preference": ["de", "german", "en", "english"]
```

- Bevorzugte Sprache: `"de"` oder `"german"` (beide gelten als Deutsch — verschiedene
  Tools nutzen ISO-Codes oder Vollnamen)
- Fallback: nächste Sprache in der Liste
- Letzter Fallback: erstes verfügbares `<name>`-Element

Ohne `xml:lang`-Attribut wird der Name direkt übernommen.

---

## Import-Pipeline (Entwurf)

```
Input/*.archimate  oder  Input/*.xml (ArchiMate Exchange Format)
  │
  ▼
ArchiMate-Parser
  Liest Elemente + Beziehungen aus dem XML
  Wendet Typ-Mapping an (aus archimate_mapping.json)
  Extrahiert: {archimate_id, archimate_type, name, bridgr_label}
  │
  ▼
Identity Resolution
  1. archimate_id bekannt? → direkter Lookup (deterministisch)
  2. Exakter Namensabgleich → MERGE, archimate_id ergänzen
  3. Fuzzy Match → Kandidat in Review-Queue
  4. Kein Match → neuer Knoten
  Namenswahl: language_preference aus archimate_mapping.json
  │
  ▼
Beziehungs-Import
  Für jede ArchiMate-Beziehung:
    Beide Endpoints aufgelöst? → BRIDGR-Relation erstellen
    Mindestens ein Endpoint unaufgelöst? → überspringen / loggen
  │
  ▼
Neo4j-Writer
  MERGE auf name + label (exakt)
  SET archimate_id, archimate_source
```

**Entscheidung F1:** Eigene Services — `archimate_import_service.py` und
`archimate_export_service.py`. Beide lesen `archimate_mapping.json` als gemeinsame
Wissensquelle. Kein Mapping-Wissen im Code.

---

## Export-Pipeline (Entwurf)

**Export-Scope: immer vollständiger Graph.**
Solange keine Views/Viewpoints definierbar sind, gibt es keinen sinnvollen Teilexport.
Der Export bildet den gesamten BRIDGR-Graphen ab — unabhängig von der Herkunft der Knoten
(BPMN, CMDB oder ArchiMate). Ein selektiver Export ist für eine spätere Version vorgesehen.

```
Neo4j (alle Knoten + alle Relationen lesen)
  │
  ▼
Mapping anwenden (BRIDGR-Label → ArchiMate-Typ)
  archimate_type-Property vorhanden? → Original-Typ verwenden (Roundtrip)
  Sonst: konfigurierter Export-Typ aus archimate_mapping.json
  Knoten ohne Export-Mapping werden übersprungen (kein Generic-Fallback)
  │
  ▼
ArchiMate-XML-Generator
  Erstellt valides ArchiMate Exchange Format 3.x
  Kein <views>/<viewpoints>-Block (v1)
  <elements> + <relationships> + <organizations>
  │
  ▼
Output/archimate_export_<timestamp>.xml
```

**Entscheidung F2:** Export-Button im ArchiMate-Tab (bisheriger "Mapping-Tab").
Der Tab wird zum zentralen ArchiMate-Arbeitsbereich: Mapping konfigurieren → importieren → exportieren.
**Tab-Name: "EA-Modell"** (neutral, nicht tool-spezifisch; kann später ohne großen Aufwand geändert werden).

---

## ArchiMate-Tab: UI-Konzept

Der Tab ist der zentrale Arbeitsbereich für alles ArchiMate in BRIDGR.
Tab-Name: noch offen ("ArchiMate", "EA-Modell", o.ä.).

### Bereich 1 — Mapping konfigurieren

Zwei Untersektionen (Elemente + Beziehungen), je als editierbare Tabelle.

**Elemente:**
```
                Import (ArchiMate → BRIDGR)         Export (BRIDGR → ArchiMate)
BRIDGR-Label    Akzeptierter AM-Typ                 Kanonischer AM-Typ
──────────────  ─────────────────────────────────   ────────────────────────
Prozess         [BusinessProcess          ▼]        [BusinessProcess    ▼]
Anwendung       [ApplicationComponent     ▼]        [ApplicationComponent ▼]
Schnittstelle   [ApplicationInterface     ▼]        [ApplicationInterface ▼]
Server          [Node                     ▼]        [Node              ▼]
OrgEinheit      [BusinessActor            ▼]        [BusinessActor     ▼]
Rolle           [BusinessRole             ▼]        [BusinessRole      ▼]
```

**Beziehungen:**
```
Label-Paar               Akzeptierte AM-Typen (Import)              Kanonisch (Export)
──────────────────────   ─────────────────────────────────────────  ──────────────────
Anwendung → Prozess      [ServingRelationship ✓] [Realization ✓] …  [ServingRelationship ▼]
Prozess → Prozess        [TriggeringRelationship ✓] [Flow ✓] …      [TriggeringRelationship ▼]
...
```

[ Mapping speichern ]

### Bereich 2 — Import & Export

```
[ ArchiMate-Datei importieren ]      [ Graphen als ArchiMate exportieren ]

Letzter Import: archimate_model_v3.xml (2026-05-12)
Nicht-gemappte Typen: BusinessFunction (14), DataObject (3)
Letzter Export: archimate_export_20260512_143200.xml
```

---

## Dateiformate

| Format | Unterstützung v1 |
|---|---|
| ArchiMate Exchange Format 3.x (XML) | **Ja** — primäres Format |
| Archi `.archimate` (proprietäres XML) | Später — anderes Namespace-Schema |

Der Exchange-Format-Standard ist werkzeugübergreifend und der richtige Ausgangspunkt.
Archi kann Exchange-Format importieren und exportieren.

### Beispiel ArchiMate Exchange Format (vereinfacht)

```xml
<?xml version="1.0" encoding="UTF-8"?>
<model xmlns="http://www.opengroup.org/xsd/archimate/3.0/"
       xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
       identifier="id-model-1" version="3.0">
  <name xml:lang="de">Unternehmensarchitektur</name>
  <elements>
    <element identifier="id-1" xsi:type="BusinessProcess">
      <name xml:lang="de">Posteingang</name>
    </element>
    <element identifier="id-2" xsi:type="ApplicationComponent">
      <name xml:lang="de">SAP SD</name>
    </element>
  </elements>
  <relationships>
    <relationship identifier="id-3" xsi:type="ServingRelationship"
                  source="id-2" target="id-1"/>
  </relationships>
</model>
```

---

## Entscheidungen

| ID | Frage | Entscheidung |
|---|---|---|
| F1 | Eigener Service oder bestehende Import-Pipeline? | **Eigene Services:** `archimate_import_service.py` + `archimate_export_service.py`, gemeinsame Wissensquelle `archimate_mapping.json` |
| F2 | Export-Trigger UI-Platzierung | **ArchiMate-Tab** (erweiterter Mapping-Tab); Tab-Name noch offen |
| F3 | Beziehungs-Mapping: konfigurierbar oder fest? | **Konfigurierbar, m:1 auf Import** (Liste akzeptierter AM-Typen pro Label-Paar); **1:1 auf Export** (kanonischer Typ); `archimate_rel_type` für Roundtrip |
| F4 | Fuzzy-Match-Schwellwert für Identity Resolution | **Initialer Wert = CMDB-Schwellwert**, separat konfigurierbar in `archimate_mapping.json` |
| F5 | v1-Scope | **Reguläres Feature, kein Flag.** ArchiMate-Support ist Voraussetzung vor Public Release. v1-Scope-Definition in `CONTEXT.md` muss mit `Bridgr_Architektur_v21.md` aktualisiert werden. |

---

## Nächste Schritte

### Architektur finalisieren
1. Architekturkapitel in `Bridgr_Architektur_v21.md` schreiben
2. Fuzzy-Match-Schwellwert aus bestehendem CMDB-Matching ablesen und in `archimate_mapping.json`-Default übernehmen

### Implementierungsreihenfolge (Entwurf)
1. `archimate_mapping.json` — Datei mit Defaults anlegen
2. `services/archimate_import_service.py` — XML-Parser, Typ-Mapping, Identity Resolution, Neo4j-Schreiben
3. `services/archimate_export_service.py` — Neo4j lesen, XML generieren
4. `ui/archimate_tab.py` — Mapping-Editor + Import/Export-Aktionen
5. `app.py` — neuen Tab einbinden
6. Tests: Parser, Mapping, Identity Resolution, Roundtrip (import → export → compare)

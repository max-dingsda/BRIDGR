# BRIDGR — Test Audit (External Review)
**Stand:** 2026-05-29 | Reviewer: Claude Sonnet 4.6

---

## Ausgangslage

Die bestehenden Tests wurden vollständig von Codex geschrieben — also vom selben Agenten, der auch den Produktionscode erstellt hat. Der vorliegende Audit analysiert die Testabdeckung unabhängig davon aus der Perspektive der Architekturspezifikation (`Bridgr_Architektur_v18.md`).

Ausgangszustand: **170 Tests**, alle grün.

---

## Methodik

1. Architekturspezifikation (v18) und CONTEXT.md gelesen, um fachliche Anforderungen zu verstehen.
2. Alle Quelldateien in `skills/`, `cmdb.py`, `graph_schema.py`, `neo4j_utils.py`, `pipeline.py` und `services/` gesichtet.
3. Alle bestehenden Tests gesichtet und mit dem Anforderungskatalog aus der Spezifikation abgeglichen.
4. Lücken nach fachlichem Risiko priorisiert.

---

## Gefundene Lücken

### 1. `skills/review.py::collect_review_items` — komplett ungetestet

**Risiko: Hoch.** Die Funktion entscheidet, was im Review landet und was in den Graph geschrieben wird.  
Das ist ein zentrales Qualitäts-Gate der Pipeline. Die Spezifikation (Abschnitt 8) fordert explizit:
- Schwache Kandidaten bleiben reviewbar.
- Abgelehnte Links erscheinen NICHT im Review.
- Starke Links OHNE CMDB-ID erscheinen im Review.

Obwohl `collect_review_items` in `pipeline.py` aufgerufen wird, haben die Pipeline-Tests diese Funktion nur implizit mitgetestet — ohne ihre Grenzfälle abzudecken.

**Erstellt:** `tests/test_review.py` (7 Tests)

---

### 2. CMDB-Validierung — fehlende Fehlerpfade

**Risiko: Mittel.** Die CMDB-Normalisierung in `cmdb.py` enthält explizite Fehlerbehandlung für ungültige Eingaben, die durch die bestehenden Tests nicht erreicht wurde.

Konkrete Lücken:
- Unbekannter Entity-Typ (z. B. `"database"`) → `CmdbLoadError`
- Unbekannter Server-Typ (z. B. `"container"`) → `CmdbLoadError`
- Zeile ohne Entity-ID → `CmdbLoadError`
- Zeile ohne Entity-Name → `CmdbLoadError`
- `load_cmdb_relation_rows`: Happy Path, fehlende Datei, fehlende Pflichtspalten — komplett ungetestet
- `normalize_cmdb_relations` mit unvollständiger Zeile → `CmdbLoadError`
- `build_cmdb_option_labels` und `find_cmdb_row_by_label` — komplett ungetestet

Die Spezifikation (Abschnitt 5) definiert `physical` und `virtual` als einzige gültige Server-Typen. Ein Test dafür fehlte.

**Ergänzt:** `tests/test_cmdb.py` (+12 Tests)

---

### 3. Graph-Schema-Validierung — fehlende Richtungs- und Label-Tests

**Risiko: Mittel.** `validate_query_schema` in `graph_schema.py` wird via `validate_read_only_cypher` aufgerufen und schützt den Query-Layer vor illegal generierten Cypher-Queries. Die bestehenden Tests deckten bereits Beziehungstypen ab, aber nicht:

- Unbekanntes Node-Label → `QueryValidationError`
- Falsche Richtung für `DIENT` (die Spezifikation definiert `Anwendung → Prozess`, nicht umgekehrt)
- Falsche Richtung für `VERANTWORTET` (`OrgEinheit → *`, nicht umgekehrt)
- Ungerichtetes Beziehungsmuster
- Unbekannte Property auf bekanntem Label (z. B. `p.beschreibung` für `Prozess`)

Hintergrund: Mehrere Findings aus `Specs/Findings.txt` (Nr. 24, 27, 28) belegen, dass lokale LLM-Modelle wiederholt ungültige Cypher erzeugen. Die Validierung ist daher ein kritischer Schutzwall.

**Ergänzt:** `tests/test_neo4j_utils.py` (+7 Tests)

---

### 4. `skills/graph_writer.py` — fehlende Zweige

**Risiko: Mittel.** Der Graph Writer hat mehrere Codepfade, die von den bestehenden Tests nicht erreicht wurden:

- **Vorhandener Prozessknoten (kein Placeholder):** Wenn `_upsert_process_node` einen bereits existierenden Prozess findet (Branch `if process_rows`), muss er nur updaten statt neu anlegen. Dieser Zweig war ungetestet.
- **Rollen-Knoten (`Rolle`/`BETEILIGT_AN`):** `write_payload` schreibt Rollen in den Graphen, aber kein Test prüfte, ob `BETEILIGT_AN`-Edges erzeugt werden.
- **Mehrere OrgEinheiten je Prozess:** Die Architektur erlaubt mehrere `VERANTWORTET`-Beziehungen von verschiedenen `OrgEinheit`-Knoten zu einem Prozess — ungetestet.
- **CMDB-Entity vom Typ `process`:** `_upsert_cmdb_entity` hat einen Branch für `entity_type == "process"`, der `Prozess`-Knoten in Neo4j schreibt. Laut Spezifikation Abschnitt 5 ist das ein vorgesehener Typ — ungetestet.

**Ergänzt:** `tests/test_graph_writer.py` (+4 Tests)

---

### 5. `skills/identity.py` — Edge Cases

**Risiko: Niedrig.** `extract_bpmn_process_ids` hatte nur einen Happy-Path-Test:

- Leere BPMN ohne `<process>`-Elemente → kein Absturz, leere Liste
- Malformiertes XML → `xml.etree.ElementTree.ParseError`

Diese Pfade sind für die stabile `prozess_id`-Ableitung relevant (Findings Nr. 15).

**Ergänzt:** `tests/test_identity.py` (+2 Tests)

---

## Zusammenfassung

| Datei | Neue Tests | Kern-Grund |
|---|---|---|
| `tests/test_review.py` (neu) | 7 | `collect_review_items` komplett ungetestet |
| `tests/test_cmdb.py` | 12 | Fehlerpfade + `load_cmdb_relation_rows` + Hilfsfunktionen |
| `tests/test_neo4j_utils.py` | 7 | Schema-Richtungs- und Label-Validierung |
| `tests/test_graph_writer.py` | 4 | Fehlende Branches: Rollen, Multi-OrgUnit, Existierender Prozess, CMDB-Prozesstyp |
| `tests/test_identity.py` | 2 | Leere Eingabe + Malformed XML |
| **Gesamt** | **+31** | |

Endstand: **201 Tests**, alle grün.

---

## Beobachtungen ohne neue Tests

Folgende Punkte wurden identifiziert, aber bewusst NICHT als neue Tests umgesetzt, weil sie eher architektonische oder manuelle Verifikationsschritte erfordern:

- **`_resolve_duplicate_placeholders`:** Die Methode wird nur indirekt über `_upsert_process_node` aufgerufen wenn ein existierender Prozess UND ein namensgleicher Placeholder vorhanden ist. Ein Unit-Test würde zwei koordinierte Mock-Antworten erfordern. Die Logik ist komplex genug für einen eigenen Test, der den Aufwand rechtfertigt — wurde als Folgeaufgabe markiert, nicht sofort umgesetzt.
- **`pipeline.py` — CMDB-Datei wird bei Archivierung nicht mitbewegt:** Spec Abschnitt 3.2 fordert das explizit. Der bestehende Test in `test_import_service.py` prüft nur Prozessdateien. Dieser Aspekt wäre ein Integrationstest auf Ebene des Import-Workflows, nicht ein Unit-Test.
- **Separate Read-only DB-Identität für den Query-Layer:** Laut `README.md` noch nicht implementiert — kein Test sinnvoll solange das Feature fehlt.

---

## Hintergrund: Warum externe Test-Reviews wichtig sind

Wenn Entwickler ihre eigenen Tests schreiben, entstehen systematische blinde Flecken: Getestet wird tendenziell was man implementiert hat, nicht was die Spezifikation fordert. Insbesondere Fehlerpfade, Grenzfälle und Invarianten die "selbstverständlich" erscheinen, bleiben oft ungetestet.

In BRIDGR war der auffälligste Fall `collect_review_items` — die Funktion entscheidet über das Herzstück der Pipeline (was landet im Review vs. im Graph), hatte aber null Tests. Die CMDB-Validierungspfade und die Cypher-Richtungsvalidierung sind weitere Beispiele: der Code war korrekt, aber die Tests bewiesen das nicht.

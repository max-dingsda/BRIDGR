# Technisches Review — BRIDGR Architektur und Code-Validierung
**Erstellt durch Gemini (Antigravity) | Juni 2026**

---

## 1. Einleitung und Zielsetzung
Dieses technische Review bewertet die Übereinstimmung der architektonischen Aussagen aus [README.md](file:///f:/workspace/BRIDGR/README.md) und [Bridgr_Architektur_v28.md](file:///f:/workspace/BRIDGR/Specs/Bridgr_Architektur_v28.md) mit der tatsächlichen Umsetzung im Quellcode. 

Ziel ist es, "schöngefärbte" (sugarcoated) Darstellungen aufzudecken, bei denen die Dokumentation eine Zielarchitektur oder ein Verhalten beschreibt, das im Code entweder fehlerhaft, unvollständig oder abweichend implementiert ist.

---

## 2. Kritische Abweichungen und Gaps (Soll vs. Ist)

### Gap 1: Die angebliche Ablösung von `kb.json` (Sugarcoating & Redundanz)
* **Aussage der Dokumentation (Architektur v28, Abs. 2.2):** 
  > *"`knowledge_base/kb.json` bleibt aus Kompatibilitätsgründen im Projekt vorhanden, ist aber kein aktiver Architektur-Speicher für neue Entscheidungen."* 
  > (Ähnlich in README: *"...wird nicht mehr aktiv beschrieben oder gelesen."*)
* **Die Realität im Code:** 
  Das Gegenteil ist der Fall. Die Datei `kb.json` wird in `services/organization_service.py` und `services/review_service.py` an Dutzenden Stellen aktiv als primärer Datenspeicher für manuelle Entscheidungen verwendet und beschrieben. Funktionen wie `add_org_unit_entry`, `accept_org_candidate` oder `reject_org_candidate` rufen alle `save_knowledge_base` auf. Auch die Liste der offenen Organisationskandidaten im UI wird direkt aus `kb.json` (mittels `load_knowledge_base`) geladen.
* **Fazit:** Die Dokumentation schönt den Fortschritt bei der Migration hin zu einer reinen Neo4j-Datenhaltung. Das System ist nach wie vor in einer Hybrid-Phase, in der Geschäftslogik stark von `kb.json` abhängt.

---

### Gap 2: Pipeline-Bug bei der Kandidaten-Persistenz (Funktionaler Fehler)
* **Aussage der Dokumentation (Architektur v28, Abs. 7.1):** 
  Der Import-Lauf verarbeitet Dokumente, erzeugt Review-Artefakte und pflegt die Wissensbasis.
* **Die Realität im Code (`processing/pipeline.py`):** 
  In `run_pipeline` wird die Wissensbasis geladen (`knowledge_base = load_knowledge_base()`) und bei der Verarbeitung jedes Dokuments über `update_organization_knowledge` im Arbeitsspeicher aktualisiert (neue Organisationskandidaten werden hinzugefügt). 
  **Aber:** Am Ende von `run_pipeline` wird `save_knowledge_base(knowledge_base)` **niemals aufgerufen**! 
* **Konsequenz:** Neu extrahierte Kandidaten aus importierten Dokumenten gehen nach Beendigung des Skripts im Dateisystem verloren, sofern sie nicht manuell über andere UI-Aktionen getriggert und gespeichert werden. Das ist ein schwerer Fehler im Datenfluss der Import-Pipeline.

---

### Gap 3: Datenverlust beim Prozess-Merge (Schwere Architekturverletzung)
* **Aussage der Dokumentation (Architektur v28, Abs. 11.8):** 
  Beim Konsolidieren/Mergen von Prozessen sollen alle Fachbeziehungen berücksichtigt werden:
  > *"...eingehend: `DIENT`, `KÖNNTE_DIENEN`, `BETEILIGT_AN`, `VERANTWORTET`, `REALISIERT`, `UNTERSTUETZT`, `BENOETIGT`, `VERARBEITET`, `BETRIFFT`, `BEEINFLUSST`; ausgehend: `FOLGT_AUF`, `UNTERSTUETZT`, `BENOETIGT`, `VERARBEITET`."*
* **Die Realität im Code (`services/merge_service.py` -> `_merge_process_relationships`):** 
  Die Implementierung kopiert nur eine fest verdrahtete Untermenge an Beziehungen (`DIENT`, `KÖNNTE_DIENEN`, `BETEILIGT_AN`, `VERANTWORTET`, `FOLGT_AUF` und eingehende `Alias`-Kanten).
  Alle Beziehungen der ArchiMate-Motivationsebene (`REALISIERT`, `UNTERSTUETZT`, `BENOETIGT`, `VERARBEITET`, `BETRIFFT`, `BEEINFLUSST`) werden beim Löschen des Quellknotens **komplett verworfen**.
* **Konsequenz:** Wenn ein Benutzer zwei Prozesse konsolidiert, die aus einem ArchiMate-Import stammen, verliert der resultierende Prozess alle Verknüpfungen zu Zielen, Anforderungen, Risiken oder Ressourcen. Das steht im direkten Widerspruch zur Spezifikation.

---

### Gap 4: Das Pseudo-Graphmodell der `ManualDecision` (Abweichende Implementierung)
* **Aussage der Dokumentation (Architektur v28, Abs. 10.4):** 
  Es existiert ein Entscheidungsgraph mit Mustern wie `(:ManualDecision)-[:AFFECTS]->(:Prozess)` oder `[:CREATED_ALIAS]`.
* **Die Realität im Code:** 
  Diese Kanten existieren nicht. In `services/decision_service.py` wird beim Aufruf von `create_manual_decision` lediglich ein einzelner, isolierter Knoten `(:ManualDecision)` mit Attributen erstellt. Die betroffenen Fachobjekte und IDs werden als JSON-String in das Feld `payload_json` gepackt.
  Die Rücknahme (`revert_manual_decision` in `services/correction_service.py`) traversiert keine Graph-Kanten, sondern parst dieses JSON im Speicher und setzt ad-hoc generierte Cypher-Statements ab.
* **Fazit:** Die Dokumentation zeichnet das Bild eines eleganten Graph-Auditing-Modells. Die tatsächliche Implementierung weicht davon ab und verlässt sich auf textbasierte JSON-Payloads innerhalb von Nodes.

---

### Gap 5: Standardkonfiguration vs. Zielbild (Legacy-Standard)
* **Aussage der Dokumentation (Architektur v28, Abs. 7.5.5):** 
  Das neue Typ-Datei-Format (eine CSV pro Objekttyp) ist das produktive Standard-CMDB-Format. Das Legacy-Format (zwei gemischte Dateien) ist ein reines "Entwicklungsformat".
* **Die Realität im Code (`config.json`):** 
  Die Standardkonfiguration wird mit `"cmdb_type_files": {}` ausgeliefert. Dadurch ist standardmäßig die Legacy-Logik aktiv, die auf die Dateien `cmdb_entities.csv` und `cmdb_relations.csv` zugreift.
* **Fazit:** Das System wird standardmäßig im Legacy-Modus betrieben. Der Anwender muss das produktive Format erst explizit selbst konfigurieren.

---

## 3. Positive Befunde (Übereinstimmung mit der Architektur)

Trotz der Gaps gibt es wesentliche Bereiche, die exakt und robust nach Spezifikation umgesetzt wurden:

* **Sicherheit im Chat-Layer (Read-Only):**
  Die Sperrung schreibender Token (`CREATE`, `MERGE`, `DELETE`, etc.) sowie die allowlist-basierte Schema-Validierung in `core/neo4j_utils.py` und `core/graph_schema.py` sind vorbildlich implementiert. Das LLM kann unter keinen Umständen manipulative Queries gegen die Datenbank absetzen.
* **Verstecken der Betriebsknoten:**
  Der Knotentyp `ManualDecision` und `Ablehnung` ist konsistent vom Query-Schema ausgeschlossen. Das LLM "weiß" nichts von deren Existenz und bezieht sie nicht in Antworten ein.
* **Undo-Mechanismus:**
  Abgesehen von der JSON-Payload-Hürde funktioniert die Rücknahme-Logik von manuellen Zuordnungen und Merges zuverlässig und konsistent (wurde erfolgreich durch Unit-Tests in `tests/test_correction_service.py` abgedeckt).
* **Alias-Projektion:**
  Die automatische Generierung von `(:Alias)-[:KANN_MEINEN]->(...)` bei Bestätigungen und Merges ist implementiert und unterstützt die deterministische Erkennung von Synonymen bei Folge-Imports und im Chat-Lookup.

---

## 4. Technische Empfehlungen
1. **Pipeline-Fix:** In `processing/pipeline.py` am Ende des Imports unbedingt `save_knowledge_base(knowledge_base)` aufrufen, um Datenverlust bei Organisationskandidaten zu verhindern.
2. **Merge-Korrektur:** In `services/merge_service.py` müssen die restlichen ArchiMate-Beziehungen (z. B. `REALISIERT`, `UNTERSTUETZT`, `BENOETIGT`, `VERARBEITET`, `BETRIFFT`, `BEEINFLUSST`) in die Kantenübertragung des Prozess-Merges einbezogen werden.
3. **Dokumentation anpassen:** Entweder das `kb.json`-Einstellungsszenario im Code finalisieren (Migration zu reiner DB-Haltung abschließen) oder die Dokumentation dahingehend korrigieren, dass `kb.json` ein aktiver Systembestandteil ist.

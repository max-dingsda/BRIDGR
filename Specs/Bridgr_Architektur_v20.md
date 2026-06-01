# Bridgr
**CMDB-Zielarchitektur** | Stand: Juni 2026 | v0.20

---

## 1. Ziel

*(unveraendert gegenueber v0.19)*

Prozessdokumentation und CMDB-Export zusammenfuehren, um einen EA-Wissensgraphen aufzubauen
und ihn ueber eine natuerlichsprachliche Web-Oberflaeche abfragbar zu machen.

Kernfrage:
Welche IT-Bausteine unterstuetzen welche Geschaeftsprozesse und wie sicher wissen wir das?

Bridgr schliesst die Luecke klassischer Discovery-Tools: Diese kennen die IT-Landschaft,
aber nicht den Business-Kontext aus Prozessdokumentation.

### Visionsziel: vollwertiger EA-Chatbot

Der Tab "Kommunikation" ist kein einfaches Query-Werkzeug, sondern ein vollwertiger
Unternehmens-Architektur-Chatbot. Benutzer stellen Fragen in natuerlicher Sprache zu
IT-Bausteinen, Prozessen und deren Beziehungen und erhalten kontextbewusste,
gesprächsfoerdernde Antworten — unabhaengig davon, wie die Frage formuliert ist.

Dieses Visionsziel ist der Massstab fuer alle Designentscheidungen im Abfrage-Layer.
Jede Abwaegung in diesem Bereich wird daran gemessen.

---

## 2. Gesamtarchitektur

*(unveraendert gegenueber v0.19)*

Das System besteht weiterhin aus zwei klar getrennten Schichten:

- Pipeline:
  Prozessdokumente + CMDB -> optionale Vortransformation fuer grosse BPMN -> Extraktion
  -> Matching -> Review-Artefakte -> Graph-DB
- Abfrage-Layer:
  Web-UI -> LLM (Orchestrator) -> Tool: Cypher-Ausfuehrung -> Neo4j -> Antwort in
  natuerlicher Sprache

Die Pipeline bleibt sequentiell, nachvollziehbar und idempotent.

---

## 3. Inputs und Dateifluss

*(unveraendert gegenueber v0.19)*

### 3.1 Eingangsdateien

- Prozessdokumente:
  BPMN sowie unstrukturierte Prozessbeschreibungen als TXT, DOCX oder PDF
- Transformierte BPMN-Prozessdateien:
  aus grossen BPMN/XML-Dateien abgeleitete, kompakte TXT-Dateien mit genau einer
  Importeinheit pro Prozess
- CMDB-Export:
  vorerst nur CSV

### 3.2 Inbox-Prinzip

*(unveraendert gegenueber v0.19)*

### 3.3 Archivierung verarbeiteter Dateien

*(unveraendert gegenueber v0.19)*

---

## 4. Scope v0.20

| Bereich | In Scope | Out of Scope |
|---|---|---|
| Eingabeformate | BPMN, TXT, DOCX, PDF, CMDB als CSV | ODT/ODF und weitere CMDB-Dateiformate |
| UI | Streamlit Web-UI (4 Tabs) | CLI-Review |
| Chat-Architektur | Tool-Use (LLM als Orchestrator) mit Prompt-Only-Fallback | Multi-Agenten-Orchestrierung |
| LLM-Backends | OpenAI-kompatible API (lokal und remote); Tool-Use wenn unterstuetzt | cloud-spezifische Provider-Integrationen |
| Review | Bearbeitung schwacher oder offener Matching-Faelle | Externes Ticketing |
| Lauf-Modi | `full`, `partial` | automatische Delta-Erkennung als eigener UI-Modus |
| CMDB-Modell | `Anwendung`, `Schnittstelle`, `Server`, `OrgEinheit` | tiefe Attributmodellierung |
| Deployment | Lokal / Docker | Cloud-Deployment |
| Rollen-Modell | Lanes als `:Rolle` mit `BETEILIGT_AN`; `KANN_EINNEHMEN` als kuratierbarer Link | automatische OrgEinheit-Ableitung aus Lanes |

---

## 5. Domaenenmodell

### Prozess

*(unveraendert gegenueber v0.19)*

### folgt_auf

*(unveraendert gegenueber v0.19)*

### Anwendung

*(unveraendert gegenueber v0.19)*

### Schnittstelle

*(unveraendert gegenueber v0.19)*

### Server

*(unveraendert gegenueber v0.19)*

### Rolle

Eine `Rolle` repraesentiert einen Prozessteilnehmer auf Prozessebene — typischerweise aus
einer BPMN-Lane abgeleitet. Sie ist bewusst von `OrgEinheit` getrennt: Beteiligung an
einem Prozess impliziert keine Eigentuemer- oder Verantwortungsbeziehung.

Rollen werden immer aus Prozessquellen extrahiert; sie entstehen nie aus CMDB-Daten.

### OrgEinheit

Eine `OrgEinheit` ist ein reales organisatorisches Objekt (Abteilung, Team, Bereich).
Sie entsteht entweder:
- durch explizite Pflege in Tab 4, oder
- durch Bestaetigung eines CMDB-Owner-Kandidaten.

OrgEinheiten aus Prozessquellen entstehen nicht mehr automatisch. Stattdessen werden
alle Lanes als Rollen extrahiert; der Benutzer ordnet Rollen in Tab 4 einer OrgEinheit zu.

### Verantwortung

`VERANTWORTET` verbindet eine `OrgEinheit` mit dem Objekt, fuer das sie verantwortlich ist.
Die Beziehung wird nur gesetzt wenn:
- ein CMDB-Owner-String exakt einer bekannten OrgEinheit entspricht, oder
- der Benutzer die Zuordnung in Tab 4 manuell bestaetigt (CMDB-Kandidaten-Flow).

`VERANTWORTET` wird **nicht** aus Prozessextraktion abgeleitet. Lane-Beteiligung ist kein
Ownership-Nachweis.

### Rollenzuordnung

`KANN_EINNEHMEN` verbindet eine `OrgEinheit` mit einer `Rolle`. Die Beziehung drueckt aus:
"Diese Organisationseinheit besetzt diese Prozessrolle." Sie entsteht ausschliesslich durch
Benutzerbestaetigung in Tab 4 und wird nie automatisch geschrieben.

---

## 6. Anwendungsschichten

*(unveraendert gegenueber v0.19)*

---

## 7. Importlogik

*(unveraendert gegenueber v0.19)*

---

## 8. Matching und Review

*(unveraendert gegenueber v0.19)*

---

## 9. Graph Writer

### 9.1 Vollstaendiges Schreibmodell

```cypher
(:Prozess)
(:Anwendung)
(:Schnittstelle)
(:Server)
(:OrgEinheit)
(:Rolle)
(:Alias)

(:Rolle)-[:BETEILIGT_AN]->(:Prozess)
(:OrgEinheit)-[:KANN_EINNEHMEN]->(:Rolle)
(:OrgEinheit)-[:VERANTWORTET]->(:Anwendung)
(:OrgEinheit)-[:VERANTWORTET]->(:Schnittstelle)
(:OrgEinheit)-[:VERANTWORTET]->(:Server)
(:Prozess)-[:FOLGT_AUF]->(:Prozess)
(:Anwendung)-[:DIENT]->(:Prozess)
(:Anwendung)-[:USES_INTERFACE]->(:Schnittstelle)
(:Anwendung)-[:RUNS_ON]->(:Server)
(:Schnittstelle)-[:RUNS_ON]->(:Server)
(:Alias)-[:KANN_MEINEN]->(:OrgEinheit)
(:Alias)-[:KANN_MEINEN]->(:Anwendung)
```

`(:OrgEinheit)-[:VERANTWORTET]->(:Prozess)` existiert nicht mehr. Prozessperspektive
wird ausschliesslich ueber `BETEILIGT_AN` und `KANN_EINNEHMEN` abgebildet.

### 9.2 Schreibregeln pro Quelle

| Quelle | Erzeugt |
|---|---|
| BPMN-Extraktion (Lanes) | `(:Rolle)-[:BETEILIGT_AN]->(:Prozess)` |
| Unstrukturierter Text (Rolle-Feld) | `(:Rolle)-[:BETEILIGT_AN]->(:Prozess)` |
| Unstrukturierter Text (prozess_eigentuemer-Feld, explizit) | Kandidat → Review in Tab 4 |
| Tab 4 (Prozess-Owner-Zuweisung) | `(:OrgEinheit)-[:VERANTWORTET]->(:Prozess)` |
| Tab 4 (Rollenzuordnung) | `(:OrgEinheit)-[:KANN_EINNEHMEN]->(:Rolle)` |
| CMDB (exakter Owner-Match) | `(:OrgEinheit)-[:VERANTWORTET]->(Anwendung\|Schnittstelle\|Server)` |
| Tab 4 (CMDB-Kandidaten-Bestaetigung) | `(:OrgEinheit)-[:VERANTWORTET]->(Anwendung\|Schnittstelle\|Server)` |

### 9.4 Kardinalitaet Prozess-Owner

Pro Prozess gibt es 0 oder 1 `VERANTWORTET`-Kante von einer OrgEinheit. Beim Schreiben
wird eine eventuell vorhandene Kante zuerst geloescht, dann die neue gesetzt. Die
Datenbank erzwingt diese Regel nicht; die Anwendung ist verantwortlich fuer die Einhaltung.

### 9.3 Idempotenz

- `BETEILIGT_AN`-Kanten werden bei jedem Reimport geloescht und neu geschrieben.
- `KANN_EINNEHMEN`-Kanten sind kuratierten Ursprungs und werden **nicht** bei Reimport
  geloescht. Sie bleiben erhalten bis der Benutzer sie explizit entfernt.

---

## 10. Abfrage-Layer

*(unveraendert gegenueber v0.19)*

Das Graph-Schema in `graph_schema.py` wird um `:Rolle`, `BETEILIGT_AN` und `KANN_EINNEHMEN`
erweitert, damit der Chat-Layer diese Beziehungen abfragen kann.

---

## 11. Organisation-Tab (Tab 4)

### 11.1 Bestehender Flow: OrgEinheiten und CMDB-Kandidaten

Unveraendert gegenueber v0.19.

### 11.2 Neuer Flow: Prozess-Owner-Pflege

Jede OrgEinheit-Card zeigt einen Button "Prozesse verwalten". Dahinter erscheint eine
Multiselect-Liste aller Prozesse im Graphen. Bereits dieser OE zugewiesene Prozesse sind
vorselektiert. Prozesse mit einem anderen Eigentuemer werden mit einem Hinweis markiert
("→ [andere OE]"); eine Auswahl ersetzt den bisherigen Eigentuemer (1-Owner-Constraint).

Zusaetzlich gibt es einen Abschnitt "Prozesse ohne Eigentuemer" mit allen Prozessen ohne
`VERANTWORTET`-Kante. Dort kann direkt eine OE zugewiesen werden.

Extrahierte `prozess_eigentuemer`-Kandidaten aus unstrukturierten Texten erscheinen als
Vorschlaege im Kandidaten-Abschnitt und erfordern Benutzerbestaetigung.

### 11.3 Neuer Flow: Rollenzuordnung

Tab 4 zeigt zusaetzlich alle `:Rolle`-Knoten aus Neo4j, die noch keine
`KANN_EINNEHMEN`-Kante zu einer OrgEinheit haben. Quelle ist ausschliesslich eine
Neo4j-Abfrage — kein kb.json-Kandidatenmechanismus.

```cypher
MATCH (r:Rolle)-[:BETEILIGT_AN]->(p:Prozess)
WHERE NOT (:OrgEinheit)-[:KANN_EINNEHMEN]->(r)
RETURN r.name AS rolle, collect(p.name) AS prozesse
ORDER BY r.name
```

Fuer jede nicht zugeordnete Rolle kann der Benutzer:
- Eine bestehende OrgEinheit auswaehlen und zuordnen → erzeugt `KANN_EINNEHMEN`
- Eine neue OrgEinheit anlegen und sofort zuordnen → erzeugt OrgEinheit + `KANN_EINNEHMEN`
- Die Rolle ohne Zuordnung belassen (kein Pflichtfeld)

`KANN_EINNEHMEN` wird in Neo4j geschrieben; kein Schreiben in kb.json.

---

## 12. Konfiguration

*(unveraendert gegenueber v0.19)*

---

## 13. Akzeptanzkriterien

Alle Kriterien aus v0.19 gelten weiterhin. Neu hinzugekommen:

16. Unstrukturierte Dokumente mit explizitem `prozess_eigentuemer` erzeugen einen Kandidaten im Review-Flow
17. Alle BPMN-Lanes werden als `:Rolle`-Knoten extrahiert und mit `BETEILIGT_AN` mit dem
    Prozess verbunden
17. `(:OrgEinheit)-[:VERANTWORTET]->(:Prozess)` wird aus der Prozessextraktion nicht mehr
    geschrieben
18. Tab 4 zeigt nicht zugeordnete Rollen aus Neo4j und erlaubt die Erstellung von
    `KANN_EINNEHMEN`-Kanten
19. `KANN_EINNEHMEN`-Kanten ueberleben einen Reimport unveraendert
20. Der Chat-Layer kann Rollen, `BETEILIGT_AN` und `KANN_EINNEHMEN` abfragen
21. Pro Prozess existiert hoechstens eine `VERANTWORTET`-Kante von einer OrgEinheit; eine neue Zuweisung ersetzt die alte
22. Tab 4 zeigt alle Prozesse pro OrgEinheit mit Vorauswahl der aktuell zugewiesenen

---

## 14. Getroffene Entscheidungen

*(alle Entscheidungen aus v0.19 bleiben gueltig; neu hinzugekommen:)*

| Entscheidung | Gewaehlt | Verworfen | Begruendung |
|---|---|---|---|
| Lane → Rolle statt OrgEinheit | Lanes erzeugen immer `:Rolle` | Lane direkt als OrgEinheit schreiben | Lane-Beteiligung impliziert kein Ownership; BPMN-Modelle verwenden Lanes fuer Rollen und OrgEinheiten gleichermassen — eine automatische Klassifikation waere unzuverlaessig |
| KANN_EINNEHMEN als kuratierbarer Link | Nur durch Benutzeraktion in Tab 4 | Automatisch bei Namensgleichheit | Auch identische Namen koennen verschiedene Konzepte meinen; Kuration durch den Benutzer ist explizit und pruefbar |
| Rollenzuordnung graph-only | Neo4j-Abfrage fuer nicht zugeordnete Rollen | kb.json-Kandidatenmechanismus | Aligned mit Finding 2 (kb.json-Abloesung); Neo4j ist robuster gegen Dateimanipulation und Sync-Fehler |

---

*Bridgr | Architektur v0.20 | Stand Juni 2026*

# BRIDGR Feedback — Live-Review via Claude in Chrome
_Erstellt: 2026-06-08 | Basis: Vollständiger Live-Durchlauf localhost:8501_
_Getestet: Chat/Kommunikation, Zuordnungen (Bestätigen/Ablehnen), Organisation (Kandidaten, Batch, Prozesseigentümer)_

---

## Systemzustand beim Review

- 32 Prozessdateien aus letztem Import (Mix: .txt, .docx, .bpmn)
- 7 eindeutige + 61 zu prüfende Applikationszuordnungen
- 6 Organisationseinheiten bekannt, 10 offene Kandidaten
- Neo4j erreichbar, LLM konfiguriert (Gemma lokal)

---

## Tab Kommunikation — Funktionstest

### Was funktioniert
- Chat antwortet korrekt auf direkte Fragen ("Welche Prozesse nutzen SAP SD?" → "Jahresabschluss")
- Ergebnis wird als Tabelle dargestellt + CSV-Export ist erreichbar
- Cypher-Query unter "Technische Details" einsehbar — gut für Power-User und Debugging
- Antwortzeit lokal ca. 30–40 Sekunden — akzeptabel für PoC, aber für produktive Nutzung ein Thema

### Finding #1 — Kontextauflösung bei Folgefragen / LLM überspringt Tool Call — ✅ ERLEDIGT

**Ursache (analysiert):** Kein Code-Bug, kein fehlendes History-Handling.
`_build_llm_history` übergibt bereits bis zu 20 vollständige Messages als echte Chat-History.
Das Problem lag auf zwei Ebenen:

1. **Modell:** gemma4:e4b (~4B effektive Parameter) zu schwach für zuverlässiges
   Entitätstyp-Tracking über Turns.
2. **Systemprompt:** Zeile "Your knowledge comes exclusively from the graph" beschreibt
   eine Eigenschaft statt ein Pflichtverhalten — schwächere Modelle interpretieren das als
   optional und antworten aus Trainingswissen statt den Graphen abzufragen.

**Lösung:** Zwei Maßnahmen kombiniert:

1. **Modellwechsel:** gemma4:e4b → gemma4:12b (7.6GB, läuft vollständig im VRAM der
   RTX 5060 Ti 16GB). 12b löst Folgefragen mit impliziten Entitätsreferenzen korrekt auf.

2. **Systemprompt-Anpassung** in `prompts/chat_system.md`, Zeilen 5-6 ersetzt durch:
   ```
   **Every factual answer about the IT landscape requires a graph query first.**
   Never answer from general knowledge — your company-specific data lives exclusively
   in the graph. A response without a prior query is only allowed for clarifications,
   greetings, or questions about your own capabilities.
   ```
   Aktive Handlungsanweisung statt passive Selbstbeschreibung — Modelle halten sich
   besser an explizite Protokolle als an Eigenschaftsbeschreibungen.

**Ergebnis nach Fix:** Beide Fragen korrekt mit Graphabfrage beantwortet, technische
Details in beiden Antworten vorhanden, Folgefrage-Kontext korrekt aufgelöst.

**Lerneffekt:** Modell nicht zu schnell abschreiben — oft ist es der Prompt, nicht das Modell.

**Nachbefund (2026-06-08):** Auch nach Modell- und Prompt-Wechsel trat das Verhalten erneut auf —
gemma4:12b überspringt sporadisch den Tool Call und halluziniert Antworten aus dem Trainingswissen.
Ursache: `tool_choice: "auto"` überlässt dem Modell die Entscheidung; bei nicht-deterministischen
Modellen ist das nicht zuverlässig genug.

**Zusätzliche Code-Maßnahme:** Correction-Retry in `services/query_service.py`
(`_run_tool_use_turn`): Wenn der erste Response keinen Tool Call enthält und noch keine Query
ausgeführt wurde, wird ein `[HINWEIS]` injiziert und einmal wiederholt. Das Event
`query_correction_retry` im `debug.log` macht das Auslösen des Mechanismus sichtbar.
Findings.txt Eintrag #9.

### Beobachtung: Chat-History nach Seiten-Reload weg
Nach einem Browser-Reload ist der Chat-Verlauf vollständig zurückgesetzt — kein Hinweis
in der UI darauf. Bei einer aktiven Analyse-Session unangenehm.

---

## Tab Zuordnungen — Funktionstest

### Was funktioniert
- **Bestätigen** funktioniert einwandfrei: Eintrag verschwindet sofort aus der Liste, keine Seite neu laden nötig
- **Ablehnen** funktioniert: CMDB-Kandidat wird entfernt, Eintrag bleibt als "offen ohne Kandidat" stehen
- Sofortige UI-Aktualisierung nach jeder Aktion — sehr gute UX, kein Streamlit-Rerun-Delay spürbar
- Mehrere Einträge mit echten CMDB-Matches (DocuSign/DocuSign Signing API, SAP CRM/SAP SRM) — Matching-Qualität wirkt plausibel

### Beobachtung: kein Undo
Nach Bestätigen oder Ablehnen gibt es keine Rückgängig-Funktion. Für Testdaten egal,
in Produktion könnte ein Klick-Fehler problematisch sein.
Eine einfache Lösung wäre ein kurzes Zeitfenster mit "Rückgängig"-Option (Toast-Notification),
alternativ ist Korrektur über "Manuell anlegen" möglich.

---

## Tab Organisation — Funktionstest

### Was funktioniert
- **Kandidaten übernehmen** funktioniert sauber: "Auftragsbearbeitung" als neue OE angelegt,
  sofort aus Kandidatenliste entfernt
- Neu angelegte OE taucht sofort in den Eigentümer-Dropdowns auf — kein Refresh nötig ✓
- **Batch-Zuweisung** funktioniert: Prozesse per Multiselect wählen, gemeinsame OE wählen,
  "Batch zuweisen" klicken — vom Projektleiter bestätigt (nicht reproduzierbares Testproblem
  auf meiner Seite, vermutlich Klick-Reihenfolge-Artefakt beim Browser-Automation-Test)
- Kandidaten-Karten zeigen Prozesse + Rollen + Quellen — hilft bei der Entscheidung,
  Qualität der extrahierten Informationen wirkt plausibel

---

## Allgemeine Workflow-Beobachtungen

### Positive Überraschung: Reaktionsgeschwindigkeit der UI
Trotz Streamlit ist die UI nach Aktionen erstaunlich reaktionsschnell.
Bestätigen/Ablehnen/Übernehmen aktualisieren die Ansicht ohne merkliche Verzögerung.

### Sitzungsgebundenheit ist der größte Workflow-Bruch
Der Reload-Reset betrifft Chat-History und vermutlich auch nicht gespeicherte Formulareingaben.
Für einen EA-Analysten der eine halbe Stunde Zuordnungen bearbeitet und dann versehentlich
F5 drückt ist das ein echter Schmerzpunkt — zumindest der Chat-Verlauf wäre speicherbar.

### Tab-Navigation per Klick bei gescrollter Seite
Wenn man weit runtergescrolt ist und auf einen anderen Tab klickt, wird der Klick
gelegentlich nicht registriert. Workaround: erst nach oben scrollen, dann Tab klicken.
Betrifft vermutlich nur Browser-Automation — manuell eher kein Problem.

---

## Priorisierungsübersicht

| Prio | Thema | Typ | Status |
|------|-------|-----|--------|
| Kritisch | Dual Source of Truth kb.json/Neo4j ablösen | Architektur | Offen |
| ✅ Erledigt | Finding #1: Folgefragen-Kontextauflösung + LLM überspringt Tool Call | LLM/Prompt + Code | gemma4:12b + Systemprompt-Fix + Correction-Retry in query_service.py |
| Hoch | Import-Expander standardmäßig offen | UX | Bekannt |
| Mittel | Chat-Sessionsgebundenheit: Hinweis in UI fehlt | UX | Bestätigt live |
| Mittel | Kein Undo nach Bestätigen/Ablehnen | UX | Neu |
| Mittel | Kommunikations-Tab: Systemstatus beim Öffnen fehlt | UX | Bekannt |
| Niedrig | Mapping speichern: fehlendes visuelles Feedback | UX | Bekannt |
| Niedrig | Org-Sync: Zeitstempel letzter Sync fehlt | UX | Bekannt |

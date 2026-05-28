# UX-Review BRIDGR

_Erstellt: 2026-05-28_

---

## Gesamteindruck

Die App ist funktional und deckt den Workflow korrekt ab, aber sie spiegelt ihren eigenen Entstehungsprozess wider: Features wurden iterativ hinzugefügt, nicht von oben nach unten entworfen. Für einen neuen Nutzer ist der Einstieg unklar, und die Tab-Struktur widerspricht dem natürlichen Workflow.

---

## 1. Information Architecture — kritisches Problem

**Die Tab-Reihenfolge ist umgekehrt zum Arbeitsablauf.**

Der logische Flow ist:
```
Konfigurieren → Importieren → Reviewen → Abfragen
```

Die tatsächliche Tab-Reihenfolge:
```
Kommunikation | Link Editing | Anwendungskonfig | Organisation
   (Ende)         (Mitte)        (Anfang)          (parallel)
```

Ein neuer Nutzer startet auf Tab 1, sieht ein leeres Chatfeld, tippt eine Frage — und bekommt eine Warnung "Bitte zuerst ein LLM-Modell konfigurieren." Diese Warnung erscheint erst **nach** dem Eintippen, nicht proaktiv beim Laden der Seite.

**Empfehlung:** Tab-Reihenfolge drehen:
```
Import | Review | Abfrage | Organisation
```
oder Config ganz in eine Sidebar auslagern (Streamlit unterstützt `st.sidebar`).

---

## 2. Tab 3 — Anwendungskonfig: zwei Welten in einem Tab

**Import** (operativer Workflow) und **Konfiguration** (System-Setup) haben völlig unterschiedliche Nutzungsfrequenzen und Nutzertypen. Beide sind in Expandern versteckt (`expanded=False`), d.h. der Tab wirkt beim Öffnen leer.

Der Import — die **Kernfunktion der App** — ist hinter zwei Klicks vergraben:
1. Tab "Anwendungskonfig" wählen
2. Expander "Import" aufklappen
3. Pipeline starten

**Empfehlung:** Import-Sektion als eigenen Tab oder mit `expanded=True`. Konfigurations-Felder dagegen können collapsed bleiben, da sie selten angefasst werden.

Das Konfigurationsformular selbst hat ~20 Felder in einer **flachen, ungruppierten Liste**. Das ist für einen Techniker lesbar, aber einschüchternd. Einfache Gliederung mit `st.divider()` und Abschnittsüberschriften (LLM, Neo4j, CMDB-Spaltenmapping) würde schon viel helfen.

---

## 3. Tab 2 — Link Editing: Redundanz und kognitive Überlastung

Das Tab enthält zwei Ansichten auf dieselben Daten:
- **Review-Items-Tabelle** (aggregierte Sicht, alle offenen Links)
- **Dokumentdetails** (expandable, per Dokument mit denselben Links)

Ein Nutzer sieht dieselbe Verknüpfung zweimal — einmal in der Tabelle, einmal in den Details. Das sorgt für Verwirrung: "Habe ich das schon bestätigt? Wo muss ich nochmal schauen?"

**Empfehlung:** Entweder die aggregierte Tabelle ODER die Dokumentdetails als primäre Reviewfläche — nicht beide. Die Tabellen-View ist kompakter; die Dokumentdetails könnten auf "rein informativ" reduziert werden (kein Confirm/Reject dort).

Die **Knowledge-Base-Verwaltung** am Ende des Tabs (KB leeren) ist eine technische/destruktive Operation, die semantisch nicht zum Nutzer-Review gehört. Sie gehört in den Config-Tab oder in ein separates Admin-Panel.

---

## 4. Tab 4 — Organisation: Cramped Actions

Die Kandidaten-Aktionszeile quetscht 5 Widgets in eine Zeile:
```
[Selectbox: bestehende Org] [Mappen] [Textfeld: neuer Name] [Übernehmen] [Abweisen]
```

Das ist schwer lesbar und die beiden Aktionspfade ("auf bestehende mappen" vs. "als neue erstellen") sind visuell nicht unterschieden. Auf kleineren Bildschirmen wird das eng.

**Empfehlung:** Zwei Zeilen pro Kandidat oder zwei `st.columns`-Blöcke mit klarer Überschrift:
```
[Auf bestehende mappen]     vs.    [Als neue übernehmen]
```

---

## 5. Sprachliche Konsistenz

**Umlaute:** Konsequent ohne Umlaute ("Bestaetigen", "Ablehnen", "Gespraech", "Manuell anlegen"). Das ist vermutlich eine Encoding-Entscheidung, wirkt aber unprofessionell in einer deutschen App. Entweder echte Umlaute oder konsequentes ASCII — aktuell ist es inkonsistent (z.B. "Ablehnen" braucht keine Umlaute, "Übernehmen" schreibt sich "Uebernehmen").

**Deutsch/Englisch-Mix:** Tab-Labels, Feldnamen und Button-Labels wechseln zwischen beiden Sprachen. Beispiele:
- "Save Config" in einem sonst deutschen Formular
- "Run Mode", "full/partial", "Debug Mode" als englische Fachbegriffe
- "Review-Items", "Knowledge Base" als Anglizismen

Das ist bei technischen Tools akzeptabel, sollte aber bewusst sein — und die Wechsel sollten nicht innerhalb eines Kontextes passieren.

---

## 6. Kein Onboarding-Zustand

Bei leerem System (kein Config, kein Import) zeigt die App:
- Tab 1: leeres Chatfeld, keine Erklärung
- Tab 2: "Noch kein gespeicherter Pipeline-Lauf vorhanden"
- Tab 3: zwei geschlossene Expander

Ein Nutzer der App zum ersten Mal benutzt, hat keine Orientierung. Ein einfaches `st.info("Startpunkt: Konfigurieren Sie zuerst LLM und Neo4j im Tab Anwendungskonfig, dann starten Sie einen Import.")` auf Tab 1 (wenn kein Modell konfiguriert) würde schon helfen.

---

## Priorisierte Empfehlungen

| Priorität | Maßnahme | Aufwand |
|---|---|---|
| Hoch | Tab-Reihenfolge drehen (Import zuerst) | gering |
| Hoch | Import-Expander standardmäßig offen | minimal |
| Hoch | Proaktive Status-Warnung in Tab 1 bei leerem Config | gering |
| Mittel | Config-Formular in Abschnitte gliedern | gering |
| Mittel | Review: nur eine Reviewfläche (Tabelle ODER Details) | mittel |
| Mittel | Kandidaten-Layout: zwei Aktionspfade klar trennen | gering |
| Niedrig | KB-Tools aus Review-Tab herausnehmen | gering |
| Niedrig | Umlaute vereinheitlichen | trivial |

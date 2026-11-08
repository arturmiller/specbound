# Das Specbound-Designboard pflegen

## Ausgangspunkt

Das vom Nutzer bereitgestellte HTML liegt unverändert unter `docs/original/`.
SHA-256: `4884fbc5a00eefbfb1b3e95a1b1767cdae747d29c2a36b0f5e7336479e5ea9d5`.

Die fünf JSON-Datensätze sind inhaltlich unverändert extrahiert. Ein Test
vergleicht sie mit den ursprünglichen Deklarationen. Bei späteren bewussten
Inhaltsänderungen den Vergleich gezielt anpassen und das Original erhalten.
Den Einmalimport `scripts/import-original.mjs` nicht erneut auf bearbeitete
Quellen anwenden.

## Änderungen zusammenhalten

1. Betroffene Stories, Screens, Architekturbausteine und Tasks über stabile IDs bestimmen.
2. Inhalte in `designboard/data/`, Screen-Darstellung in `designboard/src/prototype.js`,
   Architektur/Planung in `architecture-roadmap.js` und Canvas-Verhalten in `canvas.js` ändern.
3. Bei abgeschlossener Umsetzung Designnotizen nachvollziehbar abschließen und
   Screens mit dem tatsächlichen Produktverhalten abgleichen.
4. `npm run check` ausführen. Betroffene Abläufe im Browser prüfen, insbesondere
   Vorschau, Notizkoordinaten unter Zoom sowie Sicherung/Import.
5. Quellen zusammen mit der Produktänderung reviewen und versionieren.
   `dist/` wird gebaut und nicht von Hand geändert.

Task-Markierungen sind lokale Planungshilfen. Die ursprünglichen 10 Epics,
17 Features und 49 Tasks wurden als GitHub Issues übernommen, einschließlich
Elternbeziehungen und Task-Abhängigkeiten. Die Zuordnung der stabilen Board-IDs
steht in [GitHub-Issues](github-issues.md) und maschinenlesbar in
`github-issues.json`. Das zusätzliche Epic E11 plant die 44 Designboard-Screens
in Phase 1 mit acht Features und 16 Tasks. Die ursprüngliche V1-Baseline-Arbeit
ist Phase 2; T024 und T026 sind Later. Es gibt keine laufende GitHub-Synchronisierung;
lokale Task-Markierungen spiegeln den tatsächlichen Issue-Status nicht wider.

## Speicherung

`specbound-workspace-v1` ist der gemeinsame Browser-Speicherschlüssel. Die
ursprünglichen Schlüssel für Board und Task-Status werden beim ersten Start
weiterhin gelesen. Jede Domain hat eigenen Browser-Speicher: Für den Wechsel
zwischen lokalem Board und gehosteter Site JSON-Sicherung exportieren/importieren.

Das Format `specbound-workspace`, Version 1, enthält `board` (bisheriges
`atelier-designboard`, Version 3), `roadmapProgress`, `draftNote` und `view`.
Der Import prüft Referenzen, Koordinaten, IDs und Versionen vor der Übernahme.
Dateien werden als Daten gelesen, nicht als Code ausgeführt. Ältere Board-Exporte
ersetzen keine Task-Markierungen. Für spätere Änderungen am Screen-/Task-Inventar
ist zu prüfen, ob eine explizite Formatmigration erforderlich ist. Die hier
ergänzten Task-IDs erhalten alle bisherigen IDs; ältere gültige Sicherungen
bleiben importierbar, neue Tasks beginnen ohne lokale Fortschrittsmarkierung.

## Prüfung der ersten Migration

- Original und Archiv: gleicher SHA-256.
- Datensätze: 44 Screens, 9 Stories, 10 Epics, 17 Features, 49 Tasks.
- Task-Abhängigkeiten: gültige Referenzen, keine Zyklen.
- Browser: Screens gerendert; Architektur und ECS-Profil bedienbar;
  Task-Markierung nach Neuladen erhalten; Notiz in Screen-Koordinaten platziert;
  Notiz und unplatzierter Entwurf exportiert, importiert und wiederhergestellt.
- Keine Anbindung an echte Produkt-, Governance- oder Evidence-Backends.

## Hosting

`dist/` ist eine eigenständige statische Site. Die ChatGPT-Site-Identität steht in
`.openai/hosting.json`. Bei Veröffentlichungen dieselbe Identität erhalten und
neu bauen. Die Veröffentlichung verändert keine Notizen in anderen Browsern.
Gemeinsame, authentifizierte Speicherung ist eine spätere Erweiterung.

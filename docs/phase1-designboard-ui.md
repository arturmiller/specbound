# Phase 1: Produktoberfläche nach Designboard

Phase 1 baut die Produkt-App aus `services/web` anhand der 44 versionierten
Screens in `designboard/data/screens.json` und ihrer Darstellung in
`designboard/src/prototype.js`. Das Designboard ist die Referenz für Aufbau,
Navigationshierarchie, Informationsgruppen, Typografie, Farben und Zustände.
Seine Beispielwerte sind keine Produktdaten und sein Prototyp ist kein Backend.
Die Originaldatei unter `docs/original/` bleibt unverändert.

Die Screen-IDs sind in den einzelnen Tasks aufgeführt; jeder der 44 Screens ist
genau einem Phase-1-Task zugeordnet. Eine Screen-Ansicht darf bei noch fehlender
Funktion einen klar benannten, zugänglichen Nicht-verfügbar-Zustand zeigen.
Dadurch wird die spätere Funktion nicht als implementiert deklariert. Insbesondere
Baseline-Simulation und Pack-Aktivierung hängen weiterhin von #65–#68 in Phase 2
ab; Ausführungsfreigaben und der externe Beispielprovider bleiben #51 und #53 in
Later. Kubernetes und AWS bleiben zurückgestellt.

## Verbindliche Abnahme für jeden UI-Task

- Die benannten Referenz-Screens vor der Umsetzung im laufenden Designboard
  ansehen. Die App auf Desktop bei 1440 × 900 und mobil bei 390 × 844 prüfen;
  das Board zeigt seine einzelnen Screen-Frames. Seitenaufbau, Navigation,
  Informationshierarchie, Karten, Tabellen, Formen, Abstände, Typografie und
  Farben müssen erkennbar zur Referenz passen. Responsive Anpassungen dürfen die
  Information oder Bedienung nicht verlieren.
- Im Pull Request für jeden betroffenen Screen aussagekräftige Vorher/Nachher-
  bzw. Referenz/App-Screenshots mit gleichem dargestelltem Zustand und Viewport
  bereitstellen. Sichtbare Unterschiede begründen; eine bloße Behauptung der
  Designkonformität oder ein reiner API-Test genügt nicht als Abnahme.
- Mit realen API-Ergebnissen bzw. kontrollierten Test-Fixtures prüfen: Daten-,
  Leer-, Lade-, Fehler- und Berechtigungszustände, direkte URL, Reload und
  Rücknavigation, soweit der Screen sie benötigt. Keine Board-Beispielwerte als
  Produktdaten ausgeben; UNKNOWN bleibt UNKNOWN. Nicht implementierte Aktionen
  sind klar als solche erkennbar und lösen keine Scheinfunktion aus.
- Tastaturbedienung, sichtbarer Fokus, aussagekräftige Labels, Status- und
  Fehlermeldungen prüfen. Browser-Integrationstest für den konkreten Benutzerweg
  sowie passende API- und Repository-Checks ausführen. Ein Task gilt nur als
  fertig, wenn Design und Verhalten nachgewiesen sind.

Die Umsetzung verwendet bestehende Organisations-, Team-, Produkt-, Pack-,
Assessment- und Agenten-APIs. Fehlende Lesezugriffe auf bereits vorhandene Daten
dürfen im passenden Task ergänzt werden, einschließlich Autorisierung und Tests.
Zusätzliche fachliche Schreibvorgänge oder Collector-Freigaben werden dadurch
nicht stillschweigend vorgezogen. Die Governance-Plattform verteilt keine
Aufträge an Agenten. Zustände aus Git bleiben durch Git-Rechte begrenzt.

## Phasen und Status

`MVP` bezeichnet den vorhandenen technischen Kern, `Phase 1` die hier geplante
Produktoberfläche, `Phase 2` den funktionalen Baseline-Ausbau und `Later`
ausdrücklich spätere Aufgaben. #51 und #53 behalten ihre HITL-Kennzeichnung.
Die lokale Fortschrittsmarkierung im Designboard ist keine Synchronisierung mit
GitHub; Issue-Zustände sind dort die Quelle für den Umsetzungsstatus.

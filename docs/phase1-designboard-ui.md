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

Die Produkt-Discovery zeigt gespeicherte Scanbeobachtungen mit Repository, Ref,
Revision, Zeitpunkt, abgedeckten Dateien und Fehlern als historische Befunde.
Aus Dateien oder fehlenden Scans werden keine Komponenten oder vollständige
Abdeckung abgeleitet. Produktdetails zeigen Subjects und Ergebnisse aus dem
zuletzt gespeicherten Assessment mit dessen Umgebung, Kontext und Revision;
dieser Snapshot ist keine zusammengefasste Aussage über alle Umgebungen. Fehlende
Beobachtungen bleiben UNKNOWN. Der Discovery-Lesezugriff folgt denselben
Teamrechten wie das zugehörige Produkt.

Der Provider-Pack-Katalog speichert das eingelesene Manifest und Capability-
Referenzen, nicht die Inhalte der referenzierten Schema- und Fixture-Dateien.
Die Vertragsansicht zeigt deshalb Dateipfade und kennzeichnet die Inhalte als
nicht verfügbar. Ein erfolgreicher Import belegt die strukturelle Validierung,
aber weder ausgeführte Tests noch eine Berechtigung zum Collector-Start.

Das Evidence-Register liest nur Datensätze sichtbarer Produktteams und zeigt
Collector-Revision, Image, Produktrevision, Scope und Ablaufzeit unverändert.
Eine gespeicherte Collector-Revision wird nicht als eindeutige Provider-ID
ausgegeben. Zeitliche Gültigkeit ist kein Vertrauensurteil; abgelaufene oder
nicht bestimmbar datierte Evidence bleibt UNKNOWN. Die seitengesteuerte Liste
ist nach Beobachtungszeit und ID stabil sortiert; bei gleichzeitig neu
eintreffenden Datensätzen kann sich ein Offset zwischen Aufrufen verschieben.

Die Übersicht summiert Bewertungen der passenden gespeicherten Snapshots;
dies ist kein aktuelles Portfolio-Urteil und kann dieselbe Kontrolle in mehreren
Snapshots enthalten. Teamfilter gelten für Produkte, Findings und Assessments,
Umgebungsfilter für Findings und Assessments. Packs bleiben organisationsweit.
Die Diagrammpunkte sind nach Erstellungszeit geordnet, ihre Abstände bilden keine
Zeitintervalle ab; ohne gespeicherte Bewertungen bleibt der Gesamtzustand UNKNOWN.

Die Finding-Ansicht verknüpft das Finding über dessen gespeichertes Ereignis
und die zugehörige Bewertung mit genau dem Assessment und den darin referenzierten
Evidence-Datensätzen. Organisation, Produkt, Control und Subject müssen
übereinstimmen; ein nicht belegbarer Zusammenhang wird nicht angezeigt. Das
historische Bewertungsergebnis und die aktuelle zeitliche Gültigkeit einer
Evidence sind getrennte Angaben. Schweregrad, Provider-Identität und Vertrauen
werden nicht aus anderen Feldern erraten; nicht gespeicherte Werte bleiben UNKNOWN.
Die Oberfläche beauftragt keine Korrekturmaßnahmen.

Der Lösungsweg zeigt ausschließlich gespeicherte Ereignisse desselben Findings
mit den zugehörigen Produkt- und Packrevisionen. Historische Berichtslinks öffnen
den jeweiligen Snapshot; ein PR-Kontext belegt weder Merge noch Reparatur oder
einen manuellen Recheck. Änderungen des Findings während des Ladens führen zu
einem Hinweis statt einer vermischten Ansicht. Specbound weist keine Arbeit zu.

Die Finding-Inbox listet gespeicherte PR-Findings sichtbarer Produktteams und
kennzeichnet ihre Herkunft. Die angezeigte Revision stammt nur aus einem zum
Finding passenden Snapshot mit gleichem Produkt, Kontext, PR und Umgebung.
Zähler und Filter beziehen sich ausschließlich auf diese PR-Findings. Baseline-
Triage, Zuweisung, Abschluss und Produktions-Recheck sind bis zu #65–#68 nicht
verfügbar; ein gespeicherter Status ist keine manuelle Abschlussaktion.

Die PR-Ansicht listet ausschließlich sichtbare, gespeicherte PR-Assessments;
sie ist keine vollständige GitHub-PR-Inbox. Der Bericht und seine Zähler beziehen
sich immer auf den gewählten unveränderlichen Snapshot. GitHub-Kommentar,
aktuelle PR-Revision, Review- und Merge-Status sowie ein manueller Recheck werden
ohne nachweisbare Datenquelle nicht behauptet oder als Aktion angeboten. Links zu
Findings führen zum jeweils aktuellen Finding und sind entsprechend beschriftet.

Agenten sind lokale nichtmenschliche Principals. Organisationsinhaber können
sie registrieren und Teams als Viewer zuordnen; eine externe Git-Identität wird
dabei nicht gespeichert und keine Ausführung gestartet. Fehlende Teamzugriffe
werden als unbekannte Mitgliedschaften dargestellt.

Agentenzugänge werden vom menschlichen Organisationsinhaber ausgestellt und
widerrufen. Das einmalig ausgegebene Token bleibt ausschließlich im flüchtigen
Ansichtszustand; nach Verlassen oder Neuladen ist es nicht erneut verfügbar.
Die Zugangsliste liefert nur ID, Ablauf und Widerruf, keine Geheimnisse oder
Hashes. Der Auditverlauf zeigt gespeicherte Specbound-Ereignisse; externe Git-
Aktivität und Repository-Rechte werden nicht daraus abgeleitet.

Die Portal-Dokumentation verwendet die versionierten Guides und deren lokale
Beispiele. Kategorien bleiben über ihre URL-Fragmente erreichbar; unbekannte
Kategorien werden als fehlend angezeigt. Die Anleitungen unterscheiden den
Entwicklungslogin von einer geschützten OIDC-Konfiguration und beschreiben die
optionalen GitHub-Publisher mit ihren tatsächlichen Voraussetzungen.

Die Governance-Ansichten zeigen gespeicherte Release-Tags und gepinnte Commits.
Eine aktive Revision, Release-Differenz oder Auswirkung auf Produkte wird daraus
nicht abgeleitet. Simulation, Baseline-Auswirkungen und Aktivierung bleiben bis
zu #67 und #68 ausdrücklich nicht verfügbar; ihre Ansichten ändern keine Daten.

## Phasen und Status

`MVP` bezeichnet den vorhandenen technischen Kern, `Phase 1` die hier geplante
Produktoberfläche, `Phase 2` den funktionalen Baseline-Ausbau und `Later`
ausdrücklich spätere Aufgaben. #51 und #53 behalten ihre HITL-Kennzeichnung.
Die lokale Fortschrittsmarkierung im Designboard ist keine Synchronisierung mit
GitHub; Issue-Zustände sind dort die Quelle für den Umsetzungsstatus.

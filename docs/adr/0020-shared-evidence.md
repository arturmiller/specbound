# 0020: Gemeinsame Evidence für mehrere Controls

`store_and_evaluate` nimmt das Ergebnis einer Collector-Ausführung für genau eine
Capability und genau eine Observation entgegen. Es speichert die Observation
einmal und bewertet anschließend eine begrenzte Liste unterschiedlicher Controls,
die alle dieselbe Capability anfordern. Jede Bewertung wird separat gespeichert;
passende Bewertungen referenzieren dieselbe Evidence-ID. Abweichende Capabilities,
doppelte Controls und mehrdeutige Responses werden abgewiesen. Eine Datenbank-
Savepoint-Grenze verhindert teilweise Speicherung bei einem Fehler.

Der Aufrufer startet den kontrollierten Collector genau einmal und übergibt dessen
validierte Response. Die Funktion startet keine weiteren Container, überspringt keine
Geltungsbereichs-, Abdeckungs- oder Frischeprüfung und bewirkt keine Freigabe. Die CI
prüft den Ablauf mit einem echten isolierten Test-Collector und PostgreSQL.
Wiederholbarkeit über Job-Retries hinweg und die Auswahl zwischen mehreren bereits
vorhandenen frischen Records gehören weiterhin zur späteren Queue-/Evidence-Arbeit.

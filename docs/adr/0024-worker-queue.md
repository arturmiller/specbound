# 0024: Worker-Leases und Ergebnisübernahme

Ein Worker beansprucht den ältesten `pending`- oder abgelaufenen `running`-Job
seiner Organisation mit `FOR UPDATE SKIP LOCKED`. Jeder Versuch erhält einen neuen
Lease-Token und eine Ablaufzeit. Stirbt der Worker, wird der Job nach Ablauf erneut
verfügbar; nach drei fehlgeschlagenen beziehungsweise abgelaufenen Versuchen wird er
`dead`. Fehlermeldungen enthalten nur feste Fehlercodes, keine Exception-Inhalte.

Der Handler bereitet die Arbeit außerhalb der Abschluss-Transaktion vor und liefert
eine Funktion, die den Snapshot innerhalb dieser Transaktion erstellt. Die
Ergebnisübernahme sperrt den Job, prüft den aktuellen Token und die Lease vor und
nach dem Erstellen und validiert Organisation, Produkt, Repository, PR-Nummer und
Head-SHA des Snapshots. Bei Fehler oder abgelaufener Lease wird der Snapshot per
Savepoint zurückgerollt. Das Job-Ergebnis wird genau einmal zugeordnet; ein
wiederholtes Bestätigen desselben abgeschlossenen Tokens liefert dieselbe ID, ohne
den Handler erneut auszuführen. Ein alter Token kann keinen neuen Versuch beenden.
Der Abschluss wendet den Finding-Lebenszyklus in derselben Transaktion auf den
Snapshot an; schlägt der Abschluss fehl oder läuft die Lease ab, werden auch
Finding- und Historienänderungen zurückgerollt. Die Job-Unique-Constraint aus ADR 0023 begrenzt das Ergebnis auf einen Job je
Repository-Bindung, PR und Head-SHA.
Bereits vor dieser Änderung abgeschlossene Jobs werden dadurch nicht rückwirkend
neu verarbeitet; für sie wird keine lückenlose Historie nachträglich behauptet.

`queue_worker.run_queue` stellt das Polling für einen explizit übergebenen,
vertrauenswürdigen Handler bereit. Der Compose-Worker bleibt standardmäßig untätig:
Es gibt noch keinen freigegebenen produktiven Handler, keine automatische Auswahl
freigegebener Packs und keine Secret-/Egress-Freigaben aus #51. Die Tests verwenden
einen lokalen Handler und PostgreSQL, nicht die Produktionsfreigabe. Worker müssen
eine verlässliche gemeinsame UTC-Uhr verwenden. Ein Downgrade der Migration wird
abgelehnt, sobald Jobs Ausführungshistorie besitzen, um sie nicht zu verwerfen.

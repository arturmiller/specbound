# ADR 0026: Lokales Monitoring und Wiederherstellung

## Entscheidung

API und Worker schreiben JSON-Zeilen auf ihre Container-Ausgabe. HTTP-Logs
enthalten Methode, Pfad ohne Query-Parameter, Status und Dauer; Request-Bodies
und Authorization-Header werden nicht erfasst. Der standardmäßig in Compose aktivierte
Endpunkt `/metrics` liefert aggregierte Jobzahlen pro Status sowie das Alter
des ältesten wartenden Jobs in Sekunden. Er ist nicht authentifiziert; die API
ist in der lokalen Compose-Konfiguration an Loopback gebunden. Mit
`METRICS_ENABLED=false` lässt sich der Endpunkt deaktivieren. Ein laufender
Worker bedeutet weiterhin nicht, dass bereits ein Job-Handler freigegeben ist.

## Sicherung und Restore

Voraussetzungen sind Docker Compose, Python 3 und ein bereits gebautes API-Image.
Das Skript sichert PostgreSQL mit `pg_dump` und die aktuellen Schlüssel und
Bytes des konfigurierten MinIO-Buckets in einem neuen Verzeichnis. Ein Manifest
enthält Prüfsummen; das Objektarchiv prüft zusätzlich jedes Objekt. Die Dateien
können vertrauliche Daten enthalten und müssen entsprechend geschützt werden.

Vor der Sicherung müssen **alle** schreibenden Prozesse angehalten sein,
einschließlich externer Datenbank- oder S3-Clients. Das Skript prüft, dass API,
Web und Worker des angegebenen Projekts gestoppt sind. Datenbank und MinIO
müssen laufen. Es gibt keinen atomaren Snapshot über beide Speicher hinweg.

Beispiel für ein Quellprojekt `specbound` und ein neues Zielprojekt
`specbound-restore` im Repository-Verzeichnis:

```sh
docker compose -p specbound stop api web worker
python scripts/compose_backup.py backup --project specbound --path ./backup-2026-11-07

# Die lokalen MinIO-Ports werden für das Zielprojekt frei benötigt.
docker compose -p specbound stop db minio
docker compose -p specbound-restore up -d --wait db minio
docker compose -p specbound-restore run --rm minio-init
python scripts/compose_backup.py restore --project specbound-restore --path ./backup-2026-11-07
docker compose -p specbound-restore up -d --wait
```

Das Zielprojekt muss neue, leere Volumes verwenden; insbesondere darf der
Migrationsdienst vor dem Restore noch nicht gelaufen sein. Die Datenbank und
der Bucket müssen leer sein. Dateinamen, Prüfsummen und das gesamte Objektarchiv
werden vor den Schreibvorgängen geprüft. PostgreSQL wird transaktional
wiederhergestellt. Scheitert anschließend der Objekt-Restore, ist das Ergebnis
nicht vollständig: Für einen erneuten Versuch ein anderes leeres Ziel verwenden.
Keine bestehenden Volumes werden vom Skript gelöscht oder überschrieben.

Das Format sichert den aktuellen Objektinhalt, keine S3-Versionen oder
Objektmetadaten. Es unterstützt höchstens 10.000 Objekte, 5 GiB pro Objekt und
8 GiB pro Archiv; temporärer Speicherplatz in mindestens Archivgröße wird
benötigt. Ein automatisierter Compose-Test stellt Assessments, Audit-IDs und
Objektinhalt aus beiden Backups wieder her und startet die Dienste danach erneut.

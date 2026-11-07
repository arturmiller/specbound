# 0025: Lokale Images und Healthchecks

Compose baut Web, API und Worker als benannte Images mit dem Tag aus
`SPECBOUND_IMAGE_TAG`; ohne Vorgabe ist der Tag `0.1.0-local`. Der Migrationsdienst
verwendet dasselbe API-Image. Die Entwicklungs-Images benötigen nur lokale Compose-
Dienste und keine Cloud-Zugangsdaten.

Die API unterscheidet `/healthz` als Prozessprüfung von `/readyz`: Bereitschaft
erfordert eine erreichbare Datenbank auf dem aktuellen Alembic-Stand und einen
mit den konfigurierten Zugangsdaten über HeadBucket erreichbaren MinIO-Bucket. Der
Compose-Healthcheck verwendet `/readyz`. Der Web-Healthcheck prüft den Webserver,
das Einstiegsskript und die API-Bereitschaft über den Proxy. Das Web startet erst,
wenn die API bereit ist. HeadBucket testet keine einzelnen Objektoperationen.
Die Healthchecks geben keine Konfigurationsdetails aus.

Der Worker stellt seinen Gesundheitsdienst nur innerhalb des Containers bereit.
`/healthz` bestätigt den laufenden Prozess und meldet `mode: idle`; `/readyz`
antwortet ohne produktiven Handler mit `503`. Der Compose-Worker-Healthcheck prüft
bewusst den Prozesszustand und ist keine Aussage, dass Jobs verarbeitet werden.
Eine Queue, ein GitHub-Webhook oder ein Collector wird dadurch nicht aktiviert.

Die Compose-CI baut und startet einen isolierten Stack, prüft die Healthchecks,
unterbricht Datenbank und MinIO und prüft jeweils Fehlererkennung und Erholung.
Ein eigener Compose-Projektname begrenzt das anschließende Entfernen der Testdaten.

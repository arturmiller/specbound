# 0009: GitHub App und lokale Webhook-Annahme

Der GitHub-Adapter verwendet eine explizit konfigurierte App-ID, Installation
und einen lokal eingebundenen privaten Schlüssel. Er prüft vor dem Abruf, dass
das angefragte Repository zur Installation gehört, und fordert ein auf dieses
Repository und Lesezugriff beschränktes Installationstoken an. Das Token wird
nicht persistiert. Repository-Metadaten werden über die bestehende Produkt- und
Teamautorisierung gelesen; eine Installation ist genau einer Specbound-
Organisation zugeordnet (`GITHUB_ORGANIZATION_ID`). Ohne diese Zuordnung oder
für andere Organisationen ist der Zugriff gesperrt.

Der Adapter liest GitHub-Metadaten, löst annotierte und leichte Tags auf Commits
auf und lädt einen am Commit festgehaltenen Snapshot. Unvollständige Git-Trees,
Symlinks, Submodule, mehr als 1000 Tree-Einträge und Snapshots über 20 MiB werden
als Fehler gemeldet. Diese Grenzen verhindern, dass ein unvollständiger Snapshot
als vollständig ausgegeben wird. Die API-Aufrufe verwenden ausschließlich
`https://api.github.com` und folgen keinen Redirects.

`POST /webhooks/github` akzeptiert höchstens 2 MiB, verifiziert die GitHub-
HMAC-SHA256-Signatur gegen die unveränderten Bytes und prüft die konfigurierte
Installation. Eine gültige Zustellung wird mit Delivery-ID, Event-Typ, Payload
und Specbound-Organisation in PostgreSQL gespeichert; erneute Zustellung
derselben ID erzeugt keinen zweiten Datensatz. Ohne Webhook-Secret ist der
Endpunkt gesperrt. Die Ereignisse bilden einen Eingang; Verarbeitung durch eine
Queue oder PR-Automation ist hier noch nicht implementiert.

## Lokale Konfiguration

Die App-Installation muss über `Contents: read` verfügen. Vor dem Start werden
`GITHUB_APP_ID`, `GITHUB_INSTALLATION_ID` und `GITHUB_ORGANIZATION_ID` gesetzt.
Der private PEM-Schlüssel bleibt außerhalb des Repositories. Für Compose wird
sein lokaler Pfad in `GITHUB_APP_PRIVATE_KEY_PATH` angegeben und das optionale
Overlay verwendet:

```sh
docker compose -f compose.yaml -f compose.github.yaml up --build
```

Das Overlay bindet den Schlüssel ausschließlich lesend in den API-Container
ein. `GITHUB_WEBHOOK_SECRET` muss denselben zufälligen Wert enthalten wie das
Secret der App auf GitHub. Schlüssel und Secret dürfen nicht ins Repository.
Der Lese-Endpunkt ist
`GET /products/{product_id}/repositories/{binding_id}/github` für ein GitHub-
Binding im jeweils berechtigten Team.

Signierte Testzustellungen lassen sich lokal ohne externen Dienst prüfen. Für
echte GitHub-Zustellungen muss der App-Webhook aktiviert und eine von GitHub
erreichbare HTTPS-Adresse eingerichtet werden. Eine lokale Weiterleitung wie
[Smee](https://docs.github.com/en/webhooks/testing-and-troubleshooting-webhooks/testing-webhooks)
kann dabei zum Testen dienen; der Weiterleitungsdienst sieht die übermittelten
Payloads. App-Installation und Lesezugriff allein aktivieren den Webhook nicht.

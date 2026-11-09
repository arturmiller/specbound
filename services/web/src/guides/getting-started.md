# Getting Started

Specbound kann lokal mit Docker Compose gestartet werden. API, Web, PostgreSQL und MinIO laufen auf dem eigenen Rechner; Cloud-Zugangsdaten sind dafür nicht erforderlich.

## Beispiel

Im Repository eine Python-Umgebung einrichten und mit dem folgenden Befehl die Entwicklungsabhängigkeiten installieren:

```sh
python -m pip install -r services/api/requirements-dev.txt
```

Anschließend den Gesundheitsendpunkt ohne laufende Dienste ausprobieren:

```sh
python services/api/examples/docs_examples.py start
```

Die Ausgabe enthält status: ok. Für die laufenden Dienste verwenden Sie docker compose up --build; das Portal ist danach unter localhost:5173 erreichbar.

## Lokaler Entwicklungslogin

Für einen lokalen Testanbieter ohne Cloud-Konto das separate Compose-Projekt starten:

```sh
docker compose -p specbound-local -f compose.yaml -f compose.local-auth.yaml up -d --build
```

Das Portal unter http://127.0.0.1:5173 öffnen. Beim Entwicklungsanbieter können local-developer und local-only verwendet werden. Nach der Anmeldung unter Einstellungen die erste Organisation erstellen und anschließend ein Team anlegen. Der Anbieter akzeptiert beliebige Zugangsdaten und ist ausschließlich für vertrauenswürdige Entwicklungsumgebungen ohne echte Geheimnisse geeignet.

## Einschränkungen

- Der Test ruft die API im Prozess auf und bestätigt nicht, dass Docker oder die Datenbank erreichbar sind.
- Für geschützte Funktionen ist ein passend konfigurierter OIDC-Provider erforderlich. Der Worker wartet ohne freigegebenen Job-Handler.

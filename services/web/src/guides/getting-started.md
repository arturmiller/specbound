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

## Einschränkungen

- Der Test ruft die API im Prozess auf und bestätigt nicht, dass Docker oder die Datenbank erreichbar sind.
- Für geschützte Funktionen ist ein passend konfigurierter OIDC-Provider erforderlich. Der Worker wartet ohne freigegebenen Job-Handler.

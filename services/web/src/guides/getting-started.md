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

Das Portal unter http://127.0.0.1:5173 öffnen. Beim Entwicklungsanbieter können local-developer und local-only verwendet werden. Eine neue Installation benötigt unter /settings eine Organisation und unter /teams ein Eigentümerteam. Ihre IDs werden serverseitig in .local/workspace/workspace.json als organizationId und defaultOwnerTeamId hinterlegt. Compose bindet dieses Verzeichnis schreibgeschützt ein; SPECBOUND_WORKSPACE_CONFIG_DIR kann das Hostverzeichnis ändern. Bei direktem API-Start zeigt SPECBOUND_WORKSPACE_CONFIG auf die JSON-Datei. Der Anbieter ist ausschließlich für vertrauenswürdige Entwicklungsumgebungen ohne echte Geheimnisse geeignet.

## Produkte und Anforderungen

Der Einstieg zeigt Produkte, Kataloge, Profile und Evidence Packs. Ein Produktmanifest definiert die zu prüfenden Repositories und eine genaue Profilversion. Ein Profil wählt geltende Controls aus einem Katalog. Evidence Packs beschreiben Datenverträge und starten beim Import keine Ausführung.

Ein Produkt öffnet Anforderungen. Die Produktauswahl liegt über den Tabs Anforderungen, Prüfungen und Geltungsbereich. Unter Anforderungen wählt man eine gespeicherte Prüfung; Nachweise, Einzelbewertungen und Findings hängen an den Controls. Ein Produktwechsel entfernt den Prüfstand des vorherigen Produkts. Fehlende Daten oder unvollständige Abdeckung bleiben ausdrücklich unbekannt.

Der Arbeitsbereich wird nicht aus Browserparametern oder der ersten Organisation abgeleitet. Bei ungültiger Konfiguration zeigt das Portal einen Einrichtungsfehler. Die bisherigen Verwaltungs- und Detailseiten bleiben über Weitere Funktionen und ihre direkten URLs erreichbar.

## Einschränkungen

- Der Test ruft die API im Prozess auf und bestätigt nicht, dass Docker oder die Datenbank erreichbar sind.
- Für geschützte Funktionen ist ein passend konfigurierter OIDC-Provider erforderlich. Der Worker wartet ohne freigegebenen Job-Handler.

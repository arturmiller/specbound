# Specbound

Das lebende Designboard verbindet 44 Portal-Screens in 9 Stories mit einer
interaktiven Systemarchitektur und einer Planung aus 11 Epics, 25 Features und
65 Tasks. Die Designboard-Portalabläufe sind ein Prototyp mit Beispieldaten;
die Umsetzung der Produktoberfläche ist in [Phase 1](docs/phase1-designboard-ui.md)
geplant.

## Lokal starten

### Produktdienste mit Docker Compose

Docker mit laufender Engine und Compose vorausgesetzt:

```sh
docker compose up --build
```

Die lokal gebauten Images heißen `specbound-api`, `specbound-web` und
`specbound-worker` und tragen standardmäßig den Tag `0.1.0-local`. Mit
`SPECBOUND_IMAGE_TAG` kann ein eigener Tag gesetzt werden.

PostgreSQL und MinIO werden lokal gestartet; der Migrationsdienst führt
`alembic upgrade head` aus, bevor die API startet. Daten bleiben in den
Compose-Volumes `postgres_data` und `minio_data` erhalten.
Die Zugangsdaten in der Compose-Datei sind ausschließlich für lokale Entwicklung.

Das Portal ist unter <http://localhost:5173> erreichbar; die API antwortet auf
<http://localhost:8000/healthz>. Die Dokumentation im Portal enthält fünf Kategorien
mit ausführbaren lokalen Beispielen und ihren Einschränkungen; die Quelldateien
liegen unter [Guides](services/web/src/guides/). Der Worker wartet, bis ein
freigegebener Job-Handler konfiguriert ist. Mit `docker compose down` werden
die Dienste beendet. Die Produktdienste sind ein erster technischer Grundaufbau.

`docker compose ps` zeigt den Zustand der Dienste. Die API meldet unter `/readyz`
nur dann Bereitschaft, wenn Datenbank, Migrationsstand und MinIO-Bucket verfügbar
sind. Der Web-Healthcheck prüft auch den API-Proxy. Der Worker-Healthcheck prüft,
ob sein Prozess lebt; seine interne `/readyz`-Antwort bleibt ohne Handler `503` und
behauptet damit keine Bereitschaft zur Job-Verarbeitung.

API und Worker schreiben strukturierte JSON-Logs. Unter
<http://127.0.0.1:8000/metrics> stehen lokale, aggregierte Jobzahlen und das
Alter des ältesten wartenden Jobs bereit. Der Endpunkt lässt sich mit
`METRICS_ENABLED=false` abschalten. Sicherung und Wiederherstellung für lokale
Compose-Projekte sind in [ADR 0026](docs/adr/0026-local-recovery.md) beschrieben.
Die optionale Zustellung von PR-Kommentaren und ihre Voraussetzungen stehen in
[ADR 0027](docs/adr/0027-pr-comment-delivery.md).
Commit-genaue GitHub-Checks sind in [ADR 0028](docs/adr/0028-commit-checks.md)
beschrieben.
Die geschützte Ansicht eines Assessment-Links erläutert
[ADR 0029](docs/adr/0029-assessment-report.md).
Die Suche über zugängliche Produkte, Packs und Findings ist in
[ADR 0030](docs/adr/0030-overview-search.md) beschrieben.
Ergebniszustände und die angezeigte Quellabdeckung erläutert
[ADR 0031](docs/adr/0031-unknown-and-coverage.md).
Agentenrechte und Governance-Pack-Freigaben beschreibt
[ADR 0032](docs/adr/0032-agent-credentials-and-approvals.md).

Für den Login muss ein öffentlicher OIDC-Client mit Code-Flow und PKCE sowie
ein eigener API-Resource-Identifier eingerichtet sein. Vor `docker compose up`
werden `OIDC_ISSUER`, `OIDC_JWKS_URL`, `OIDC_CLIENT_ID` und `OIDC_AUDIENCE`
als Umgebungsvariablen gesetzt. Der Provider muss RFC-9068-Access-Tokens und
den Resource-Parameter unterstützen. Ohne gültige Konfiguration bleiben
geschützte APIs gesperrt. Die genauen Anforderungen und Grenzen stehen in
[ADR 0002](docs/adr/0002-oidc-access-tokens.md).

### Portal mit lokalem Entwicklungslogin

Für einen vollständigen lokalen Einstieg ohne Cloud-Konto gibt es ein separates
Compose-Projekt mit einem **ausschließlich für Entwicklung geeigneten** OIDC-
Testanbieter. Es verwendet eigene Daten-Volumes und verändert die Volumes des
normalen Compose-Projekts nicht.

```sh
docker compose -p specbound-local -f compose.yaml -f compose.local-auth.yaml up -d --build
```

1. <http://127.0.0.1:5173> öffnen und **Anmelden** wählen. Diese Adresse ist
   als Redirect registriert; `localhost:5173` funktioniert dafür nicht.
2. Beim lokalen Testanbieter Benutzer `local-developer` und Passwort
   `local-only` eingeben und die Berechtigung mit **Continue** bestätigen.
3. Unter Teams einen Organisationsnamen eingeben und **Organisation erstellen**
   wählen. Anschließend stehen Teams, Produkte und Packs zur Verfügung.

Der Testanbieter akzeptiert beliebige Zugangsdaten und nutzt öffentlich bekannte
Entwicklungsschlüssel. Er ist keine echte Benutzerverwaltung und darf nur auf
einem vertrauenswürdigen lokalen Rechner ohne echte Geheimnisse oder produktive
Daten verwendet werden. Bei einem Neustart des Anbieters kann eine erneute
Anmeldung erforderlich sein. Die Organisation wird nur vom Benutzer angelegt;
ein Neustart verändert bestehende Daten nicht.

Zum Beenden (die Volumes bleiben erhalten):

```sh
docker compose -p specbound-local -f compose.yaml -f compose.local-auth.yaml down
```

### Öffentlicher Python-Lizenzscan als lokale Vorschau

Der lokale Entwicklungslogin kann um einen ausdrücklich aktivierten Worker für
öffentliche GitHub-Repositories ergänzt werden:

```sh
docker compose -p specbound-local -f compose.yaml -f compose.local-auth.yaml -f compose.license-scan.yaml up -d --build
```

Nach der Anmeldung ein Team und ein Produkt anlegen oder auswählen, unter
**Produkte → Quellen ansehen** ein öffentliches GitHub-Repository als
`owner/repository` verbinden und im Abschnitt **Öffentlicher Python-Lizenzscan**
den Git-Ref angeben und den Scan starten. Für einen ersten Versuch eignet sich
`fedragon/uv-workspace-example` mit Ref `main`. Der Zugriff benötigt kein
GitHub-Token; GitHub kann anonyme Aufrufe pro IP begrenzen.

Der Worker verarbeitet ausschließlich ausdrücklich gestartete öffentliche
Scans. Er liest erkannte Lockfiles der aufgelösten Git-Revision und Paketmetadaten
von öffentlichem PyPI, ohne Pakete zu installieren oder Repository-Code
auszuführen. Nur `uv.lock` wird derzeit ausgewertet. Andere Python-Lockfiles,
private Paketquellen, fehlende oder widersprüchliche Angaben und überschrittene
Limits bleiben unbekannt beziehungsweise werden als unvollständige Abdeckung
angezeigt. Lockfiles können Pakete für andere Umgebungen enthalten; ein Scan ist
kein Inventar der tatsächlich installierten Pakete.

Die fest hinterlegte Beispielrichtlinie erlaubt MIT, Apache-2.0, BSD-2-Clause,
BSD-3-Clause und ISC; andere bekannte Lizenzen ergeben `FAIL`, unklare
Informationen `UNKNOWN`. Das Ergebnis ist eine **Vorschau**, kein reguläres
Assessment, Finding oder freigegebenes Governance-Pack. Für den Scan spricht
der Worker nur die im Code festgelegten externen Dienste an; das Compose-Overlay
erzwingt selbst keine Netzwerk-Firewall und ist für lokale Entwicklung gedacht.
Allgemeine Image-, Secret- und Egress-Freigaben bleiben separat.

Die Scanansicht speichert Aufträge und Ergebnisse in den bestehenden lokalen
Compose-Volumes. Wird das Overlay nicht verwendet, bleiben neue Aufträge wartend,
bis ein entsprechender Worker aktiviert wird.

Für den regulären Anbieter wieder die `OIDC_*`-Variablen wie oben beschrieben
setzen und `docker compose up --build` ohne das lokale Overlay starten. Ohne
einen passenden Anbieter bleiben geschützte APIs weiterhin gesperrt. Die
Netzwerkentscheidung und Grenzen stehen in
[ADR 0033](docs/adr/0033-local-development-oidc.md).

MinIO stellt die S3-kompatible API lokal unter <http://127.0.0.1:9000> und die
Konsole unter <http://127.0.0.1:9001> bereit. Compose legt den Bucket
`specbound` beim Start an. Die voreingestellten lokalen Zugangsdaten sind
`specbound` / `local-dev-only`; sie können über `MINIO_ROOT_USER`,
`MINIO_ROOT_PASSWORD` und `BLOBSTORE_BUCKET` ersetzt werden. Einzelheiten zum
BlobStore und zum lokalen Vertragstest stehen in
[ADR 0008](docs/adr/0008-local-blobstore.md).

### Designboard

Voraussetzung: Node.js 22 oder neuer. Es gibt keine externen Laufzeitpakete.

```sh
npm run dev
```

Das Board läuft unter <http://127.0.0.1:4173>. Nach Quelländerungen den Server
neu starten; dabei wird die Anwendung neu gebaut.

```sh
npm run check
```

Prüft Build, JavaScript-Syntax, Originaldaten, Referenzen, Task-Abhängigkeiten
und Zustandsimport. `npm run build` erzeugt die statisch hostbare Site in `dist/`.

## Arbeitsstand sichern

- **Sicherung** exportiert Board-Positionen, Screen-Namen, Notizen, unplatzierten
  Notiztext, Ansicht und lokale Task-Markierungen als JSON.
- **Importieren** liest diese Sicherung oder bisherigen Board-JSON-Export.
  Fehlerhafte oder inkompatible Dateien werden vor der Übernahme zurückgewiesen.
- Der Speicherstatus zeigt, ob Browser-Speicherung funktioniert. Notizen werden
  nicht automatisch mit Git, GitHub oder anderen Geräten synchronisiert.
- **Änderungsauftrag kopieren** übergibt Feedback an den Chat. Die Schaltfläche
  versendet selbst keine Nachricht.

Die Sicherung enthält den Bearbeitungszustand. Darstellung und Produktinhalte
werden im Repository versioniert; die JSON-Sicherung ersetzt den Quellcode nicht.

## Aufbau

| Pfad | Verantwortung |
| --- | --- |
| `docs/original/specbound-designboard.html` | Bytegleich archiviertes Original |
| `designboard/data/` | Stories, Screens, Architektur und Entwicklungsplanung |
| `designboard/src/` | Portal-Demos, Canvas, Architektur/Planung und Speicherung |
| `designboard/index.html` | Gemeinsame Oberfläche der drei Arbeitsbereiche |
| `scripts/build.mjs` | Reproduzierbarer Build ohne externe Pakete |
| `tests/designboard.test.mjs` | Datenintegrität und Sicherungsformat |

Die erste Migration trennt Daten, Styles und Verhaltensbereiche. Der Build setzt
die JS-Bereiche in definierter Reihenfolge im bisherigen Laufzeit-Scope zusammen.
Weitere Modulgrenzen können schrittweise eingeführt werden.

## CI-Grundchecks

GitHub Actions prüft Python mit Ruff und API-Tests, das Web mit TypeScript und
ESLint sowie die PostgreSQL-Migration auf einer leeren Datenbank. Ein erfolgreicher
Lauf stellt Web- und Designboard-Build als Workflow-Artefakte bereit.

Weiterentwicklung und Prüfprotokoll: [Designboard pflegen](docs/designboard.md).

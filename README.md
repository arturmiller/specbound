# Specbound

Das lebende Designboard verbindet 44 Portal-Screens in 9 Stories mit einer
interaktiven Systemarchitektur und einer Planung aus 10 Epics, 17 Features und
49 Tasks. Die Portalabläufe sind ein Prototyp mit Beispieldaten.

## Lokal starten

### Produktdienste mit Docker Compose

Docker mit laufender Engine und Compose vorausgesetzt:

```sh
docker compose up --build
```

PostgreSQL wird lokal gestartet; der Migrationsdienst führt `alembic upgrade head`
aus, bevor die API startet. Daten bleiben im Compose-Volume `postgres_data` erhalten.
Die Zugangsdaten in der Compose-Datei sind ausschließlich für lokale Entwicklung.

Das Portal ist unter <http://localhost:5173> erreichbar; die API antwortet auf
<http://localhost:8000/healthz>. Der Worker läuft als eigener Prozess und wartet
bis zur späteren Einführung einer Job-Queue. Mit `docker compose down` werden
die Dienste beendet. Die Produktdienste sind ein erster technischer Grundaufbau.

Für den Login muss ein öffentlicher OIDC-Client mit Code-Flow und PKCE sowie
ein eigener API-Resource-Identifier eingerichtet sein. Vor `docker compose up`
werden `OIDC_ISSUER`, `OIDC_JWKS_URL`, `OIDC_CLIENT_ID` und `OIDC_AUDIENCE`
als Umgebungsvariablen gesetzt. Der Provider muss RFC-9068-Access-Tokens und
den Resource-Parameter unterstützen. Ohne gültige Konfiguration bleiben
geschützte APIs gesperrt. Die genauen Anforderungen und Grenzen stehen in
[ADR 0002](docs/adr/0002-oidc-access-tokens.md).

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

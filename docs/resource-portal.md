# Ressourcenportal

Der Einstieg `/` beziehungsweise `/products` zeigt die berechtigungsgefilterten Produkte des konfigurierten Arbeitsbereichs. Die Hauptnavigation enthält **Produkte, Kataloge, Profile und Evidence Packs**. Kataloge beschreiben Anforderungen; ein Profil wählt Controls und Parameter aus. Ein Produktmanifest bestimmt die konkrete Profilversion und die zu prüfenden Repositories. Ein Evidence Pack beschreibt verfügbare Capabilities und ihre Verträge.

Ein Produkt öffnet **Anforderungen**. Die Produktauswahl steht über den Tabs und bleibt in **Prüfungen** und **Geltungsbereich** erhalten. Ein Produktwechsel entfernt die Prüfung, Control-Auswahl und Filter des vorherigen Produkts. Globale Ressourcenlisten übernehmen keine Produktauswahl. Unter Anforderungen wählt man den aktuellen Konfigurationsstand oder eine gespeicherte Prüfung; die Nachweise, Einzelbewertungen und Findings hängen an den jeweiligen Controls. Ein gespeicherter Prüfstand behält seine damalige Konfiguration.

## Arbeitsbereich einrichten

Der Betreiber legt eine lokale JSON-Datei gemäß `contracts/phase4/workspace.schema.json` an. Die Organisation und das Eigentümerteam müssen bereits existieren; ihre IDs erhält man über die vorhandenen Verwaltungsseiten `/settings` und `/teams` beziehungsweise die berechtigten APIs. Diese Verwaltung ist vom alltäglichen Produktablauf getrennt.

```json
{
  "organizationId": "123e4567-e89b-12d3-a456-426614174000",
  "defaultOwnerTeamId": "123e4567-e89b-12d3-a456-426614174001"
}
```

Bei direktem API-Start verweist `SPECBOUND_WORKSPACE_CONFIG` auf den **Dateipfad**, nicht auf JSON-Inhalt. Unter Docker Compose legt man die Datei als `.local/workspace/workspace.json` ab. Alternativ setzt `SPECBOUND_WORKSPACE_CONFIG_DIR` das auf dem Host eingebundene Verzeichnis. Die API liest `/etc/specbound/workspace.json` aus dem schreibgeschützten Mount. `.local/` wird nicht versioniert. Nach geänderter Hostverzeichnis-Konfiguration die API mit `docker compose up -d api` neu erstellen; Änderungen am eingebundenen Dateiinhalt werden beim nächsten Abruf gelesen.

`GET /workspace` prüft Schema, tatsächliche Teamzugehörigkeit und Zugriff des angemeldeten Principals. Fehlende/ungültige Konfiguration ergibt 503, fehlender Zugriff 403. Browserparameter wie `?organization=...` ändern den Portal-Arbeitsbereich nicht. Es gibt keine Auswahl nach Datenbankreihenfolge und keine zusätzliche Berechtigung durch das Standardteam. OIDC, Teamrollen und Agentenrechte gelten unverändert.

## As Code und bestehende Links

Ressourcen werden über Repository, Ref-Typ, gewünschten Ref, Manifestpfad und erwartete Identität/Version registriert. Die Vorschau validiert die Struktur und Referenzen. Die Registrierung speichert eine feste Revision mit Manifest-, Commit- und Schemalinks. Mehrere Manifestpfade in einem Repository sind unabhängig registrierbar. Die Produktquellen bleiben von diesem Konfigurationsrepository getrennt. Eine Registrierung gibt keine Ausführung frei.

Bestehende `/assessments/{id}`-, `/findings?...`-, `/pr-checks?...`- und `/docs#docs/...`-Links bleiben erhalten und unterliegen ihren bisherigen API-Rechten. Im aufklappbaren Bereich **Weitere Funktionen** sind Findings, PR Checks und Administration erreichbar. Die frühere manuelle Produktverwaltung liegt unter `/legacy-products`; vorhandene explizite Produktansichten wie `/products?...&view=repository` bleiben im konfigurierten Arbeitsbereich erreichbar. Die Verwaltungsnavigation kann weiterhin Organisationen auswählen; diese Auswahl konfiguriert das Ressourcenportal nicht.

Die Browsertests nutzen einerseits gespeicherte API-/DB-Daten mit isolierter Testidentität, andererseits einen eigenen OIDC-Testanbieter mit PKCE und kryptografisch validierten Access Tokens. Diese Testdaten sind keine Live-GitHub-Scanbelege.

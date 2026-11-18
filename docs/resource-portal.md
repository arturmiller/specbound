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

### Katalog entfernen und wiederherstellen

Im Katalogdetail können Eigentümer **Katalog entfernen** und anschließend **Entfernen bestätigen** wählen. Die registrierte Revision wird archiviert und aus der aktiven Liste ausgeblendet. Unter **Entfernte Kataloge** bleibt sie auffindbar; **Katalog wiederherstellen** aktiviert genau denselben gespeicherten Stand ohne erneuten GitHub-Abruf.

Manifest, Commitlinks und die Bindung von ID/Version an unveränderte Inhalte bleiben erhalten. Bestehende Profile, Produkte und gespeicherte Prüfungen behalten ihre festen Referenzen; auch neue Prüfungen bestehender Produkte können weiterlaufen. Neue Profilregistrierungen benötigen einen aktiven Katalog. Ein erneuter Import oder eine Revisionsübernahme stellt einen archivierten Stand nicht stillschweigend wieder her. Die Aktionen verlangen Eigentümerrechte und werden mit Akteur, Zeitpunkt und Revision protokolliert. Dateien im Git-Repository werden nicht gelöscht.

Sind alle Registrierungen einer Katalog-ID und Version archiviert, gilt diese Sperre auch für einen anderen Commit mit unverändertem Kataloginhalt. Zuerst muss eine gespeicherte Registrierung ausdrücklich wiederhergestellt werden. Andere bereits aktive Registrierungen und neue Katalogversionen bleiben unabhängig davon nutzbar.

`DELETE .../resources/{revisionId}` archiviert einen Katalog; `POST .../resources/{revisionId}/restore` stellt ihn wieder her. `GET .../resources` listet aktive Ressourcen, `?include_archived=true` bezieht archivierte Stände ein. Direkte berechtigte Detailabrufe bleiben verfügbar. Migration `0028_catalog_archival` verhindert ein Downgrade, solange archivierte Kataloge existieren.

### Vorschau und Revisionsübernahme

Die Vorschau kann über **Abbrechen** beendet werden. Bei einer nicht rechtzeitig antwortenden Quelle wird der Ladezustand spätestens nach 45 Sekunden beendet und ein verständlicher Zeitlimitfehler angezeigt. Während der Registrierung wird kein Abbruch versprochen: Falls dort die Browseranfrage ihr Zeitlimit überschreitet, zuerst in der Ressourcenliste prüfen, ob die Registrierung bereits abgeschlossen wurde.

Im Ressourcendetail beziehungsweise im Produkt-Geltungsbereich können Organisationseigentümer **Neue Revision prüfen** wählen. Der gespeicherte gewünschte Ref wird erneut gelesen; optional kann ein neuer Ref mit ausdrücklichem Typ angegeben werden. Repository und Manifestpfad bleiben an die bisherige Quelle gebunden, ebenso die logische Ressourcen-ID. Die neue Version stammt aus dem Manifest.

Die Prüfung speichert nichts: Sie zeigt bisherigen und vorgeschlagenen Commit, Struktur-/Referenzprüfung, Control-Auswahl, Parameter-/Vertragsänderungen und tatsächlich gespeicherte Referenzen. Erst **Revision übernehmen** registriert den erneut validierten Stand. Commit und ein Digest der vollständigen geprüften Quellen-/Referenzkonfiguration müssen weiterhin übereinstimmen. Verschobene Release-Tags und geänderte Inhalte unter derselben ID/Version werden abgewiesen. Für inhaltliche Änderungen ist eine neue Manifestversion erforderlich.

Eine Katalog-/Profil-/Evidence-Pack-Übernahme registriert eine neue feste Revision. Sie schreibt keine bestehenden Produkt- oder Profilreferenzen um und erteilt keine Ausführungsrechte. Ein Produktmanifest muss eine neue Profilversion ausdrücklich referenzieren und anschließend selbst übernommen werden. Diese Produktübernahme aktualisiert Namen, Profil und aktuelle Repositoryauswahl atomar; künftig gestartete Prüfungen frieren den neuen Stand ein. Bereits eingereihte Prüfungen und gespeicherte Assessments behalten die alte Konfiguration.

Entfernte Produktquellen werden intern stillgelegt. Ihre IDs bleiben für alte Scan-/Nachweislinks erhalten, sie erscheinen jedoch nicht mehr als aktuelle Quellen und können keine neuen Scans erhalten. Migration `0027_repository_retirement` blockiert ein Downgrade, solange stillgelegte Quellen existieren, damit ein älterer Stand sie nicht versehentlich wieder aktiviert.

Jede erfolgreiche ausdrückliche Übernahme schreibt Akteur, Zeitpunkt, vorherige/neue Revision, Commits und Prüfdigest in das berechtigungsgefilterte Übernahmeprotokoll. Fehler lassen bisherigen Stand und Protokoll unverändert. Die API stellt dafür `POST .../resources/{revisionId}/check`, `POST .../resources/{revisionId}/adopt` und `GET .../resources/{revisionId}/adoptions` bereit. Prüfung und Übernahme verlangen Eigentümerrechte; leseberechtigte Benutzer und Agenten können das Protokoll ihrer sichtbaren Ressourcen lesen.

Eine Strukturänderung ist keine berechnete Bewertungsfolge. Regeländerungssimulation (#67), Deployment-Identität/Baseline (#65–#66) und Aktivierung/Reassessment (#68) bleiben gesonderte Vorhaben.

Ressourcen werden über Repository, Ref-Typ, gewünschten Ref, Manifestpfad und erwartete Identität/Version registriert. Die Vorschau validiert die Struktur und Referenzen. Die Registrierung speichert eine feste Revision mit Manifest-, Commit- und Schemalinks. Mehrere Manifestpfade in einem Repository sind unabhängig registrierbar. Die Produktquellen bleiben von diesem Konfigurationsrepository getrennt. Eine Registrierung gibt keine Ausführung frei.

Bestehende `/assessments/{id}`-, `/findings?...`-, `/pr-checks?...`- und `/docs#docs/...`-Links bleiben erhalten und unterliegen ihren bisherigen API-Rechten. Im aufklappbaren Bereich **Weitere Funktionen** sind Findings, PR Checks und Administration erreichbar. Die frühere manuelle Produktverwaltung liegt unter `/legacy-products`; vorhandene explizite Produktansichten wie `/products?...&view=repository` bleiben im konfigurierten Arbeitsbereich erreichbar. Die Verwaltungsnavigation kann weiterhin Organisationen auswählen; diese Auswahl konfiguriert das Ressourcenportal nicht.

Die Browsertests nutzen einerseits gespeicherte API-/DB-Daten mit isolierter Testidentität, andererseits einen eigenen OIDC-Testanbieter mit PKCE und kryptografisch validierten Access Tokens. Diese Testdaten sind keine Live-GitHub-Scanbelege.

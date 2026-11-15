# Phase 4 – Ressourcenportal und Governance als Code

Bestandsaufnahme: 15.11.2026. Ziel ist die Umsetzung des nach dem Rollenreview überarbeiteten Portalentwurfs.
Diese Datei beschreibt Planung und Unterschiede; die neue Portalimplementierung wird damit noch nicht geliefert.

## Vergleichsgrundlage

- GitHub `main`: `8213341` (nach aktuellem Fetch). Das produktive Quellmodell verwendet Organisationen/Teams, Produkte, Governance-/Provider-Packs und getrennte Reportansichten.
- Lokale funktionale Erweiterung: `f93a668` auf `issue-175-python-license-scan`, mit offenen PRs [#173](https://github.com/arturmiller/specbound/pull/173) und [#179](https://github.com/arturmiller/specbound/pull/179). Sie enthält zusätzliche Provider-Testlauf- und öffentliche Lizenzscan-Funktionalität einschließlich Repository-Assessments. Diese Arbeit ist noch nicht in `main` und wird nicht erneut geplant.
- Zielentwurf: `services/web/prototype-oscal.html`, mit `prototype-product.js`, `prototype-registry.js`, `prototype-review.css` und einer statischen Kopie des historischen Lizenzscan-Assessments. Der Entwurf ist lokal mit `npm run dev -- --port 5173` im Web-Verzeichnis erreichbar; er ist kein produktiver API-Client.
- Der aktuelle Rollenreview ist unter [Review](../reviews/prototype-role-review-2026-11-15.md) dokumentiert. Die dortige Umsetzung nach dem Review betrifft den Prototyp.

## Verbindliche Richtung aus dem Entwurf

Produkte sind Prüfgegenstände. Produktquellen und Governance-/Evidence-Quellen sind unterschiedliche Beziehungen, auch wenn sie technisch beide Git verwenden.
Die Ressourcenlisten heißen Produkte, Kataloge, Profile und Evidence Packs; der Einstieg ist Produkte, ohne zusätzliche Übersicht oder Einstellungen.
Organisationen und Teams werden aus dem vereinfachten Nutzerablauf ausgeblendet. Das ist keine Entscheidung, ihre gespeicherten Zugriffsgrenzen oder OIDC zu entfernen.

Ein Produkt verweist explizit auf ein Profil. Das Profil bestimmt Controls aus Katalogen; Subject-Typ-Matching allein bestimmt nicht, welche Controls ein Produkt erfüllen muss.
Im Produkt liegen Anforderungen, Geltungsbereich und Prüfungen. Unter Anforderungen sind Prüfungsauswahl, Control-Status, vollständige Einzelbewertungen und die tatsächlichen Nachweise verbunden.
Quellen werden als Repository, gewünschte Revision und Manifestpfad registriert; die tatsächlich verwendete Quelle wird zusätzlich mit vollständigem Commit gespeichert.
Änderungen entstehen durch versionierte Repository-Inhalte. Mehrere Manifestpfade erlauben mehrere Packs im selben Repository.

## Abweichungen und Wiederverwendung

| Bereich | Beobachtete Implementierung | Ziel und tatsächliche Lücke |
|---|---|---|
| Einstieg und Navigation | `portal-shell.jsx` bietet Übersicht, Produkte, Teams, Agenten, Packs, Findings, PR Checks, Evidence, Provider, Dokumentation, Einstellungen. `/` führt ohne Produktparameter zu Einstellungen. | Vier Ressourcenlisten plus Produktkontext. Vorhandene Deep Links/Reports bleiben über definierte Zugänge erreichbar; die Navigation wird bewusst vereinfacht. |
| Zugriffskontext | `teams.jsx` verlangt eine gewählte Organisation; Produkte benötigen ein verantwortliches Team. API und Datenmodell erzwingen diese Grenzen. | Unsichtbarer, eindeutig aufgelöster Kontext und geregelter initialer Produktimport. Das Ausblenden der UI ersetzt keine Autorisierung. Mehrdeutige Kontexte benötigen eine explizite Entscheidung. |
| Produkt als Code | Produkt-CRUD und Repository-Bindungen existieren; Produkte haben bisher Name und owner_team_id. | Produktmanifest, Schema, Quellrevision, stabile Ressourcenidentität und explizite Profilzuordnung fehlen. Bestehende Produkte benötigen einen Migrationszustand. |
| Katalog | Governance-Packs enthalten validierte Controls; `pack_catalog` ist die technische Packregistrierung, kein eigenständiges fachliches Katalog-/Profilmodell. | Katalogressource mit Gruppen und Control-Detailansicht; bestehende Governance-Controls und Regelverträge wiederverwenden bzw. gezielt adaptieren. |
| Profil | Weder Produktionsverträge noch Persistenz bieten ein eigenständiges Control-Profil. Applicability prüft Typ/Labels von Subjects. | Versioniertes Profil mit ausdrücklicher Control-Auswahl und Parametern, Referenzprüfung und Produktbindung. Das endgültige Format ist offen. |
| Manifestquelle | Pack-Import nimmt Repository, Tag und governance/provider an. Parser lesen `pack.yaml` aus der Snapshot-Wurzel; Release-/Aktivierungsidentitäten sind bisher repository-/tagbezogen. | Freier sicherer Manifestpfad, relative Packdateien, mehrere Ressourcen pro Repo/Ref und entsprechende Persistenz-/API-Migration. Bestehende Git-Snapshot- und Pinningmechanik nutzen. |
| Schemas | Versionierte GovernancePack-, Control- und EvidenceProviderPack-Schemas sowie Provider-Input-/Output-Schemas existieren. | Entwurfsbeispiele `specbound.design/v1` sind Vorschläge, keine bestätigten Verträge. Produkt-/Profilformat und Zuordnung zu OSCAL Catalog/Profile oder Adaptern müssen beschlossen werden; Laufzeit- und Berechtigungsverträge dürfen dabei nicht verloren gehen. |
| Evidence Packs | Provider-Pack-Import, Capabilities, Images, Schemas und getrennte Freigabezustände sind vorhanden. Testlauf-Reservierung ist Teil des offenen PR #173; allgemeine Credentials/Egress bleiben #51. | Manifestpfadbezogene Packliste und Verknüpfung zu benötigten Control-Capabilities. Keine automatische Ausführung oder Freigabe durch erfolgreiche Registrierung. |
| Profilgebundene Prüfung | Generische Regelbewertung und immutable Assessment-/Finding-Daten existieren. Der lokale öffentliche Scanner verwendet ein fest gepinntes Beispiel-Pack, kein Produktprofil. | Eine neue Prüfung muss den geltenden Produkt-/Profil-/Katalog-/Regelstand vorab auflösen und fixieren. Unsupported bleibt UNKNOWN/nicht bewertet. Vorhandene lokale Scan-Jobs aus #177/#178 integrieren. |
| Nachweisstand | Der Assessment-Report liefert Bewertungen und referenzierte Evidence; Inhalt, Herkunft und Gültigkeitszeiten sind bereits gespeichert. Auf dem lokalen Branch kennt öffentliche Evidence ihren tatsächlichen Erzeuger. | Produktzentrierte Darstellung und neue Profil-/Katalogquellen im Snapshot ergänzen. Historische fehlende Angaben bleiben unbekannt; keine rückwirkend erfundene Provenienz. Raw Evidence/Metadaten-Hashes sind wiederzuverwenden, nicht neu zu erfinden. |
| Control-Arbeitsplatz | Produktquelle/Discovery, Scanvorschau, Assessment-Bericht, Findingdetail und Evidence-Registry sind getrennte Ansichten. | Ein Control bündelt Auswahl der Prüfung, Status, alle Einzelbewertungen und Nachweise. Statusfilter, verständliche Leerzustände, Fokus-/Detailerhalt und revisionsgenaue Links sind durchgehend zu integrieren. |
| Änderungen an Quellen | Git-Tag-Pins und Packaktivierung existieren, aber keine allgemeine Revisionierung aller vier neuen Ressourcen. | Autorisierte Übernahme neuer geprüfter Manifestrevisionen mit Referenzprüfung und unveränderten historischen Assessments. Baseline-/Reassessment-Arbeit #65–#68 bleibt getrennt. |

### Codebelege für den Vergleich

- `services/web/src/portal-shell.jsx`, `teams.jsx`, `products.jsx`: Navigation, Organisation-/Teamkontext, Produktabläufe.
- `services/api/app/products.py`, `tables.py`: Produkt-/Repo-Bindungen und bestehende Persistenzgrenzen.
- `services/api/app/pack_catalog.py`, `pack_revisions.py`, `governance_pack.py`, `provider_pack.py`: registrierte Packs, Root-Manifeste, Freigaben und Schema-/Dateiprüfung.
- `contracts/v1`: vorhandene Produktionsverträge; keine eigenständigen Produkt-/Profilverträge.
- `services/api/app/applicability.py`, `rule_evaluation.py`, `snapshots.py`, `assessment_reports.py`: Matching, Evaluation und vorhandene historische Reportdaten.
- Nur im lokalen Erweiterungsstand: `public_license_assessment.py`, `public_license_scans.py`, `example_license_pack.py` und `public_license_worker.py`.

## Neue Phase und Arbeitspakete

Die bestehenden Phasen 1–3 werden nicht umnummeriert. Die neue Phase 4 ist ein eigener Umsetzungsschwerpunkt und verlangt nicht pauschal die Fertigstellung aller zurückgestellten Phase-3-Themen.

| Kennung | Vertikaler Durchstich | Modus | Abhängigkeit |
|---|---|---|---|
| P4-01 | Ressourcenverträge, Profilsemantik und Migration entscheiden | HITL | keine |
| P4-02 | Manifestdatei mit Repo/Ref/Pfad registrieren | AFK | P4-01 |
| P4-03 | Katalog importieren und gruppierte Controls ansehen | AFK | P4-02 |
| P4-04 | Profil auswählen, auflösen und nachvollziehen | AFK | P4-03 |
| P4-05 | Produktmanifest mit Produktquellen und Profil verbinden | AFK | P4-04 |
| P4-06 | Evidence Packs und Control-Capabilities verbinden | AFK | P4-02, P4-03 |
| P4-07 | Prüfung mit unveränderlichem Profil-/Nachweisstand | AFK | P4-05, bestehendes #178 |
| P4-08 | Vollständige Produkt-Control-/Evidence-Ansicht | AFK | P4-07 |
| P4-09 | Ressourcenportal, Einstieg und Produktkontext integrieren | AFK | P4-05, P4-06 |
| P4-10 | Neue As-Code-Revision prüfen und explizit übernehmen | AFK | P4-05, P4-06, P4-07 |

Jeder AFK-Task umfasst den notwendigen Persistenz-/API-/UI-Pfad und aussagekräftige Integrationsprüfungen. Zugänglichkeit, tatsächliche Anmeldung und Rechte gehören zu den Abnahmekriterien, nicht nur zu einer abschließenden Testaufgabe.

## Offene Entscheidungen vor autonomer Umsetzung

1. OSCAL Catalog/Profile direkt, eigene Verträge oder ein expliziter Adapter; executable Control-Regeln und existierende Providerverträge müssen dabei erhalten bleiben.
2. Ressourcenidentität, Referenzauflösung, Profilparameter und Versionskonflikte sowie Migration bestehender Root-Packs und Produkte.
3. Auflösung des internen Berechtigungs-/Eigentumskontexts bei ausgeblendeter Organisations-/Teamverwaltung, einschließlich mehrerer möglicher Kontexte.

Diese Punkte gehören in P4-01. Die Entwurfsbeispiele sind keine stillschweigende Architekturfreigabe.

## Abgrenzung zu vorhandenen Issues

- #174–#178 liefern den öffentlichen Lizenzscanner und seine vollständige Kette; neue Tasks verwenden diese Grundlage. #176 (Poetry) wird nicht erneut angelegt.
- #169–#171 und PR #173 betreffen synthetische Provider-Testläufe. Eine solche Observation wird nicht automatisch reguläre Evidence.
- #51 bleibt für allgemeine Image-/Secret-/Egress-Freigaben zuständig. Registrierung oder Schema-Erfolg ersetzt diese Entscheidung nicht.
- #65–#68 betreffen Deploymentidentität, Baseline, Änderungssimulation und Reassessment. Das Übernehmen einer Manifestrevision behauptet keine dieser Berechnungen.

## Reviewbare Quelle

Dieser Plan und der zugehörige Entwurf werden auf dem separaten Branch `design/resource-portal-phase-4` festgehalten. Produktive UI-/API-Änderungen sind nicht Bestandteil dieses Planungsbranches. Die später ergänzte Issue-Zuordnung dokumentiert die Veröffentlichung, keine laufende Statussynchronisierung.

# Phase 4: konkrete Entscheidungsvorlage für #181

Status: Beide fachlichen Empfehlungen wurden am 15.11.2026 bestätigt ("ja empfehlungen passen"). Verbindlicher Architekturentscheid: [ADR 0035](../adr/0035-oscal-resources-and-workspace.md); ausgearbeitete Verträge, validierte Beispiele und Migration: [contracts/phase4](../../contracts/phase4/README.md). Folgeaufgaben bauen nach Integration von #181 darauf auf.

## Entscheidung 1: OSCAL als Dateiformat für Kataloge und Profile?

**Empfehlung: Ja.** Kataloge und Profile werden als OSCAL-Dokumente registriert, statt ein ähnlich benanntes, aber inkompatibles eigenes Format zu etablieren. Produkte und Evidence Packs behalten Specbound-spezifische Manifeste. Ausführbare Regeln und ihre Bindung an Control-IDs erhalten einen expliziten versionierten Vertrag; Standardanforderung, konkrete Prüflogik und Nachweisangebot bleiben unterscheidbar.

Der erste unterstützte OSCAL-Umfang muss anhand offizieller, fest versionierter Schemas und gültiger Beispiele definiert werden. Für nicht implementierte Import-/Merge-/Modify-Funktionen werden verständliche Fehler geliefert. Schema-Gültigkeit allein bedeutet keine vollständig unterstützte Profilauflösung. Diese Phase beansprucht nicht, alle OSCAL-Modelle oder sämtliche OSCAL-Funktionen zu implementieren.

Vorteil: Austauschbare Kataloge/Profile und keine zweite proprietäre Darstellung derselben Grundbegriffe. Aufwand: Die bestehende ausführbare GovernancePack-Semantik braucht einen Adapter beziehungsweise eine eindeutige Ergänzung zu den OSCAL-Daten.

Alternative: zunächst eigene Produkt-/Katalog-/Profilmanifeste, nur begrifflich an OSCAL angelehnt. Geringerer Startaufwand, dafür spätere Abbildung und eine weitere Formatmigration.

Quellen: [NIST Catalog Model](https://pages.nist.gov/OSCAL/learn/concepts/layer/control/catalog/), [NIST Profile Model](https://pages.nist.gov/OSCAL/learn/concepts/layer/control/profile/).

## Entscheidung 2: Ein fester Arbeitsbereich je Installation für diese Phase?

**Empfehlung: Ja, zunächst ein aktiver, intern konfigurierter Arbeitsbereich.** Der vereinfachte Portalablauf benötigt keine Organisations-/Teamverwaltung. Die vorhandenen Datenbeziehungen und API-Autorisierung bleiben erhalten; neue Produkte erhalten eine innerhalb dieses Kontexts zulässige Eigentumszuordnung.

Die Implementierung entscheidet nicht anhand der ersten gefundenen Organisation oder eines Browserparameters, wer auf welche Daten zugreifen darf. Ein fehlender oder mehrdeutiger Kontext wird verständlich gemeldet und gibt keinen Datenzugriff frei. Die konkrete Konfigurations-/Provisionierungsform wird mit dem bestehenden OIDC-/Principal-Modell abgestimmt.

Vorteil: der vereinbarte einfache Produktablauf. Einschränkung: Der Wechsel zwischen mehreren unabhängigen Kunden-/Arbeitsbereichen ist in dieser Phase kein Nutzerablauf.

Alternative: Bereits jetzt mehrere Arbeitsbereiche für einen Benutzer unterstützen. Dann wird eine sichtbare oder anderweitig ausdrücklich ausgewählte Kontextzuordnung benötigt.

## Technische Ausarbeitung in #181

- Ein Produkt referenziert eine bestimmte Profilversion. Die gemeinsame Control-Auswahl und zulässige Parameter werden im Profil definiert; keine stillschweigenden produktlokalen Ausnahmen.
- Eine Quellenreferenz enthält Repository, relativen Manifestpfad und gewünschten Ref; jede tatsächlich verwendete Revision ist durch den vollständigen Commit bestimmt. Unterschiedliche Manifestpfade dürfen mehrere Ressourcen im selben Repository bezeichnen.
- Schemaauswahl erfolgt über bekannte, versionierte Verträge. Fremde Schema-URLs werden nicht automatisch geladen. ID-/Versionskonflikte und unauflösbare Referenzen werden abgewiesen.
- Neue Quellstände werden geprüft und ausdrücklich übernommen. Laufende und historische Bewertungen behalten ihren ursprünglichen Stand.
- Die bestehenden GovernancePack-/EvidenceProviderPack-Verträge werden gezielt migriert beziehungsweise adaptiert. Registry, Laufzeitfreigabe und erfolgreiche Bewertung sind unterschiedliche Zustände.
- Historische Scans ohne Profil-/Katalogangaben bleiben als solche lesbar; fehlende Herkunft wird nicht nachträglich ergänzt, als wäre sie damals erfasst worden.

Die technische Ausarbeitung liegt mit ADR, Schemas, Referenzbeispielen, Validierungsprüfungen und Migrationsplan vor. Der Pull Request zu #181 integriert diese Grundlage; #182 setzt danach die Registrierung und den Import um. Die beiden fachlichen Entscheidungen sind angenommen; eine produktive Implementierung des Imports ist damit noch nicht erfolgt.

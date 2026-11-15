# OSCAL-Kataloge/-Profile und ein fester Arbeitsbereich

Status: angenommen für Phase 4; die fachlichen Empfehlungen wurden am 15.11.2026 im Arbeitsgespräch bestätigt. Umsetzungstask: #181.

Kataloge und Profile verwenden native OSCAL-Dokumente. Produkte, Quellregistrierungen und ausführbare Control-Bindungen erhalten eigene versionierte Specbound-Verträge. EvidenceProviderPack behält seinen bestehenden v1alpha1-Vertrag. So bleiben austauschbare Anforderungen und ihre Auswahl von der konkreten Prüflogik und Nachweiserhebung unterscheidbar; ein zweites proprietäres Katalog-/Profilformat wird vermieden.

Die erste Stufe pinnt die offiziellen OSCAL-1.2.3-JSON-Schemas unverändert und unterstützt einen ausdrücklich begrenzten Profilumfang. Gültiges OSCAL außerhalb dieses Umfangs wird als nicht unterstützt zurückgewiesen, nicht teilweise interpretiert. Details, Beispiele und Referenzprüfungen stehen in [contracts/phase4](../../contracts/phase4/README.md).

Je Installation wird ein Arbeitsbereich mit bestehender Organisations-ID und zulässigem Eigentümerteam serverseitig konfiguriert. Die Oberfläche benötigt keine Organisations-/Teamverwaltung; OIDC, Principalauflösung, Teamrollen und bestehende API-Grenzen gelten weiter. Fehlende, ungültige oder widersprüchliche Konfiguration führt nicht zur Auswahl der ersten vorhandenen Organisation und gewährt keinen Zugriff.

## Folgen

- Produkt → genaue Profilversion → konkrete Katalog-/Bindingsquellen wird vor einer Bewertung auf vollständige Quellrevisionen fixiert. Profiländerungen wirken nicht rückwirkend auf Assessments.
- Bestehende GovernancePack-Manifeste werden über einen expliziten Legacy-Pfad adaptiert. Bisherige Providerfreigaben, Collectorverträge und synthetische Testläufe werden nicht durch die Ressourcenregistrierung ersetzt.
- Die technische Referenzprüfung in diesem Task beweist Verträge an Beispielen; API-Import, Persistenz, produktive Profilauflösung und Arbeitsbereichsprovisionierung folgen in den verknüpften vertikalen Tasks.
- Native OSCAL-Dokumente bedeuten in dieser Phase keine vollständige OSCAL-Profilverarbeitung und keine Unterstützung aller Assessment-/SSP-Modelle.

Eine nur begriffliche OSCAL-Anlehnung hätte den ersten Parser vereinfacht, aber später einen zusätzlichen Format- und Migrationspfad erfordert. Mehrere im Portal wechselbare Arbeitsbereiche werden für den aktuellen Produktablauf zurückgestellt.

# 0015: Collector-Request und -Response

Ein Collector-Request enthält `schemaVersion: 1`, ein Subject nach dem
bestehenden Subject-Vertrag, den Scope mit Produkt, Environment und
Target-Revision, eine `credentialsRef` sowie mindestens eine versionierte
Capability. Die Referenz ist entweder `null` oder ein Kennzeichner der Form
`credential:...`; sie darf keine Credentials enthalten. Ob ein Aufrufer eine solche
Referenz nutzen darf und wie sie aufgelöst wird, ist nicht Teil dieses Vertrags.

Eine Response enthält `schemaVersion: 1` und Beobachtungen mit Subject-ID,
Capability, identischem Scope, RFC-3339-Zeit, Provenienz und einem JSON-Wert.
Für jede angeforderte Capability muss mindestens eine Beobachtung vorliegen;
nicht angeforderte Capabilities und abweichende Subjects oder Scopes sind
ungültig. Der Subject-Scope im Request darf dem Request-Scope nicht
widersprechen.

Die Validierungsfunktionen erhalten ein bereits durch `load_provider_pack`
geprüftes Provider-Pack. Sie validieren Request und Response sowohl gegen die
gemeinsamen lokalen Schemas als auch gegen die vom Provider deklarierten
Runtime-Ein-/Ausgabe-Schemas. Jeder Beobachtungswert wird zusätzlich gegen das
Ausgabeschema seiner Capability geprüft. Fehlende oder unauflösbare Schemas
führen zu einem Fehler; die Prüfung lädt keine externen Referenzen nach.

Dieser Vertrag führt keinen Collector aus, bestätigt keine Vertrauenswürdigkeit,
prüft keine Secret-Berechtigung und bestimmt nicht die Aktualität einer
Beobachtung. Diese Aufgaben bleiben beim Runner und bei späteren
Evidence-/Autorisierungsaufgaben.

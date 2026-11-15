# Manifestbasierte Konfiguration – UI-Entwurf

Dieser Vorschlag gehört zum lokalen Portalentwurf `services/web/prototype-oscal.html`.
Er ist kein implementierter Backend-Vertrag und beansprucht keine OSCAL-Kompatibilität.

## Ressourcen

- Produkt: Prüfgegenstand mit Produktquellen und expliziter Profilreferenz.
- Katalog: gruppierte, wiederverwendbare Controls.
- Profil: explizite Auswahl von Controls aus einem Katalog. Parameter und mehrere Kataloge sind weitere Modellierungsfragen.
- Evidence Pack: Beschreibung der Nachweiserhebung und ihrer Laufzeit- und Datenverträge.

Die Ressourcenlisten sind unabhängig von einer Produktauswahl erreichbar; der Einstieg erfolgt über Produkte.
Produktbezogene Controls, Prüfungen und Nachweise bleiben in den Produktansichten.

## Quelle und Identität

Im Portal wird eine Quelle durch Repository, gewünschten Ref und relativen Manifestpfad registriert.
Beim Einlesen muss der Ref einmalig zu einem vollständigen Commit aufgelöst werden.
Der verwendete Stand besteht aus Repository, Manifestpfad und aufgelöstem Commit.
Die fachliche Ressourcen-ID steht im Manifest; unterschiedliche Manifestpfade dürfen nicht dieselbe ID unbemerkt überschreiben.

Ein Repository kann mehrere Ressourcen enthalten, etwa:

```text
products/audio-visualizer.json
catalogs/application.json
profiles/application-baseline.json
evidence/python-licenses/pack.json
evidence/cloud-config/pack.json
```

Relative Inhalts- und Schema-Dateipfade werden vom Manifestverzeichnis aus aufgelöst.
Für Pfade gelten gemeinsame Grenzen und Schutz vor Verlassen des erlaubten Verzeichnisses.
Ein Regel- oder Evidence-Repository wird durch die Registrierung nicht zum geprüften Produkt.

## Schemas und Referenzen

`apiVersion` und `kind` bestimmen ein von Specbound unterstütztes, versioniertes Schema.
Die Anwendung sollte Schemas aus einem bekannten Registry-Bestand auswählen; ein Manifest darf nicht beliebige externe Schemas nachladen lassen.
Produkte, Kataloge, Profile und Evidence Packs benötigen unterschiedliche Strukturverträge.
Der Prototyp zeigt vier Vorschläge unter `specbound.design/v1`; sie ersetzen die bestehenden Verträge nicht.

Nach der Strukturprüfung folgen Referenzauflösung und fachliche Prüfung:
Existiert die referenzierte Ressource in der gewählten Version? Gibt es die ausgewählten Control-IDs?
Passen benötigte und angebotene Nachweisarten zusammen?
Versionierte Referenzen müssen in einem Bewertungsstand auf konkrete Quellenrevisionen festgelegt werden.
Eine gültige Konfiguration bedeutet weder ein erfülltes Control noch eine Laufzeitfreigabe.

## Bestehender Stand und offene Umsetzung

GovernancePack und EvidenceProviderPack besitzen bereits JSON-Schema-Verträge unter `contracts/v1`.
Der aktuelle Governance-Parser liest `pack.yaml` aus der Snapshot-Wurzel.
Frei wählbare Manifestpfade, mehrere Packs pro Repository, Produkt- und Profilmanifeste sowie ihre durchgängige Referenzauflösung sind noch umzusetzen.
Zu entscheiden bleibt, ob Kataloge und Profile direkt OSCAL-Dokumente verwenden oder einen eigenen Konfigurationsvertrag erhalten.

Der Prototyp prüft lokal nur die im Schemavorschlag verwendeten Strukturmerkmale.
Er lädt keine Repository-Dateien, löst keine Revisionen oder Ressourcenreferenzen auf und speichert keine Registrierung.

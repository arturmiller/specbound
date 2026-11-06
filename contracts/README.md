# Gemeinsame Verträge

`v1/` enthält JSON Schemas (Draft 2020-12) für Subject, Fact und Evidence.
Dies sind erste Datenverträge; sie implementieren weder Discovery, eine
Evidence-Laufzeit noch Bewertungen oder Persistenz.

Zusätzlich beschreiben `governance-pack.schema.json` und
`governance-control.schema.json` das in [ADR 0011](../docs/adr/0011-governance-manifests.md)
festgelegte erste Governance-Manifestformat. Es ersetzt keine Regelbewertung.
`evidence-provider-pack.schema.json` beschreibt das Provider-Format aus
[ADR 0012](../docs/adr/0012-provider-manifests.md).

- **Subject** beschreibt ein typisiertes Prüfobjekt in einem Produktkontext.
- **Fact** hält einen benannten JSON-Wert über ein Subject fest. Ein vorhandener
  `null`-Wert ist ein tatsächlicher JSON-Wert, kein fehlendes Feld.
- **Evidence** beschreibt einen Nachweis für ein Subject und eine Capability;
  optional kann er auf mehrere Facts verweisen.

Alle drei Datensätze tragen eine ID, `schemaVersion`, `scope`, `provenance` und
`observedAt` (RFC-3339-Zeitstempel mit Zeitzone). IDs und Referenzen sind
nichtleere, nicht nur aus Leerzeichen bestehende Zeichenketten; ihre Erzeugung,
Eindeutigkeit und Existenz werden durch diese Schemas nicht geprüft.
`scope.productId` bezeichnet das Produkt; `environment` und `targetRevision`
können den Kontext bei Subjects und Facts genauer bestimmen und sind bei
Evidence erforderlich. `targetRevision` bezeichnet die beobachtete Revision
oder den Artefakt-Digest; das Format beweist keine Unveränderlichkeit.
`provenance.sourceRef` benennt die Quelle; Revision und Collector-Revision
können, soweit bekannt, zusätzlich angegeben werden. Secrets gehören nicht in
Datensätze oder Quellenreferenzen.

Die Schemas nutzen stabile URN-IDs. `common.schema.json` wird über seine URN
referenziert und muss in einer lokalen Schema-Registry bereitgestellt werden;
Validierung benötigt keinen Netzwerkzugriff. `format` ist bei JSON Schema
standardmäßig eine Annotation: Validatoren müssen die Prüfung von `date-time`
explizit aktivieren. Ein Beispiel dafür und für die lokale Registry enthalten die
Vertragstests in `tests/contracts/`. Bei inkompatiblen Änderungen eine neue
Version hinzufügen; bestehende Versionen nicht nachträglich umdeuten.

## Assessment-Zustände

`services/api/app/assessment.py` definiert PASS, FAIL, UNKNOWN und
NOT_APPLICABLE mit Begründung. Bei ungeklärtem Scope, fehlender Scope-Begründung,
fehlenden Nachweisen oder fehlendem Regelergebnis ergibt die Hilfsfunktion
UNKNOWN. Ein ausdrücklich als nicht anwendbar dokumentierter Scope ergibt
NOT_APPLICABLE auch ohne Nachweise; PASS und FAIL benötigen Nachweis-IDs und
ein begründetes, vom Aufrufer geliefertes Regelergebnis. Die Funktion sucht
keine Nachweise und prüft weder deren Existenz noch deren Aktualität oder Scope.
Diese Verantwortung bleibt bei den späteren Evidence- und Evaluations-Tasks.

Tests (mit den Entwicklungsabhängigkeiten der API installiert):

```sh
python -m unittest discover -s tests/contracts -v
```

# Evidence

Eine Observation beschreibt einen Wert für ein Subject und eine Capability. Gespeicherte Evidence ergänzt Scope, Herkunft, Collector-Revision und Gültigkeitsdauer. Abgelaufene Evidence darf kein aktuelles PASS begründen.

## Beispiel

Mit installierten Python-Entwicklungsabhängigkeiten eine Beispiel-Observation gegen den Collector-Vertrag und das Provider-Schema prüfen:

```sh
python services/api/examples/docs_examples.py evidence
```

Die Ausgabe meldet eine gültige Observation für net.internet-reachability/v1.

## Einschränkungen

- Das Beispiel validiert lokale Daten; es startet keinen Collector und speichert keinen Nachweis.
- Produktive Image-Freigaben, Secret-Zugriffe und Netzwerk-Egress sind noch nicht eingerichtet. Die aktuelle Bewertungsstrecke prüft Scanner-Abdeckung nur für OpenAPI-Subjects.

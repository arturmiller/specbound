# Packs

Governance-Packs enthalten Controls und deklarierte Capabilities. Provider-Packs beschreiben das Collector-Image und dessen Ein- und Ausgabe-Schemas. Ein Pack wird gegen einen festen Git-Commit gelesen.

## Beispiel

Mit installierten Python-Entwicklungsabhängigkeiten das mitgelieferte Governance-Beispiel validieren:

```sh
python services/api/examples/docs_examples.py packs
```

Die Ausgabe nennt das Pack com.acme.security und das Control SEC-NET-001.

## Einschränkungen

- Das Beispiel verwendet lokale Fixtures und verbindet kein Repository.
- Eine erfolgreiche Validierung oder ein gespeicherter Release-Pin ist keine Freigabe für den produktiven Einsatz.

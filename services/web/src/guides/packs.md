# Packs

Governance-Packs enthalten Controls und deklarierte Capabilities. Provider-Packs beschreiben das Collector-Image und dessen Ein- und Ausgabe-Schemas. Ein Pack wird gegen einen festen Git-Commit gelesen.

## Manifestquelle verbinden

Beim Verbinden werden Repository, Ref-Typ (Tag, Branch oder Commit), Ref und relativer Manifestpfad angegeben. Ohne Pfadangabe bleibt es bei `pack.yaml` für ältere Governance-Packs beziehungsweise `provider.yaml` für Evidence Packs. Zwei Pfade im selben Repository sind zwei getrennte Quellen. Relative Controls und Schemas müssen unterhalb des jeweiligen Manifestverzeichnisses liegen.

Das Portal zeigt die tatsächliche Manifestdatei, ihren unveränderlichen Commit und das zuständige Schema als Links. Der Ref wird beim Import einmal aufgelöst. Später bewegte Release-Tags sind ein Konflikt; Branch-Änderungen überschreiben keine gespeicherten Revisionen. Eine bestehende fachliche ID/Version darf keine geänderten Inhalte oder Abhängigkeiten bezeichnen. Dafür ist eine neue Version erforderlich.

Provider-Schemas werden zusammen mit der validierten Revision gespeichert. Alte Datensätze ohne Schema-Inhalt oder Quelldigest bleiben entsprechend erkennbar. Ein Import erteilt keine Laufzeitfreigabe und startet keinen Collector. Zugang zur konfigurierten GitHub-App und die bisherigen Organisationsrechte bleiben erforderlich.

## Beispiel

Mit installierten Python-Entwicklungsabhängigkeiten das mitgelieferte Governance-Beispiel validieren:

```sh
python services/api/examples/docs_examples.py packs
```

Die Ausgabe nennt das Pack com.acme.security und das Control SEC-NET-001.

## Einschränkungen

- Das Beispiel verwendet lokale Fixtures und verbindet kein Repository.
- Eine erfolgreiche Validierung oder ein gespeicherter Release-Pin ist keine Freigabe für den produktiven Einsatz.

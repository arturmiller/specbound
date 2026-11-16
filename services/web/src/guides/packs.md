# Packs

Governance-Packs enthalten Controls und deklarierte Capabilities. Provider-Packs beschreiben das Collector-Image und dessen Ein- und Ausgabe-Schemas. Ein Pack wird gegen einen festen Git-Commit gelesen.

## Manifestquelle verbinden

Beim Verbinden werden Repository, Ref-Typ (Tag, Branch oder Commit), Ref und relativer Manifestpfad angegeben. Ohne Pfadangabe bleibt es bei `pack.yaml` für ältere Governance-Packs beziehungsweise `provider.yaml` für Evidence Packs. Zwei Pfade im selben Repository sind zwei getrennte Quellen. Relative Controls und Schemas müssen unterhalb des jeweiligen Manifestverzeichnisses liegen.

Das Portal zeigt die tatsächliche Manifestdatei, ihren unveränderlichen Commit und das zuständige Schema als Links. Der Ref wird beim Import einmal aufgelöst. Später bewegte Release-Tags sind ein Konflikt; Branch-Änderungen überschreiben keine gespeicherten Revisionen. Eine bestehende fachliche ID/Version darf keine geänderten Inhalte oder Abhängigkeiten bezeichnen. Dafür ist eine neue Version erforderlich.

Provider-Schemas werden zusammen mit der validierten Revision gespeichert. Alte Datensätze ohne Schema-Inhalt oder Quelldigest bleiben entsprechend erkennbar. Ein Import erteilt keine Laufzeitfreigabe und startet keinen Collector. Zugang zur konfigurierten GitHub-App und die bisherigen Organisationsrechte bleiben erforderlich.

## Beispiel

Im Menü **Kataloge** werden native OSCAL-Kataloge mit Gruppen und Controls aus einer Manifestquelle registriert. Die optionale Vorschau prüft Struktur und lokale Prüfbindungen ohne Speicherung. Der anschließende Import kontrolliert den zuvor gesehenen Commit; ein zwischenzeitlich geänderter Branch wird abgewiesen und muss erneut geprüft werden.

Die Katalogansicht zeigt Anforderungen, Parameter, benötigte Nachweistypen und konfigurierte Regeln. Ein Control ohne automatisierte Prüfmethode bleibt sichtbar. Die konkrete Geltung für ein Produkt entsteht durch dessen Profilzuordnung; ein registrierter Katalog ist keine Bewertung. Bisherige Governance-Packs bleiben über den verlinkten Legacy-Katalog erreichbar.

Im Menü **Profile** werden native OSCAL-Profile registriert. Sie importieren in der ersten Stufe genau einen Katalog aus demselben Repository-Snapshot und wählen Controls ausdrücklich über ihre IDs aus. Unterstützte Parameteränderungen werden vor dem Speichern in die Prüfbindungen aufgelöst. Zuerst wird die passende Katalogversion registriert; fehlende oder widersprüchliche Referenzen sind ein Fehler. Profil und Katalog sind gegenseitig verlinkt, die tatsächlich eingebundenen Dateien besitzen eigene Commitlinks.

Ändere gemeinsame Anforderungen oder Parameter im Repository und erhöhe die jeweilige Version. Ein bestehendes Profil darf auch dann keine anderen Katalog-/Bindingsinhalte bezeichnen, wenn sich nur seine relative Importdatei geändert hat. Die Auswahl des geltenden Profils für ein Produkt ist ein eigener Konfigurationsschritt.

Mit installierten Python-Entwicklungsabhängigkeiten das mitgelieferte Governance-Beispiel validieren:

```sh
python services/api/examples/docs_examples.py packs
```

Die Ausgabe nennt das Pack com.acme.security und das Control SEC-NET-001.

## Einschränkungen

- Das Beispiel verwendet lokale Fixtures und verbindet kein Repository.
- Eine erfolgreiche Validierung oder ein gespeicherter Release-Pin ist keine Freigabe für den produktiven Einsatz.

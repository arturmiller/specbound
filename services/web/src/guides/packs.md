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

## Evidence Packs

Unter **Evidence Packs** lassen sich mehrere Provider-Manifeste desselben Repositorys über ihren jeweiligen Manifestpfad registrieren. Die Quellregistrierung verwendet den Typ `EvidenceProviderPack` und den bestehenden Manifestvertrag. Das Detail zeigt die gespeicherten Input-, Output- und Capability-Schemas, Image-Digest, deklarierte Berechtigungen sowie passende Controls. Der Abgleich unterscheidet genaue Capability-Versionen, fehlende Anbieter und inkompatible Versionen. Registrierung und Strukturvalidierung erteilen keine Ausführungs-, Secret- oder Egress-Freigabe. Allgemeine Freigaben werden separat umgesetzt (#51).

## Produkte als Code

Unter **Produkte → Produkt aus Manifest registrieren** wird ein Produktmanifest aus Git geprüft und übernommen. `spec.repositories` enthält nur die tatsächlichen Prüfquellen, `spec.profile` die genaue registrierte Profil-ID und Version. Die Herkunft des Produktmanifests ist davon getrennt. Im Produkt zeigt **Geltungsbereich** die Kette Produkt → Profil → Katalog sowie die ausgewählten Controls.

Der Server benötigt `SPECBOUND_WORKSPACE_CONFIG` als Pfad zu einer lokalen JSON-Datei mit `organizationId` und `defaultOwnerTeamId`; Organisation und Team müssen bereits existieren und zusammengehören. Fehlende Konfiguration wird nicht durch eine automatisch gewählte Organisation ersetzt. Authentifizierung und Teamrechte gelten weiterhin.

Bestehende Produkte bleiben **Ohne Profilzuordnung**. Gleiche Namen oder Repositorys erzeugen keine rückwirkende Zuordnung. Manifestverwaltete Produkte lassen sich nicht zusätzlich über die bisherigen Produkt-/Repository-Endpunkte umkonfigurieren. Für Änderungen wird eine neue Manifestversion veröffentlicht und anschließend ausdrücklich übernommen; die Übernahme neuer Revisionen folgt im eigenen Änderungsvorgang.

## Einschränkungen

Eine neue öffentliche Lizenzprüfung fixiert beim Start den Produkt-, Profil-, Katalog- und Bindungsstand aus der Registrierung. Profilparameter bestimmen die spätere Bewertung; die feste Beispielrichtlinie ersetzt keine ausdrückliche Produktkonfiguration. Der Worker liest die Regeln nicht erneut von einem beweglichen Branch.

Im Assessment bleiben alle ausgewählten Controls sichtbar. Der Python-Scanner liefert `python.package-license/v1` für beobachtete Python-Pakete. Andere Bindungen sind für diesen Lauf **Nicht unterstützt**, Controls ohne Methode oder Beobachtungen **Nicht bewertet**; ihr Ergebnis ist UNKNOWN. NOT_APPLICABLE entsteht nur aus einer tatsächlichen Einzelbewertung im passenden beobachteten Scope. Control-Anzahl und Paket-Einzelbewertungen sind getrennt.

Bestehende historische Scans erhalten keine nachträglichen Profilangaben. Neue Prüfungen bestehender unzugeordneter Produkte verwenden einen ausdrücklich gespeicherten Legacy-Beispielstand. Öffentliche Evidence behält ihren tatsächlichen Erzeuger und ihre Metadatenherkunft. Fehlende Beobachtungen und unvollständige Scans schließen keine Findings; die bisherigen Prozess- und Paketgrenzen gelten weiter. Die Grenze von 1.000 Einzelbewertungen wird vor der Bewertung auf vollständige Controls verteilt. Weitere ausgewählte Controls bleiben mit dem ausdrücklichen Grund **Bewertungsgrenze erreicht** als nicht bewertet und UNKNOWN sichtbar; ihre Findings werden nicht geschlossen.

- Das Beispiel verwendet lokale Fixtures und verbindet kein Repository.
- Eine erfolgreiche Validierung oder ein gespeicherter Release-Pin ist keine Freigabe für den produktiven Einsatz.

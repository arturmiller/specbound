# Phase-4-Verträge und validierte Beispiele

Grundlage: [ADR 0035](../../docs/adr/0035-oscal-resources-and-workspace.md). Diese Dateien definieren die Verträge für Ressourcenimport, Auflösung und Registrierung. API und Offline-Beispielprüfung verwenden dieselben Validatoren.

## Formate

| Ressource | Dokument und Identität |
|---|---|
| Katalog | Natives OSCAL 1.2.3 `catalog`, offizielles unverändertes JSON Schema. |
| Profil | Natives OSCAL 1.2.3 `profile`, offizielles unverändertes JSON Schema und der unten beschriebene unterstützte Verarbeitungsumfang. |
| Produkt | `product.schema.json`, `apiVersion: specbound.example/v1alpha1`, `kind: Product`. Produktquellen und genau eine Profil-ID/-Version. |
| Ausführbare Bindungen | `control-bindings.schema.json`, `kind: ControlBindings`. Referenz auf Katalog-ID/-Version und bestehende Governance-Control-Strukturen. Internes Konfigurationsartefakt, kein zusätzlicher Ressourcen-Tab. |
| Evidence Pack | Weiterhin `v1/evidence-provider-pack.schema.json`, `kind: EvidenceProviderPack`, einschließlich `approved-container`, unveränderlichem Image-Digest, Capabilities, Input-/Output-Schemas und Permissions. |
| Quellregistrierung | `resource-source.schema.json`, `kind: ResourceSource`. GitHub-Provider, Repository, gewünschter Ref, sicherer Manifestpfad, Ressourcentyp sowie erwartete ID/Version. Das ist die API-/Registrierungsbeschreibung, kein notwendiger zusätzlicher Wrapper um die native OSCAL-Datei. |
| Installationskontext | `workspace.schema.json`: Organisations-ID und Standard-Eigentümerteam-ID, serverseitig ausgewertet. |

Die `specbound.design/v1`-Beispiele des UI-Prototyps sind keine Produktionsverträge. Für Katalog und Profil gibt es insbesondere kein neues eigenes `kind: ControlCatalog`/`ControlProfile` als Ersatz für OSCAL.

## Identität, Version und Quellen

Bei OSCAL ist die Wurzel-UUID eine Dokumentidentität. Sie wird nicht als dauerhaft unveränderliche Ressourcen-ID verwendet. Die stabile fachliche ID steht genau einmal in `metadata.props` als `name: resource-id`, `ns: https://specbound.example/ns/resource`; die Version kommt aus `metadata.version`. Die verwendeten ID-/Versionsregeln entsprechen den neuen typisierten Referenzen. Änderungen von OSCAL-Inhalten aktualisieren UUID und `last-modified` nach den OSCAL-Regeln.

Für eigene Manifeste stehen ID/Version in `metadata.id`/`metadata.version`. Logische Identität ist `(Arbeitsbereich, Ressourcentyp, ID)`; eine Version ist unveränderlich. Physische Quellenprovenienz ist `(Provider, Repository, Manifestpfad, vollständiger Commit)` plus Inhalts-/Abhängigkeitsdigest. Eine andere Quelle darf eine bestehende ID/Version nicht unbemerkt mit anderen Inhalten oder anders aufgelösten Abhängigkeiten belegen. Gleicher Inhalt darf erneut beobachtet werden; Konflikte verlangen eine neue Version oder eine ausdrückliche Identitätskorrektur.

Gewünschter Ref und tatsächlich verwendeter Commit bleiben getrennt. Branch-Updates werden als Kandidat geprüft und explizit übernommen; bewegte Release-Tags bleiben nach den bestehenden Pinningregeln ein Konflikt. Eine Prüfung fixiert die gesamte aufgelöste Abhängigkeitsmenge. Ein unverändertes Profil mit durch geänderte relative Imports abweichendem Inhalt gilt nicht als dieselbe unveränderliche Profilversion.

Registrierte Manifestpfade sind relative Repositorypfade aus nichtleeren Segmenten mit Buchstaben (`A-Z`, `a-z`), Ziffern, Punkt, Unterstrich und Bindestrich. `.`/`..`-Segmente, leere Segmente, Laufwerkspfade und Prozentkodierung sind unzulässig. Der Dokumenttyp wird aus dem registrierten Vertrag bestimmt, nicht aus einer beliebigen Schema-URL im Inhalt.

## Erster unterstützter OSCAL-Umfang

Kataloge und Profile verwenden den gemeinsamen produktiven Validator unter `services/api/app/resource_contracts.py`; der Offline-Checker ruft denselben Code auf. Sie sind über `/organizations/{id}/resources` und die Menüs **Kataloge** und **Profile** registrierbar. Ein POST mit `preview=true` schreibt weder Quellpin noch Ressource. `X-Expected-Commit` schützt den anschließenden Import vor einem währenddessen geänderten Ref. Produktmanifeste verweisen ausdrücklich auf eine registrierte Profilversion und legen ausschließlich ihre eigenen Produktquellen fest.

`EvidenceProviderPack` ist im selben Quellendpunkt registrierbar und verwendet unverändert den vorhandenen v1-Parser. Die quellenseitige erwartete ID/Version erhält dafür die v1-Grenzen (ID bis 200 Zeichen, gültige Version ohne zusätzliche 128-Zeichen-Grenze); neue native Ressourcentypen behalten ihre engeren Grenzen. Quellkonfigurations-ID/-Version bleiben davon getrennt. Der Import speichert Datenverträge und deklarierte Berechtigungen, erteilt jedoch keine Laufzeitfreigabe. Der Capability-Abgleich prüft genaue Versionen; auf einer Packdetailseite wird die Kompatibilität dieses Packs unabhängig von anderen Anbietern dargestellt.

Vor einem Profil wird seine Katalogversion registriert. Der Profilimport liest Katalog und Bindungen aus demselben Snapshot wie die Profildatei und gleicht deren Inhaltsdigest mit der registrierten Katalogidentität ab. Inhaltsgleiche registrierte Definitionen an einer anderen Revision bleiben referenzierbar; die tatsächlich eingebundene Datei wird zusätzlich mit dem Commit des Profilimports verlinkt. Mehrdeutige oder abweichende Kataloginhalte werden abgewiesen. Die gespeicherte Profilauswahl enthält ausschließlich ausdrücklich ausgewählte Controls und aufgelöste Bindungsparameter; Änderungen der Abhängigkeitsmenge benötigen eine neue Profilversion.

`ResourceSource.spec.refType` kann `branch` (Standard), `tag` oder `commit` sein. Branch-Namen werden für GitHub als `heads/<Name>` aufgelöst, damit ein gleichnamiger Tag nicht ausgewählt wird ([GitHub-Commitvertrag](https://docs.github.com/en/rest/commits/commits#get-a-commit)). Der bestehende Ref-Längenbereich des Adapters beträgt 200 Zeichen.

- JSON-Inhalte und JSON-kompatibles YAML werden gegen die gepinnten JSON-Schemas validiert; der Offline-Beispielchecker liest JSON. Die vorhandenen Größen-/YAML-Schutzmaßnahmen gelten für den späteren Import weiter.
- Ein Profil importiert genau einen Katalog aus demselben gepinnten Repository-Snapshot. `href` ist ein relativer Dateipfad. `../catalogs/application.json` ist zulässig, sofern die normalisierte Auflösung innerhalb der Repository-Wurzel bleibt. Absolute URLs, Abfragen, Fragmente, Prozentkodierung und das Verlassen des Repositories werden nicht unterstützt.
- Auswahl ausschließlich über eine nichtleere `include-controls`-Auswahl mit eindeutigen `with-ids`. Keine stillschweigende Gesamtauswahl. Profile als Importquelle, mehrere Imports, Regex-Selektoren, `include-all`, `exclude-controls` und Child-Control-Auswahl werden zunächst explizit zurückgewiesen.
- `merge` ist ausdrücklich `as-is: true`, ohne weitere Kombinationsregeln. Gruppen und narrative Anforderungsinhalte stammen aus dem Katalog. Verschachtelte Gruppen sind zulässig; verschachtelte Controls werden vorerst zurückgewiesen.
- `modify` unterstützt ausschließlich `set-parameters` mit `param-id` und `values`. Nur eindeutige Control-lokale Parameter mit Werten werden verarbeitet; global/gruppenlokal definierte Parameter, Constraints, Selections und sonstige semantische Modifikationen werden zunächst zurückgewiesen. Parameter nicht ausgewählter Controls werden nicht importiert.
- Doppelte oder fehlende Control-/Parameter-IDs, unbekannte Auswahlziele, nach Anwendung des Profils noch wertlose ausgewählte Parameter und Bindungswidersprüche sind Fehler. Ein Profil darf fehlende Katalogstandardwerte ergänzen. Ein ausgewähltes Control ohne verfügbare ausführbare Bindung bleibt sichtbar und nicht automatisiert bewertet; es wird nicht als PASS ausgegeben.

Dies ist ein zugesicherter erster Verarbeitungsumfang, kein vollständiger OSCAL-Resolver. Der Beispielchecker liefert eine interne Auswahlprojektion, kein als OSCAL ausgegebenes vollständig aufgelöstes Katalogdokument. Eine spätere Erweiterung benötigt weitere Semantiktests.

Beim GitHub-Ressourcenimport werden nur die vom Parser benötigten Manifest-, Import-, Binding-, Schema- und Testdateien aus einem gepinnten Baum gelesen. Fremde Repositorydateien werden nicht heruntergeladen. Der resultierende unveränderliche Snapshot enthält genau die gelesenen Dateien; bestehende Ref-/Versionsfences sowie Pfad-, Symlink- und Größenprüfungen gelten weiterhin. Ein gemeinsames Netzwerkzeitbudget beendet weitere Abrufe nach 30 Sekunden; Quellzeitüberschreitungen ergeben HTTP 504.

## Prüflogik und Parameter

Der native Katalog benennt die Bindungsdatei über `metadata.links` mit `rel: specbound-control-bindings` und einem relativen `href`. Die Datei liegt im selben Snapshot. Es wird keine Prüflogik aus dem Internet nachgeladen und kein Quellcode ausgeführt. Fehlt eine Bindungsdatei, bleibt der Katalog als Anforderungskatalog verwendbar.

Bindings referenzieren die exakte fachliche Katalog-ID/-Version; eine Bindung verwendet die bestehende Control-ID, `target`, `requiredEvidence` und `assertions`. Die Compile-Projektion führt wieder zu diesen bestehenden Governance-Control-Strukturen. Zur Parametrisierung gibt es zwei explizite Referenzfelder:

- `expectedParameter` an `equals` liest genau einen OSCAL-Parameterwert als JSON-Skalar und ersetzt ihn durch `expected`. Beispiel: OSCAL-Wert `"true"` wird zu Boolean `true`. Gleichzeitig `expected` und `expectedParameter` ist ein Fehler.
- `allowedParameter` an `spdx-allowlist` übernimmt die OSCAL-Werteliste als `allowed`. Gleichzeitig `allowed` und `allowedParameter` ist ein Fehler. Der SPDX-Operator kommt aus dem separaten Lizenzscan-Branch/PR #179; der Basiskern wird hier nicht um diesen Operator erweitert.

Unterstützte Operatoren sind `equals`, `exists`, `all`, `any` und der genannte SPDX-Operator nach Integration seiner Grundlage. Neue Bindungen mit unbekannten Operatoren, fehlerhaften Operanden, mehrdeutigen Parameterreferenzen oder ungültigen Feldpfaden werden abgelehnt. Auch die expandierten Parameterwerte werden erneut gegen das Bindungsschema geprüft. Das Verhalten alter Legacy-Packs wird nicht rückwirkend umgedeutet. Erwartungswerte in Profilen sind Konfigurationswerte und keine selbst erhobenen Nachweise.

## Ein Arbeitsbereich, bestehende Autorisierung

Die spätere API liest eine vom Betreiber angegebene lokale Konfigurationsdatei über `SPECBOUND_WORKSPACE_CONFIG`. Vor Zugriff müssen Organisations-ID und Standardteam existieren und das Team zu dieser Organisation gehören. Falsche oder fehlende Konfiguration führt zu einer eindeutigen Nichtverfügbarkeit; es gibt weder Browser-Overrides noch eine Auswahl des ersten gefundenen Datensatzes.

Der eingeloggte Principal benötigt weiterhin die vorhandene Berechtigung für den jeweiligen Lese-/Schreib-/Freigabevorgang. Ein Standardteam weist Eigentum zu, erteilt aber keine Mitgliedschaft oder Rolle. Ein Benutzer mit Rechten ausschließlich in einer anderen Organisation erhält durch die Installationskonfiguration keinen Zugriff. Provisionierung und Betreiberkonfiguration sind vertrauenswürdige Einrichtungsschritte, nicht Funktionen der normalen Produktansicht. Die Schema-/Beispieltests ersetzen die nachfolgenden Datenbank- und API-Autorisierungstests nicht.

## Migration und Kompatibilität

| Bestand | Übergang |
|---|---|
| Root-`pack.yaml` | Bestehender GovernancePack-Parser bleibt als Legacy-Vertrag verfügbar. Explizite Konvertierung erzeugt einen neuen nativen Katalog, ein Profil mit ausdrücklicher Control-Auswahl und eine Bindungsdatei. Alte Commits und Freigaben werden nicht überschrieben. |
| Root-`provider.yaml` | EvidenceProviderPack-Format bleibt unverändert. Der neue frei wählbare Manifestpfad erweitert die Quellreferenz; aus der Manifest-Unterwurzel wird ein geeigneter Snapshot für den bisherigen Parser bereitgestellt. JSON ist als JSON-kompatible YAML-Datei lesbar. |
| Release-/Aktivierungsdaten | Repository-/Tag-Identitäten werden manifestpfadbezogen erweitert. Bestehende Root-Manifestpfade werden anhand des gespeicherten Packtyps zugeordnet; Mehrdeutigkeiten sind vor Migration aufzulösen. Aktive Revisionen und Freigaben bleiben an ihren ursprünglichen Inhalt gebunden. |
| Bestehende Produkte | Ihre IDs und Repository-Bindungen bleiben erhalten. Sie werden zunächst ausdrücklich als ohne Profilzuordnung ausgewiesen; der Betreiber/Benutzer bindet ein geprüftes Produktmanifest und Profil. Kein automatisches Profil aus Subject-Typen oder vorhandenen Findings. |
| Historische Assessments/Evidence | Ursprüngliche Regel-, Produkt- und Erzeugerinformationen bleiben unverändert. Fehlende Profil-/Katalog-/Erzeugerversionen werden nicht nachträglich erfunden. |
| Provider-Testläufe | Synthetische Observationen bleiben getrennt. Eine Ressourcenregistrierung macht sie weder zu regulärer Evidence noch zu einer Ausführungsfreigabe. |

Die Datenbank-/API-Migration erfolgt in den vertikalen Folgeaufgaben, mit Upgrade- und Bestandsdatentests. Kein Löschen bestehender Organisationen, Teams, Autorisierungsdaten oder Bewertungen.

## Validierung ausführen

```sh
uv run --no-project --with-requirements services/api/requirements-dev.txt python contracts/phase4/validate_examples.py
uv run --no-project --with-requirements services/api/requirements-dev.txt python -m unittest discover -s tests/contracts -v
```

Die offiziellen Schemas liegen unverändert unter `contracts/oscal/1.2.3`; `sources.json` enthält Release-URLs und SHA-256-Pins. Die offline ausgeführten Beispiele benötigen keinen Repositoryzugriff und keine Credentials. Unicode-Patterns der offiziellen Schemas werden mit der gepinnten `regex`-Bibliothek geprüft, nicht entfernt.

Die Beispiele enthalten einen nativen Katalog, ein natives Profil mit Parameteränderung, ein Produkt, zwei unterschiedliche Evidence-Pack-Manifestpfade im selben Beispielrepository, Quellregistrierungen und den Arbeitsbereichskontext. Dummy-Image-Digests in Fixtures sind keine Laufzeitfreigaben.

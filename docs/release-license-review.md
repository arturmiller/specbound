# Lizenzprüfung für Specbound-Releases

Das Release umfasst den gebauten Browser-Client sowie die API- und Worker-Images.
Bei einem zusätzlichen Image oder Installationspaket muss die freigebende Stelle
auch dessen Inhalte prüfen. Die Entwicklungs-Compose-Dateien starten zusätzliche
Dienste mit eigenen Lizenzen.

Für den eigenen Code von Portal, API und Scanner ist Apache-2.0 vorgesehen.
Vor der Veröffentlichung sind die Rechte an den Beiträgen und der genaue Umfang
der Lizenz zu bestätigen. Die Freigabe dokumentiert die Lizenzdatei und die
Hinweise für mitgelieferten Drittcode. Die geschützte Referenz auf diese Entscheidung
wird als `projectLicenseEvidence` in der Release-Prüfung hinterlegt.

## PR-Prüfung und Freigabe

Registriere den [Lizenzkatalog](../contracts/phase4/examples/catalogs/license-controls.json),
das [Profil für Kundenauslieferung](../contracts/phase4/examples/profiles/license-distribution.json)
und das [Specbound-Produktmanifest](../contracts/phase4/examples/products/specbound-license.json)
als Quellen. Übernimm das Manifest am vorhandenen Produkt, falls das Repository
schon gebunden ist. In der Produktrevision bestimmt `spec.licenseUse` den Einsatz.
Für `internal` oder `saas` kann das Produkt das
[Profil für den Serverbetrieb](../contracts/phase4/examples/profiles/license-server.json)
mit dem [Anwendungskatalog](../contracts/phase4/examples/catalogs/application.json)
verwenden. Beide Profile sind Beispiele für Unternehmensregeln.
Das Auslieferungsprofil erlaubt zusätzlich `MIT-0` und `PSF-2.0`.
Bei PSF-2.0 gehören Lizenztext und Copyright-Hinweise in die Auslieferung.

### Schwache Copyleft-Lizenzen bei unveränderter Bibliotheksnutzung

Der Lizenzkatalog enthält die Control-Erweiterung `PY-LIC-001.1`. Das
Auslieferungsprofil 1.2.0 wählt sie aus und erlaubt darüber `LGPL-3.0-only` und
`MPL-2.0`, sofern das Produkt diese Pakete als unveränderte Bibliotheken nutzt.
Die Regel legt die Organisation im Profil fest. Das Produkt erklärt in
`spec.implementedRequirements`, dass es die Bedingung erfüllt. Es kann nur
Controls erklären, die sein Profil auswählt. Eine Lizenz außerhalb der
Profilparameter kann es also nicht selbst freigeben.

Für ein betroffenes Paket ergibt `PY-LIC-001` nur dann PASS, wenn

- das Produkt `PY-LIC-001.1` erklärt,
- das Paket im Lockfile aus PyPI stammt und
- jede gesperrte Paketdatei per SHA-256 mit der Datei auf PyPI übereinstimmt.

Die Begründung im Bericht nennt das Control, das Produkt, den Commit der
Produktdefinition und die Profilversion. `PY-LIC-001.1` wird je Paket bewertet.
Für Pakete, die die Ausnahme nicht brauchen, ist das Ergebnis „nicht anwendbar“.
Ob Dateien dieser Lizenzen direkt in den eigenen Quellcode kopiert wurden,
prüft der Lockfile-Scan noch nicht.

In `spec.repositories[].paths` legt das Produkt fest, welche Ordner zu ihm
gehören. Nur Lockfiles unter diesen Ordnern werden bewertet. Andere Lockfiles im
Repository zeigt der Bericht als außerhalb der Produktpfade an. Ohne `paths`
gehört das ganze Repository zum Produkt.

Liegt das Produktmanifest im Repository des Pull Requests, liest der PR-Check
`paths` und `implementedRequirements` am Commit des Pull Requests. Eine Änderung
wirkt also schon im Pull Request, der sie einführt. Profil und Katalog kommen
immer aus den registrierten Versionen der Organisation. Ändert der Pull Request
die Produkt-ID oder verweist er auf eine andere Profilversion, oder ist das
Manifest ungültig, gelten keine Erklärungen aus dem Pull Request.

Mit `allowApprovedUse: true` erlaubt die SPDX-Regel belegte Freigaben. Der
Organisationseigentümer öffnet im Bericht die Paketbewertung und hinterlegt
Begründung, erfüllte Auflagen oder Vertragsumfang, einen geschützten HTTPS-Nachweis
und gegebenenfalls das Ablaufdatum. Der Bericht zeigt die Entscheidung und ihre
Begründung. Der Nachweislink ist nur für den Organisationseigentümer abrufbar.
Vertrauliche Vertragsdetails gehören in die geschützte Ablage.

Die Freigabe bindet das Produkt, die Repository-Zuordnung, die Paketversion und
Artefakthashes, die Kontrolle, die Profilrevision und die Nutzungsart. Ein neuer
Prüflauf berücksichtigt die Freigabe. Bei aktiviertem PR-Worker kann eine aktuelle
fehlgeschlagene Prüfung für denselben Commit neu eingeplant werden. Der gespeicherte
Bericht bleibt zeitbezogen abrufbar. Der GitHub-Check überprüft erfolgreiche
Ergebnisse regelmäßig erneut und berücksichtigt dabei Ablauf und Widerruf.

Der Lockfile-Scan bewertet alle referenzierten Dateien. Bei einem fertigen
Wheel zählt die hash-geprüfte Lizenzangabe im Wheel. Bei alten oder dynamischen
Metadaten kann der Scanner die Lizenz des Quellarchivs über eine mitgelieferte
Lizenzdatei belegen. Neben dem exakten Abgleich von Apache-2.0- und MIT-Texten kann der Worker mit
dem Buildziel `license-scan` ScanCode einsetzen. Ein einzelner vollständiger
Lizenztext muss mit der Deklaration im selben Archiv übereinstimmen. Der
Nachweis speichert Dateiname und SHA-256 sowie bei ScanCode Version, Regel
und Zeilenbereich. Der Befund gilt für dieses Archiv. Ein offener
Dateinachweis erzeugt einen blockierenden Verstoß. Für die Auslieferung sind
die tatsächlich gebauten Artefakte maßgeblich.

### Geprüfte Paketdateien und Auslieferungsauflagen

Die manuell geprüften Lizenznachweise gelten jeweils für eine bestimmte Datei
aus PyPI. Specbound verifiziert deren SHA-256 und zeigt die Fundstelle.

- [boolean.py 5.0](https://pypi.org/project/boolean.py/5.0/) deklariert
  BSD-2-Clause. `LICENSE.txt` enthält die Bedingungen, `README.rst` nennt
  dieselbe SPDX-Kennung und der Änderungsverlauf verweist auf die Dokumentation.
- [python-dateutil 2.9.0.post0](https://pypi.org/project/python-dateutil/2.9.0.post0/)
  erlaubt BSD-3-Clause für den gesamten Code. Die Datei `LICENSE` im Wheel
  und im Quellarchiv nennt Apache-2.0 zusätzlich für einen Teil des Codes.
- [certifi 2026.11.20](https://pypi.org/project/certifi/2026.11.20/) nennt
  MPL-2.0 im Quellarchiv und im Wheel. Für die Kundenauslieferung sind
  Lizenzhinweise und der Zugang zum passenden Quellcode des ausgelieferten
  MPL-Bestandteils zu belegen. Das betrifft insbesondere das mitgelieferte
  Zertifikatspaket. Siehe [Mozilla MPL FAQ](https://www.mozilla.org/en-US/MPL/2.0/FAQ/).
- `psycopg` und `psycopg-c` (LGPL-3.0-only) sind über `PY-LIC-001.1` zulässig,
  wenn die Auflagen für das konkrete Artefakt erfüllt sind. API und
  Worker bauen die C-Erweiterung aus dem versionierten Quellarchiv und
  laden Debian-`libpq5`. Die Laufzeitpakete aus Debian gehören ins
  Image-Inventar. Dokumentiere
  die mitgelieferten Lizenztexte und Hinweise, den passenden Bibliotheksquellcode
  und den Weg, wie Empfänger eine geänderte Bibliothek mit der Anwendung
  einsetzen können. Prüfe auch, dass die Auslieferungsbedingungen Änderungen
  an den Bibliotheksteilen und Reverse Engineering zu deren Fehlersuche
  zulassen. Das Binary-Wheel bleibt in der Entwicklungsgruppe und im
  universellen Lockfile. Siehe [LGPL-3.0, Abschnitt 4](https://www.gnu.org/licenses/lgpl-3.0.html)
  und [Psycopg-Dokumentation zur lokalen Installation](https://www.psycopg.org/psycopg3/docs/basic/install.html#local-installation).
- `pywin32` steht mit Windows-Marker im universellen Lockfile. Das untersuchte
  Windows-Wheel enthält mehrere Lizenzdateien, darunter LGPL-2.1 für
  `adodbapi`. Der universelle Scan führt den offenen Befund weiter. Für
  Linux-Auslieferungen hält das Inventar der gebauten Artefakte fest, welche
  Komponenten tatsächlich dazugehören.

Die Lizenznachweise für `certifi` und `psycopg` ergänzen die Entscheidung
über die Kundenauslieferung. Die dokumentierte Erfüllung der Auflagen muss
für das jeweilige Paket und das freizugebende Artefakt hinterlegt werden.

## Gebaute Artefakte prüfen

Erzeuge den Portal-Build mit `npm ci` und `npm run build` in `services/web`.
Der Build enthält ein Inventar der eingebundenen npm-Pakete mit den Hashes der
JavaScript-Dateien. Baue API und Worker aus der zu prüfenden Revision und exportiere
die auszuliefernden Images mit `docker image save`. Der Release-Check katalogisiert
alle ausgelieferten Schichten der Archive mit [Syft](https://github.com/anchore/syft)
und verifiziert den Portal-Build anhand seines Inventars. `uv` und die Lockfiles
liegen in der Build-Stufe. Die finale Stufe übernimmt die installierten Abhängigkeiten.
Bei einem Release des Workers mit ScanCode gehört das so gebaute Worker-Image
in die Release-Prüfung.

Beispiel für den Aufruf aus `services/api` mit installierten Projektabhängigkeiten
und geprüft installiertem Syft.

```sh
python -m app.release_license_review --portal ../web/dist \
  --api-image api.tar --worker-image worker.tar \
  --policy distribution-policy.json --output release-license-review.json \
  --summary release-license-review.md
```

Eine erste Prüfung kann mit dieser Richtlinie beginnen.

```json
{
  "use": "customer-distribution",
  "allowed": ["MIT", "MIT-0", "Apache-2.0", "BSD-2-Clause", "BSD-3-Clause", "ISC", "PSF-2.0"],
  "reviewedArtifacts": {}
}
```

Der Bericht enthält für `portal`, `api-image` und `worker-image` je einen
SHA-256-Digest und die gefundenen Komponenten. Wenn Syft eine Lizenzdatei oder
Paketmetadaten im Image ermittelt, enthält der Bericht deren Fundstelle. Die
Markdown-Zusammenfassung zeigt fehlende Freigaben und offene Komponenten.
Ungeklärte Lizenzen zählen als blockierende Verstöße.
Die freigebende Stelle bestätigt
für jeden Digest die Vollständigkeit des Inventars einschließlich eingebetteter
Bibliotheken und mitgelieferter Assets sowie die erfüllten Lizenzhinweise und
weiteren Auflagen.

Die geschützte Richtlinie kann unter `reviewedArtifacts` je Artefakt die Felder
`sha256`, `inventoryEvidence` und `noticeEvidence` enthalten. Für eine
abweichende oder ungeklärte Lizenz verweist `componentApprovals` vom
SPDX-Paket-ID im Bericht beziehungsweise von `name@version` bei Portal-Paketen
auf die geprüfte komponentenspezifische Freigabe für die Auslieferung. Die
Freigabedatei stammt aus dem vertrauenswürdigen Release-Prozess. Der Check
prüft ihre Zuordnung zu den Artefakten. Die fachliche Entscheidung verbleibt
bei der freigebenden Stelle.

Exitcode `0` signalisiert einen vollständig belegten Prüfstand, `1` eine offene
Prüfung und `2` einen technischen Fehler. Nach Änderungen am Artefakt benötigt
die neue Datei eine Prüfung ihres eigenen Digests.

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

Registriere den [Beispielkatalog](../contracts/phase4/examples/catalogs/application.json),
das [Profil für Kundenauslieferung](../contracts/phase4/examples/profiles/license-distribution.json)
und das [Specbound-Produktmanifest](../contracts/phase4/examples/products/specbound-license.json)
als Quellen. Übernimm das Manifest am vorhandenen Produkt, falls das Repository
schon gebunden ist. In der Produktrevision bestimmt `spec.licenseUse` den Einsatz.
Für `internal` oder `saas` kann das Produkt das
[Profil für den Serverbetrieb](../contracts/phase4/examples/profiles/license-server.json)
verwenden. Beide Profile sind Beispiele für Unternehmensregeln.

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
Lizenzdatei belegen. Neben dem exakten Apache-2.0-Abgleich kann der Worker mit
dem Buildziel `license-scan` ScanCode einsetzen. Ein einzelner vollständiger
Lizenztext muss mit der Deklaration im selben Archiv übereinstimmen. Der
Nachweis speichert Dateiname und SHA-256 sowie bei ScanCode Version, Regel
und Zeilenbereich. Der Befund gilt für dieses Archiv. Ein offener
Dateinachweis erzeugt einen blockierenden Verstoß. Für die Auslieferung sind
die tatsächlich gebauten Artefakte maßgeblich.

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
  "allowed": ["MIT", "Apache-2.0", "BSD-2-Clause", "BSD-3-Clause", "ISC"],
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

# Specbound

Begriffe für die Bewertung von Produkt- und Governance-Daten.

## Sprache

**Arbeitsbereich**:
Der serverseitig konfigurierte Zugriffskontext einer Installation mit einer bestehenden Organisation und einem Standard-Eigentümerteam. Er ersetzt keine Anmeldung oder Teamrolle. Browserparameter können ihn nicht wechseln.

**Produkt**:
Das zu prüfende System mit seinen tatsächlichen Quellen. Ein Produktmanifest ordnet ihm ausdrücklich eine genaue Profilversion zu. Ein Scanner und das Repository der Governance-Konfiguration sind keine Produkte dieses Prüfablaufs.

**Katalog**:
Ein natives OSCAL-Dokument mit gruppierten Controls, ihren Anforderungen und Parametern. Seine Registrierung macht noch keine Anforderung für ein Produkt geltend.

**Profil**:
Ein natives OSCAL-Dokument, das Controls aus einer konkreten Katalogquelle auswählt und unterstützte Parameter setzt. Die Produktzuordnung bestimmt seine Geltung.

**Control**:
Eine identifizierte Anforderung im Katalog. Eine ausführbare Prüfbindung beschreibt ihre konkrete Auswertung. Ohne unterstützte Methode oder passende Nachweise bleibt das Ergebnis unbekannt.

**Evidence Pack**:
Ein versioniertes `EvidenceProviderPack` mit Capabilities, Ein-/Ausgabeschemas, Runtime- und Berechtigungsdeklarationen. Es ist eine Erweiterung, kein Nachweis und keine Ausführungsfreigabe.

**Nachweis**:
Eine gespeicherte Beobachtung mit tatsächlichem Wert, Herkunft, Zeitpunkt und Gültigkeit, die eine Control-Bewertung verwendet. Im technischen API-Modell heißt sie Evidence.

**Prüfung / Assessment**:
Ein gespeicherter Bewertungsstand mit konkreter Produkt-, Profil- und Quellenkonfiguration, Einzelbewertungen und Nachweisen. Er wird unter Anforderungen ausgewählt. Aktuelle Nachweisfrische verändert keine damaligen Ergebnisse.

**Ressourcenquelle / ResourceSource**:
Die Konfiguration von Repository, Manifestpfad, Ref-Typ, gewünschtem Ref und erwarteter Ressourcenidentität. Eine registrierte Revision fixiert den gelesenen Commit und die validierten Inhalte.

**Revisionsprüfung**:
Das erneute Lesen einer Ressourcenquelle und der Vergleich mit einem vorgeschlagenen Stand. Struktur und konkrete Referenzen werden validiert, ohne etwas zu registrieren oder geltende Produktanforderungen zu ändern.

**Katalogarchivierung**:
Das Entfernen einer registrierten Katalogrevision aus der aktiven Auswahl. Ihre Inhalte und bestehenden festen Referenzen bleiben erhalten; die Revision kann wiederhergestellt werden.

**Übernahme**:
Die ausdrückliche, autorisierte und protokollierte Registrierung einer geprüften Ressourcenrevision. Nur eine Produktübernahme ersetzt dessen aktuellen Konfigurationsstand; bereits gespeicherte Prüfungen und andere feste Referenzen bleiben erhalten. Eine Übernahme ist keine Ausführungsfreigabe und keine simulierte Bewertung.

**Agenten-Principal**:
Eine nichtmenschliche Identität, die einem oder mehreren Teams lesend zugeordnet werden kann.

**Governance-Pack-Freigabe**:
Die Entscheidung eines Organisationsinhabers, eine bestimmte Governance-Pack-Revision fachlich freizugeben.

**Collector-Freigabe**:
Die gesonderte Entscheidung über die zulässige Ausführung eines Collectors und dessen Zugriffsgrenzen.

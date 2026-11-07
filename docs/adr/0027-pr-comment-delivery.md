# ADR 0027: PR-Kommentar aus abgeschlossenen Assessments

## Entscheidung

Ein optionaler Publisher verarbeitet abgeschlossene Assessment-Jobs und sendet
deren aggregierte Statuszahlen und einen Assessment-Link als GitHub-Kommentar.
Das Installationstoken wird auf das Repository und `pull_requests: write`
beschränkt. Der Publisher aktualisiert ausschließlich einen markierten Kommentar
des eigenen GitHub-App-Bots; andere Kommentare bleiben unangetastet. Er prüft
vor der Zustellung den aktuellen PR-Head. Ein veralteter Job wird übersprungen.
Die Repository-Bindung muss weiterhin zum ursprünglichen signierten Ereignis
passen; eine nachträglich geänderte Bindung erhält kein altes Ergebnis.
Ein späterer Push kann während einer laufenden GitHub-Anfrage eintreffen; dessen
Job aktualisiert den Kommentar nach seiner Fertigstellung erneut.

Ein Datenbankeintrag merkt sich erfolgreiche oder veraltete Zustellungen getrennt
vom Assessment-Job. Fehler werden ohne Exception-Inhalt protokolliert und nach
30 Sekunden erneut versucht. PostgreSQL serialisiert Publisher pro Repository
und PR; nach einem Abbruch kann ein bereits erstellter Bot-Kommentar anhand der
App-Identität wiedergefunden werden. Mehrdeutige Repository-Bindungen werden
vorläufig nicht veröffentlicht, damit Ergebnisse nicht einem falschen Produkt
zugeordnet werden. Der Link unter `/assessments/<snapshot-id>` führt zur
authentifizierten, auf das Team des Produkts begrenzten Berichtsansicht.

## Lokale Konfiguration

Die Zustellung ist standardmäßig deaktiviert. Zur Aktivierung setzt man
`GITHUB_COMMENT_PUBLISHING=true`, `GITHUB_ORGANIZATION_ID`, `GITHUB_APP_ID`,
`GITHUB_INSTALLATION_ID` und `PORTAL_PUBLIC_URL`. Der private App-Schlüssel
muss im Worker unter dem Pfad `GITHUB_APP_PRIVATE_KEY_FILE` lesbar eingebunden
werden, beispielsweise über eine eigene Compose-Override-Datei mit einem
schreibgeschützten Bind-Mount. Der Schlüssel gehört nicht ins Repository.
Die App-Installation benötigt Schreibrechte für Pull Requests.

Diese Zustellung verarbeitet nur vorhandene, erfolgreich abgeschlossene Jobs.
Sie aktiviert weder den noch nicht freigegebenen Assessment-Handler noch eine
für GitHub erreichbare Webhook-URL. Tests verwenden simulierte GitHub-Antworten;
sie behaupten keinen Live-Durchlauf.

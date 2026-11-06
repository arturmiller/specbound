# 0007: Scannerabdeckung und betroffene Bewertungen

Jeder OpenAPI-Scannerlauf speichert zur Repository-Zuordnung Scannerkennung,
angefragten Ref, beobachteten Commit, Beobachtungszeit, untersuchte Dateipfade,
Fehler und `covered`, `partial` oder `failed`. `covered` bedeutet nur, dass die
in ADR 0006 beschriebene Dateiauswahl ohne gemeldete Fehler gelesen wurde; es
behauptet weder vollständige Inventarisierung des Repositorys noch aufgelöste
Referenzen. Ausgaben eines Laufs stehen dem Aufrufer zur Verfügung; diese
Änderung persistiert Coverage, nicht Subjects oder Bewertungen.

`assess_with_scan` ist die Auswertungsgrenze für Regeln, die den OpenAPI-Scanner
benötigen. Sie verlangt den jüngsten Lauf für Produkt, Repository, Scanner und
Ref, den passenden unveränderlichen Commit und `covered`. Fehlt etwas davon oder
ist die Abdeckung unvollständig, ist das Ergebnis `UNKNOWN`, auch wenn ein
Aufrufer ein PASS-Ergebnis übergibt. Ein neuer fehlgeschlagener Lauf kann so eine
frühere erfolgreiche Abdeckung nicht versehentlich weiterverwenden. Die
Beobachtungszeit wird vom ausführenden Dienst angegeben; bei gleicher Zeit
entscheidet die persistierte Lauf-ID. Bewertungen ohne diese Scannerabhängigkeit
nutzen weiterhin die allgemeine Assessment-Funktion.

Diese Funktionen sind noch kein allgemeiner Assessment-Workflow. Es gibt hier
keinen produktiven Git-Adapter oder automatischen Scan-Trigger; diese Integration
folgt mit den entsprechenden späteren Aufgaben. `$ref`-Referenzen werden nicht
aufgelöst und verhindern bis dahin eine vollständige Coverage.

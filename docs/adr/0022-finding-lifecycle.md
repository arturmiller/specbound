# 0022: Finding-Lebenszyklus

Ein Fingerprint ist der SHA-256-Hash einer kanonischen Liste aus Organisation,
Produkt, Repository-Bindung, Assessment-Kontext, optionaler PR-Nummer, Environment,
Subject-ID und Control-ID. Git- und Pack-Revision sowie Ergebnis sind nicht Teil
der Identität, damit ein wiederholt beobachteter Befund denselben Finding-Datensatz
behält. PRs, Baselines und Environments bleiben getrennt.

Ein `FAIL` erzeugt ein offenes Finding beziehungsweise öffnet es erneut. `PASS`
schließt ein vorhandenes Finding; `UNKNOWN` und `NOT_APPLICABLE` schließen es
nicht. Solange noch nie ein `FAIL` vorlag, wird kein Finding erzeugt. Pro Finding
und angewendetem Snapshot wird höchstens ein Verlaufseintrag mit Ergebnis, Grund,
Bewertungs-ID und Zustand gespeichert. Wiederholte Verarbeitung ist idempotent.

Nur der neueste Snapshot desselben Produkt-, Repository-, Kontext- und Environment-
Scopes darf den Zustand verändern; ältere Zustellungen werden ignoriert. Bei
gleichem Erstellungszeitpunkt entscheidet deterministisch die Snapshot-ID. Snapshot-
Erstellung und Finding-Aktualisierung sperren dieselbe Produktzeile in PostgreSQL,
damit konkurrierende Verarbeitungen keine doppelten Findings erzeugen oder einen
älteren Zustand über einen neueren schreiben. Der Ablauf ist intern und erzeugt
noch keine externen Benachrichtigungen.

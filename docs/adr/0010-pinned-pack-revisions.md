# 0010: Unveränderliche Pack-Revisionen

Ein Pin bindet Organisation, Repository und Git-Tag dauerhaft an die beim
Auflösen beobachtete vollständige Commit-ID. Derselbe Pin kann wiederholt
angefordert werden. Zeigt ein Tag später auf einen anderen Commit, melden Pin
und Verifikation `TagMoved` mit ursprünglicher und neuer ID; der gespeicherte
Pin wird nicht überschrieben. Die Datenbank verhindert doppelte Pins pro
Organisation, Repository und Tag.

Ein interner Revisionszeiger hält für jedes Repository die ausgewählte Revision.
Beim Setzen wird der Tag erneut gegen den Pin geprüft. Ein späterer Tag-Move
ändert den Zeiger nicht; er wird bei erneuter Verifikation als Konflikt erkannt.
Die Datenbank bindet den Zeiger an dieselbe Organisation und dasselbe
Repository wie die Revision. Die Organisation wird bei gleichzeitigen
Änderungen gesperrt.

Dieser Zeiger ist ausschließlich eine Grundlage für spätere Workflows: Er
validiert kein Pack, prüft keine Freigabeberechtigung und aktiviert keine
Governance-Regeln. Deshalb wird er hier nicht als HTTP-Aktion angeboten.
Künftige Aufrufer müssen die fachliche Validierung, Berechtigung und erneute
Verifikation vor der Verwendung sicherstellen. Die Tag-Auflösung und die
Datenbanktransaktion sind nicht atomar; ein anschließender Tag-Move kann erst
bei der nächsten Prüfung erkannt werden.

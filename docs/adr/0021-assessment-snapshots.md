# 0021: PR- und Baseline-Assessments

Ein Assessment-Snapshot gehört zu Organisation, Produkt und Repository-Bindung und
trägt genau einen Kontext: `pull_request` mit positiver PR-Nummer oder `baseline`
ohne PR-Nummer. Environment, vollständiger Git-Commit, vollständiger Governance-
Pack-Commit und Erstellungszeit werden unveränderlich zusammen mit den Control-
Bewertungen, deren Ergebnissen und Gründen sowie den verwendeten Evidence-IDs
gespeichert. Dadurch können PR- und Produktionsassessments desselben Produkts
unabhängig nebeneinander bestehen. Es gibt noch keine automatische PR-Zustellung
oder öffentliche Snapshot-API.

Beim Erstellen müssen alle Bewertungen zu Organisation, Produkt, Environment,
Ziel- und Pack-Commit sowie, falls ein Scan referenziert ist, zur Repository-Bindung
passen. Doppelte Bewertungen für dasselbe Subject und Control werden zurückgewiesen.
Referenzierte Evidence muss im Snapshot-Zeitpunkt vorhanden, passend und aktuell
sein; andernfalls ist eine neue Bewertung erforderlich. Ein Snapshot ist ein
historischer Stand, keine Aussage, dass seine Evidence auch später noch aktuell ist.
Der Aufrufer ist für die Herkunft der gepinnten Pack-Revision verantwortlich;
der Snapshot allein stellt keine Pack-Freigabe dar.

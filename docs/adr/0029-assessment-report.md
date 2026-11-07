# ADR 0029: Revisionsgenauer Assessment-Bericht

Der PR-Kommentar verlinkt `/assessments/<snapshot-id>`. Die Ansicht lädt genau
diesen Snapshot und zeigt Revision, Pack-Revision, Ergebnisse, gespeicherte
Finding-Ereignisse, Controls, Subject-Quellverweise und Evidence-Fakten. Sie
ersetzt ein historisches Ergebnis nicht durch den neuesten Produktstand. Wenn
keine Finding-Ereignisse gespeichert wurden, wird das ausdrücklich angezeigt.

Die API prüft die Leseberechtigung für das zuständige Produktteam und die
Organisation des Snapshots; andere Nutzer erhalten HTTP 403. Fehlende Snapshot-
IDs ergeben 404, unvollständige referenzierte Provenienz 409. Evidence-Fakten
werden ausschließlich nach erfolgreicher Autorisierung ausgeliefert.
Quellverweise und Fakten werden als Text dargestellt und nicht als ausführbares
HTML interpretiert. Nach OIDC-Anmeldung kehrt der Browser zum ursprünglichen
Assessment-Pfad zurück.

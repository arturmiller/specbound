# ADR 0031: Unbekannte Ergebnisse und Quellabdeckung

Die Übersicht zeigt gespeicherte Assessment-Snapshots auch dann, wenn kein
Finding existiert. Sie nennt die Anzahl für `PASS`, `FAIL`, `UNKNOWN` und `N/A`
sowie die gespeicherten Gründe. Diese Liste ist historisch und behauptet keinen
automatisch aktuellen Gesamtstatus.

Der Bericht unterscheidet die Ergebniszustände mit Text und Farbe und zeigt zu
jeder Bewertung ihre Begründung und die zugehörige gespeicherte Quellabdeckung.
Eine vollständige Quellabdeckung beweist weder, dass ein Provider vorhanden ist,
noch dass Evidence vorliegt: Fehlt der aktuelle Nachweis, bleibt das Ergebnis
`UNKNOWN`. Fehlende Abdeckung wird explizit benannt. Die dargestellte Abdeckung
bezieht sich auf den Scan des historischen Assessments, nicht auf einen späteren
Neuscan oder eine aktuelle Freigabe.

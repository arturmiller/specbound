# 0019: Begrenzte regelbasierte Bewertung

Ein Control enthält eine nichtleere Liste von Assertions, die mit `all` verknüpft
werden. `equals` vergleicht den Wert eines punktgetrennten Objektpfads mit
`expected`; `exists` prüft, ob der Pfad existiert. Ein vorhandenes `null` zählt als
vorhanden. Fehlende Vergleichswerte und unvollständige Objektstrukturen ergeben
`UNKNOWN`; ein sicher fehlendes Feld ergibt bei `exists` `FAIL`. Boolesche Werte
werden nicht mit Zahlen gleichgesetzt. `all` und `any` enthalten weitere
Assertions unter `assertions` und verwenden dreiwertige Logik: Ein feststehendes
Ergebnis bleibt gültig, ansonsten entsteht `UNKNOWN`. Unbekannte Operatoren,
ungültige Pfade und überschrittene Komplexitätsgrenzen ergeben `UNKNOWN`.

Die interne Bewertung verwendet ein validiertes Control und einen gepinnten
Governance-Commit. Sie prüft Organisation, Produkt, Zielrevision, Subject-Provenienz
und aktuelle Scanner-Abdeckung sowie den Geltungsbereich. Bei anwendbaren Controls
muss genau ein aktueller, zum Subject und zur Capability passender Evidence Record
vorliegen; mehrere gleich passende Records sind bis zu einer späteren Auswahlregel
mehrdeutig und führen zu `UNKNOWN`. Abgelaufene oder fremde Evidence kann kein
`PASS` oder `FAIL` begründen. `NOT_APPLICABLE` benötigt keinen Evidence Record.

Die derzeit prüfbare Scanner-Abdeckung umfasst `api.path` und `api.schema` aus dem
OpenAPI-Scanner. Für andere Subject-Typen liefert dieser Einstiegspunkt `UNKNOWN`,
bis eine passende Abdeckungsprüfung implementiert ist. Der Aufrufer muss das Subject
aus dem vertrauenswürdigen Scanner-Ergebnis und das Control aus dem gepinnten Pack
übernehmen; die gespeicherten Snapshots allein beweisen keine Pack-Freigabe. Ein
öffentlicher Bewertungs- oder Job-Endpunkt wird mit diesem Schritt nicht eingeführt.

Jeder Lauf speichert Ergebnis, menschenlesbaren Grund, verwendete Evidence-IDs,
Scope, Scanner-ID, Zeitpunkt und die Control- und Subject-Snapshots in PostgreSQL.
Diese Datensätze sind einzelne Control-Bewertungen, noch keine vollständigen
Assessment-Snapshots oder Finding-Lebenszyklen.

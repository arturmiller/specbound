# 0017: Persistente Evidence und Gültigkeit

Eine durch den Collector-Vertrag validierte Observation wird als Evidence Record
mit Organisation, Produkt, Subject, Capability, Environment, Zielrevision,
Collector-Revision, Image-Digest, Provenienz, Wert und Beobachtungszeit gespeichert.
Die Collector-Revision ist der vollständige Git-Commit des validierten Provider-Packs;
die Zielrevision ist ein vollständiger Git-Commit oder ein SHA-256-Digest. Die
Organisation muss Eigentümerin des Produktteams sein. Der interne Aufrufer ist
dafür verantwortlich, die Observation aus dem vertrauenswürdigen Runner zu beziehen;
die Speicherung allein beweist keine Image-Freigabe oder Collector-Ausführung.

Die TTL wird pro Speicherung explizit in ganzen Sekunden angegeben (größer als null,
höchstens ein Jahr). `expiresAt` ist `observedAt + TTL`; der Zeitpunkt selbst ist
bereits abgelaufen. Zukünftige Beobachtungen werden abgelehnt. Abgelaufene Records
bleiben für Nachvollziehbarkeit bestehen, werden aber nicht als aktuell ausgewählt.
Die Auswahl muss Organisation, Produkt, Environment, Zielrevision, Subject und
Capability exakt treffen und prüft `observedAt <= now < expiresAt`.

`assess_with_evidence` kontrolliert alle übergebenen Nachweis-IDs gegen diese Auswahl
und gibt bei fehlenden, fremden oder abgelaufenen Records `UNKNOWN` ohne diese IDs
zurück. Es gibt noch keine persistierte Assessment-Pipeline; der spätere Evaluator
muss diese geprüfte Schnittstelle verwenden. Die bisherige allgemeine Funktion
`determine_assessment` bleibt eine reine Zustandsfunktion ohne Datenbankzugriff.

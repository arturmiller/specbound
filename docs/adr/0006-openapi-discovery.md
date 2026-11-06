# 0006: Begrenzter OpenAPI- und JSON-Schema-Scanner

Der Scanner liest über `GitSource.fetch` einen vollständigen Snapshot und bindet
alle Subjects an dessen Commit-ID und die vom Aufrufer angegebene Produkt- und
Repository-ID. Subject-IDs beruhen auf Produkt, Repository, Dateipfad, Typ und
JSON-Pointer; bei gleicher Beobachtungszeit und gleichem Snapshot ist das
Ergebnis deterministisch. Die Beobachtungszeit wird vom Aufrufer angegeben.

Erkannt werden Dateien `openapi.yaml`, `openapi.yml`, `openapi.json`, Dateien
mit Endung `.openapi.yaml`, `.openapi.yml` oder `.openapi.json` und eigenständige
Dateien `*.schema.json`. OpenAPI 3.0/3.1 liefert Subjects für Pfade und
`components.schemas`; JSON Schema liefert ein Subject für das Dokument und
weitere für `$defs`. Quellenreferenzen enthalten Dateipfad und JSON-Pointer.
Andere Dateinamen werden nicht durchsucht. Referenzen werden nicht aufgelöst;
Dateien mit `$ref` melden daher unvollständige Abdeckung. Der Scanner ist keine
vollständige Spezifikationsvalidierung.

Fehlende Quellen und nicht lesbare, zu große, mehrdeutige oder nicht unterstützte
Dateien erscheinen als Fehler, während Ergebnisse anderer Dateien erhalten
bleiben. YAML-Anker und -Aliase sind ausgeschlossen; je Datei gelten maximal
2 MiB. Ein leerer Treffer bedeutet daher nicht automatisch vollständige
Abdeckung oder PASS. Die dauerhafte Coverage und ihre Auswirkung auf Bewertungen
folgen in #48. Ohne den späteren Git-Adapter #40 erfolgt noch keine echte
Repository-Anbindung; die Tests verwenden Snapshots aus Fixture-Repositories.

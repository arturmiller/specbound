# 0011: Governance-Manifeste aus gepinnten Snapshots

Ein Governance-Pack enthält `pack.yaml` mit `apiVersion:
specbound.example/v1alpha1`, `kind: GovernancePack`, einer ID und Version,
einer Liste von Control-Dateien unter `controls/` und versionierten
Capability-Referenzen. Das Format folgt dem Beispiel im Designboard. Jede
Control-Datei enthält eine eindeutige ID, `target.kind`, eine referenzierte
`requiredEvidence.capability` und mindestens eine Assertion. Die Capability muss
auch im Manifest deklariert sein; ihr Format ist beispielsweise
`net.internet-reachability/v1`.

Der Parser liest ausschließlich Dateien aus einem bereits auf einen Commit
gepinnten Git-Snapshot. Die mitgelieferten JSON Schemas prüfen das Manifest und
die Control-Dateien lokal ohne Netzwerkzugriff. Fehlende Dateien, ungültige
Versionen, doppelte IDs oder YAML-Schlüssel, unsichere Pfade und YAML-Aliase
werden abgewiesen. Dateien sind auf 2 MiB begrenzt und müssen JSON-kompatible
Werte enthalten.

Die Prüfung bestätigt Struktur und deklarierte Referenzen. Sie prüft nicht, ob
ein Provider die Capability tatsächlich anbietet, und bewertet oder validiert
nicht die fachliche Bedeutung der Assertions. Pack-Freigabe und Regelbewertung
sind separate spätere Schritte; aus einem parsebaren Manifest folgt kein PASS.

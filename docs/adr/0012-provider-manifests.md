# 0012: Evidence-Provider-Manifeste

Ein `provider.yaml` im gepinnten Snapshot beschreibt ein
`EvidenceProviderPack` mit `specbound.example/v1alpha1`, Pack-ID und Version,
einem Container-Runtime-Vertrag und versionierten Capabilities. Das Format folgt
dem Designboard-Beispiel. Das Container-Image muss einen vollständigen
`@sha256:`-Digest besitzen; ein Tag allein reicht nicht.

Runtime-Ein- und Ausgabevertrag liegen als JSON Schemas unter `contracts/`.
Jede Capability deklariert ein Ausgabeschema unter `schemas/`. Die Dateien
müssen im Snapshot vorhanden, höchstens 2 MiB groß und gültige JSON Schemas
für Draft 2020-12 sein. Nicht lokale Schema-Referenzen werden abgelehnt;
lokale Referenzen werden bei diesem Schritt nicht aufgelöst. Deklarierte
Testdateien müssen im Snapshot unter `tests/` liegen. Doppelte Capabilities
mit gleicher ID und Version sowie unsichere Pfade sind ungültig.

Die Prüfung führt keine Container aus und erteilt weder Berechtigungen noch
Credentials. `permissions` sind ausschließlich deklarative Angaben. Eine
erfolgreiche Schema-Prüfung bedeutet keine Vertrauensentscheidung, keinen
erfolgreichen Collector-Test und keine Provider-Aktivierung; diese Grenzen
werden von späteren Aufgaben behandelt.

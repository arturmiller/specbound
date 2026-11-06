# 0013: Katalog für gepinnte Packs

Ein Organisationseigentümer kann ein Governance- oder Evidence-Provider-Pack
über Repository und Tag verbinden. Der Katalog löst den Tag auf, lädt den
Snapshot am Commit, prüft das passende Manifest und speichert dessen
Katalogdaten an der unveränderlichen Revision. Bei einem verschobenen Tag wird
ein Konflikt gemeldet; der bisherige Eintrag bleibt unverändert. Die
Auflösung und der Git-Host sind nicht atomar, sodass spätere Tag-Bewegungen bei
der nächsten Prüfung erkannt werden.

Die GitHub-App muss der Organisation zugeordnet sein. Mitglieder dürfen die
Katalogeinträge ihrer Organisation lesen; nur der Organisationseigentümer darf
Packs verbinden. Die Oberfläche zeigt Pack-ID, Version, Repository, Tag,
Commit, Controls und Capabilities. Ein Branch ist kein Teil des Vertrags.

Die angezeigten Daten sind strukturell validiert und noch nicht freigegeben.
Der Katalog aktiviert keine Governance-Regeln, führt keine Provider aus und
erteilt keine Berechtigungen. Der Browser-Test verwendet einen ausdrücklich im
Testprozess eingespeisten Fixture-Git-Adapter; die reguläre Anwendung aktiviert
diesen Adapter nicht.

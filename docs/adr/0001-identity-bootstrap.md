# 0001: Identitätsgrenze bis zur OIDC-Anbindung

Status: Die Übergangssperre ist durch [ADR 0002](0002-oidc-access-tokens.md)
für konfigurierte OIDC-Provider abgelöst. Ohne gültige OIDC-Konfiguration
bleibt die API weiterhin gesperrt. Die unten dokumentierten Teamrollen gelten
weiterhin.

Die Team-API benötigt eine verifizierte Identität und ist standardmäßig gesperrt.
Bis Issue #36 die OIDC-Identität bereitstellt, liefert die Identitätsgrenze 401;
Header, Query-Parameter oder Umgebungsvariablen schalten keine Testidentität frei.
Der Health-Endpunkt bleibt unabhängig davon erreichbar.

Integrationstests ersetzen diese Grenze ausschließlich im Testprozess und nutzen
eine isolierte PostgreSQL-Datenbank. Ein ersetzter Test-Principal ist keine
produktiv verifizierte Identität. Die Rollenprüfung wird in #34 implementiert;
die persistierte Principal-ID ist bis #36 eine externe Referenz, keine bereits
implementierte Principal-Tabelle. Die Team-API ist bis zur Integration beider
Bausteine für reale Nutzer nicht freigeschaltet.

Der Browser-Test startet einen eigenen Testserver mit dieser Einspeisung und
verlangt dafür ausdrücklich `SPECBOUND_E2E_DATABASE_URL` für eine Wegwerf-
Datenbank. Der reguläre API-Start aktiviert keine Testidentität.

Beim Erstellen einer Organisation wird die vertrauenswürdig bereitgestellte
Principal-ID als Eigentümer gespeichert. So kann die spätere Rollenprüfung die
Einrichtung des ersten Teams autorisieren, bevor Teammitgliedschaften existieren.

Der Organisationseigentümer verwaltet Organisation und Teams. Team-Admins
verwalten ihr Team und dessen Mitgliedschaften; Maintainer dürfen das eigene
Team ändern, Viewer nur lesen. Mitglieder sehen nur ihre eigenen Teams; andere
Principals erhalten keinen Zugriff. Neue Organisationen können von einer
verifizierten Identität angelegt werden, die dann deren Eigentümer wird.

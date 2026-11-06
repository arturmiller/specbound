# 0003: Agentenidentitäten und Audit-Grenze

Agenten gehören genau einer Organisation und können in mehreren ihrer Teams
Mitglied sein. Bis zur Umsetzung von #38 sind Agentenmitgliedschaften im Portal
auf `viewer` begrenzt; es werden keine Credentials oder Agentenaufträge erzeugt.
Nur Organisationseigentümer verwalten Agenten und lesen deren Auditlog.

Agentenanlage, Umbenennung, Löschung und Änderungen ihrer Teammitgliedschaften
werden in derselben Datenbanktransaktion wie das jeweilige Ereignis protokolliert.
Ein Team mit Agentenmitgliedschaften und eine Organisation mit Agenten oder
Agentenmitgliedschaften können erst nach expliziter Entfernung gelöscht werden,
damit kaskadierende Löschungen die Auditierung nicht umgehen. Agentenlöschung
entfernt ihre Mitgliedschaften mit jeweils eigenem Auditereignis. Die Auditdaten
werden beim Löschen einer Organisation nicht mitgelöscht; ein späterer
organisationsübergreifender Audit-Zugriff ist hier nicht implementiert.

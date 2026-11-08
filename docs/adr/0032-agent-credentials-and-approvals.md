# ADR 0032: Agentenrechte und Governance-Freigaben

Agenten erhalten eigene, auf eine Stunde befristete und widerrufbare lokale
Zugangsdaten. Ausschließlich deren kryptografischer Hash wird gespeichert; die
Ausgabe erfolgt einmalig. Organisationsinhaber mit menschlichem Principal
erstellen und widerrufen Zugangsdaten. Agenten können nur über ihre zugewiesenen
Teams lesen und weder Organisationen anlegen noch Schreibrechte oder eine
Governance-Pack-Freigabe erhalten. Die API bleibt ohne konfigurierte OIDC-
Benutzeranmeldung geschlossen, auch für Agenten.
Ein Organisationsinhaber stellt Zugangsdaten mit
`POST /organizations/{org}/agents/{agent}/credentials` aus und widerruft sie
mit `DELETE /organizations/{org}/agents/{agent}/credentials/{credential}`.
Die Antwort auf die Ausstellung enthält das Token nur einmal und ist als
`no-store` markiert; es wird ausschließlich im `Authorization`-Header verwendet.

Eine Governance-Pack-Freigabe bezieht sich auf eine einzelne, bereits validierte
und gepinnte Revision und wird von einem menschlichen Organisationsinhaber
erteilt oder widerrufen. Sie ist ein eigener auditierter Datensatz: Sie ändert
keinen aktiven Revisionszeiger und erlaubt weder Collector-Ausführung noch
Secret-Zugriff oder Egress. Diese gesonderten Freigaben bleiben bei #51. Git-
Repository-Rechte werden außerhalb von Specbound bei Git verwaltet.
`PUT /organizations/{org}/packs/{revision}/approval` erteilt die Freigabe,
`DELETE` auf demselben Pfad widerruft sie; nur Governance-Packs sind zulässig.

Die Compose-Konfiguration bindet die API an Loopback; Agenten-Zugangsdaten sind
für diesen lokalen Betrieb gedacht. Außerhalb eines geschützten lokalen
Transports ist HTTPS erforderlich. Menschliche Identitäten hängen weiterhin von
der in ADR 0002 beschriebenen Provider-Konfiguration ab.

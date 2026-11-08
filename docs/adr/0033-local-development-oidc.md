# ADR 0033: Lokaler OIDC-Entwicklungsanbieter

Das optionale `compose.local-auth.yaml` startet `oidc-provider` ausschließlich
für den lokalen Entwicklungsablauf. Der öffentliche Browser-Client nutzt
Authorization Code mit PKCE und fordert `urn:specbound:api` als Ressource an.
Der Anbieter stellt dafür RS256-signierte RFC-9068-Access-Tokens aus; die API
prüft sie unverändert gemäß ADR 0002. Ein ID-Token ist kein API-Access-Token.
Die registrierte Redirect-URI ist `http://127.0.0.1:5173/`.

Browser und API verwenden denselben Loopback-Issuer. Die API erreicht den JWKS
über `http://local-oidc:5556/jwks` im isolierten Docker-Netz. Damit diese eine
interne HTTP-Adresse zugelassen wird, setzt ausschließlich das lokale Overlay
`SPECBOUND_LOCAL_DEV_OIDC=1`. Die Ausnahme gilt nur bei exakt diesem JWKS-Pfad
und dem Issuer `http://127.0.0.1:15556`; andere HTTP-Hosts bleiben gesperrt.
Die Signatur- und Claim-Prüfung wird dadurch nicht umgangen. Ein abgefangenes
JWKS könnte im Entwicklungsnetz allerdings gefälschte Tokens ermöglichen.
Der Anbieter und die API veröffentlichen Ports ausschließlich auf dem
Loopback-Interface des Hosts. Der
Entwicklungsmodus akzeptiert beliebige Anmeldedaten und verwendet bekannte
Testschlüssel sowie einen flüchtigen Speicher. Andere Container im selben
Docker-Netz können den Anbieter erreichen. Dieser Aufbau ist nicht für echte
Benutzer, Geheimnisse, unüberwachte Netzwerke oder Produktion geeignet.

Das Overlay wird ausdrücklich aufgerufen und das dokumentierte Compose-Projekt
hat eigene Volumes. Es erstellt keine Organisation automatisch: Ein angemeldeter
Benutzer legt sie über die reguläre API an und wird ihr Eigentümer. Dadurch ist
der erneute Start datenbewahrend. Ohne Overlay bleibt die ursprüngliche
Provider-Konfiguration und der geschlossene Standard unverändert.

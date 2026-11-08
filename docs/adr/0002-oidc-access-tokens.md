# 0002: OIDC-Code-Flow und getrennte API-Access-Tokens

Das Web ist ein öffentlicher OIDC-Client und verwendet Authorization Code mit
PKCE, State und Nonce über `oidc-client-ts`. Die API akzeptiert ausschließlich
RS256-signierte RFC-9068-JWT-Access-Tokens (`at+jwt`) eines konfigurierten
Issuers und JWKS; sie prüft Signatur, Issuer, API-Audience, Ablauf, Ausgabezeit,
Client-ID, Subject, Token-ID und den `openid`-Scope. API-Audience und Client-ID
müssen verschieden sein; ID-Tokens werden nicht als API-Token akzeptiert.
Ein nicht konfigurierter oder unzulässiger Provider lässt die API geschlossen.

Der Provider muss den Resource-Parameter und dieses Access-Token-Profil für
den registrierten öffentlichen Client unterstützen. Issuer und JWKS benötigen
HTTPS; HTTP ist ausschließlich für Loopback-Testserver erlaubt. Die öffentlichen
Parameter heißen `OIDC_ISSUER`, `OIDC_JWKS_URL`, `OIDC_CLIENT_ID` und
`OIDC_AUDIENCE`; JWKS und Issuer müssen zum selben vertrauenswürdigen Provider
gehören. Die freizugebende Redirect-URI ist der Ursprung der Web-App mit `/`.
Eine eng begrenzte, ausdrücklich aktivierte Ausnahme für den lokalen
Entwicklungsanbieter und seine interne Docker-JWKS-Adresse beschreibt
[ADR 0033](0033-local-development-oidc.md).
Der Provider muss für diesen Client ausschließlich interaktive
Benutzeranmeldungen ausstellen; ein Access-Token allein beweist nicht, dass
der zugrunde liegende Account ein Mensch ist. Ein bereits registrierter
Agenten-Principal wird über diesen Benutzer-Login nicht als Benutzer akzeptiert.

Der Browser speichert die OIDC-Sitzung im tabbezogenen `sessionStorage`.
„Lokal abmelden“ entfernt diese Sitzung; es beendet weder die Sitzung beim
Provider noch widerruft es einen bereits ausgestellten Token. Er läuft nach
seiner vom Provider bestimmten Laufzeit ab. Es wird kein Refresh-Token
angefordert. Für produktive Nutzung sind HTTPS und ein vertrauenswürdiger
OIDC-Provider erforderlich.

Benutzer erhalten eine stabile, issuer-qualifizierte Principal-ID. Vorhandene
externe Teamreferenzen werden nicht automatisch einem Benutzer zugeordnet;
Mitgliedschaften müssen die richtige Principal-ID referenzieren. Die
Agentenregistrierung und Agentenrechte bleiben Aufgaben von #37 und #38.

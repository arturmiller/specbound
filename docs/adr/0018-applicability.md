# 0018: Geltungsbereich von Controls

Ein Control kann in `target.labels` zusätzlich zu `target.kind` erforderliche
Schlüssel-Wert-Paare angeben. Alle angegebenen Labels müssen exakt übereinstimmen;
zusätzliche Subject-Labels sind zulässig. Ein bekannter abweichender Typ oder ein
bekannter abweichender Labelwert ergibt `NOT_APPLICABLE` mit Begründung. Fehlende
oder ungültige erforderliche Labels ergeben `UNKNOWN`, sofern nicht bereits ein
anderer Wert sicher widerspricht. Übereinstimmender Typ und alle erforderlichen
Labels ergeben `APPLICABLE`.

Der Matcher behandelt nur explizit bekannte Typen als klassifiziert. Die initialen
Typen sind `database`, `api`, `api.path` und `api.schema`; letztere stammen aus dem
OpenAPI-Scanner. Ein anderer, fehlender oder unbekannter Typ ergibt `UNKNOWN`, auch
wenn eine Zeichenkette zufällig dem Control-Ziel entspricht. Ein vertrauenswürdiger
Aufrufer kann ein vollständiges Register bekannter Typen übergeben; dadurch wird
kein unbekannter Typ automatisch freigegeben. Typen werden exakt verglichen,
insbesondere gibt es keine implizite Hierarchie zwischen `api` und `api.path`.

Das Ergebnis enthält den `Applicability`-Wert und eine Begründung zur Weitergabe
an die Assessment-Zustandsfunktion. Matching allein wertet weder Regeln noch
Evidence aus und ersetzt keine Prüfung der Scanner-Abdeckung.

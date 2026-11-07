# 0016: Kontrollierter Collector im Worker

Der Worker stellt eine interne Runner-Funktion bereit; ein Job-Polling oder eine
öffentliche API zum Starten existiert noch nicht. Es gibt standardmäßig keine
freigegebenen Images und keinen Docker-Socket im Compose-Worker. Ein vertrauenswürdiger
Aufrufer muss Image-Digest und vollständiges Startkommando als festes Paar vorgeben;
beide müssen mit dem validierten Provider-Pack übereinstimmen. Das Kommando enthält
mindestens ein Argument, damit kein implizites Image-CMD ausgeführt wird. Das Image
muss bereits lokal vorhanden sein und darf keine Volumes deklarieren.

Der Request wird validiert und als begrenztes JSON über die Umgebungsvariable
`SPECBOUND_REQUEST` übergeben. Er ist während der Ausführung über Docker-Metadaten
einsehbar und darf keine Secrets enthalten. Secret-Referenzen werden bis #51
ausnahmslos abgelehnt. Der Collector läuft als unprivilegierter Nutzer mit
schreibgeschütztem Dateisystem, ohne Netzwerk, Linux-Capabilities und zusätzliche
Privilegien; CPU, Speicher, Prozesse und Logs sind begrenzt. Die Ausgabe wird gegen
den Collector-Vertrag validiert. Fehler und Timeouts ergeben `UNKNOWN`; das
Containerobjekt wird bei jedem Ergebnis zwangsweise entfernt. Kann die Entfernung
nicht bestätigt werden, signalisiert der Runner stattdessen einen Fehler.

Der Docker-Daemon ist eine privilegierte Vertrauensgrenze: Sein Socket darf nur an
vertrauenswürdige Worker gegeben werden, niemals an Collector-Container. Docker
beschreibt die [Berechtigungen des Daemons](https://docs.docker.com/engine/security/).
Diese Isolation ist keine Freigabe beliebiger fremder Images. Die CI verwendet ein
unveränderlich referenziertes Test-Image; echte Image-, Secret- und Egress-Freigaben
bleiben Gegenstand von #51.

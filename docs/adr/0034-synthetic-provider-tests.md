# 0034: Synthetische Provider-Testläufe

Ein menschlicher Organisationseigentümer kann für eine importierte Revision des
Beispielproviders `arturmiller/specbound-example-provider` mit Capability
`demo.fixture/v1` einen Testlauf vormerken. Die Organisation, Packrevision und
der gepinnte Commit werden in einem eigenen Datensatz gespeichert. Der Request
enthält weder frei wählbares Kommando noch Image oder Credential.

Dieser erste Schritt startet keinen Collector: Der Lauf bleibt `pending` und
die Oberfläche bezeichnet ihn als vorgemerkt und die Ausführung als nicht
verfügbar. Nur der Eigentümer kann die Testläufe lesen und anlegen. Sie sind
von Evidence, Assessments und Findings getrennt und erzeugen keine Observation.
Der spätere Executor #170 muss eine unabhängig konfigurierte Freigabe für die
exakte Revision, das Image und das Kommando erzwingen; dieser Datensatz selbst
ist keine Ausführungsfreigabe.

Der Betrieb nutzt die bestehende lokale Docker-Compose-Umgebung. Nach
`docker compose up -d --build` werden Migrationen beim Start angewendet; ein
Docker-Socket oder zusätzliche Collector-Rechte sind hierfür nicht erforderlich.

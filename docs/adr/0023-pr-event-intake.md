# 0023: PR-Ereignisse und Assessment-Jobs

Nach erfolgreicher Signatur- und Installationsprüfung werden `pull_request`-Events
mit Aktion `opened` oder `synchronize` auf PR-ID, PR-Nummer, Basis-Repository und
vollständigen Head-Commit geprüft. Ein passendes GitHub-Repository wird innerhalb
der konfigurierten Organisation über seine Produktbindung gefunden. Für jede
passende Bindung wird ein `pending`-Assessment-Job gespeichert. Andere Aktionen
oder nicht gebundene Repositories erzeugen keinen Job.

Zustellung und Jobs werden in derselben Datenbanktransaktion gespeichert. Eine
bereits bekannte Delivery-ID wird nicht erneut verarbeitet; unterschiedliche
Zustellungen desselben PR-Heads erzeugen aufgrund einer Datenbank-Unique-Constraint
ebenfalls nur einen Job je Bindung, PR-Nummer und Head-SHA. Ein neuer Head erzeugt
einen neuen Job. Das Modell enthält noch keine Job-Ausführung, Retries oder
Worker-Leases; diese folgen separat. Die Tests senden signierte Fixtures an den
lokalen Webhook. Ein tatsächlicher GitHub-Webhook benötigt weiterhin eine dafür
konfigurierte und für GitHub erreichbare Zustell-URL.

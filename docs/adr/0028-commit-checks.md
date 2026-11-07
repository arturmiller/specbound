# ADR 0028: Commit-genauer GitHub-Check

Der optionale Publisher meldet für abgeschlossene PR-Assessments den Check
`Specbound assessment` an genau der ausgewerteten Commit-SHA. Ein veralteter
Job kann keinen Check für eine neuere SHA erstellen; ein eigener bereits
vorhandener Check für seine alte SHA wird bei der nächsten Bearbeitung auf
`failure` gesetzt. Fehlgeschlagene und
unbekannte Controls, fehlende Bewertungen, unvollständige Abdeckung und fehlende
oder abgelaufene Evidence ergeben `failure`. Für `success` muss mindestens ein
Control bestanden sein; jede verwendete Evidence wird im ursprünglichen Scope
erneut geprüft. Die Zuordnung zum signierten PR-Ereignis und die Zustell- und
Retry-Sperren sind dieselben wie in ADR 0027.

Ein erfolgreicher Check wird spätestens nach fünf Minuten und zum frühesten
Evidence-Ablauf erneut ausgewertet und bei Ablauf auf `failure` gesetzt. Das
setzt einen laufenden Publisher und
eine erreichbare GitHub-API voraus: GitHub-Checks besitzen kein eigenes
automatisches Ablaufdatum. Bei Ausfall können frühere GitHub-Ergebnisse deshalb
bis zur nächsten erfolgreichen Zustellung sichtbar bleiben. Ein späterer
Assessment-Lauf ersetzt keine tatsächlich notwendigen Freigaben für Collector,
Secrets oder Egress.
Wird eine Repository-Bindung geändert oder entfernt, kann ein bereits auf
GitHub vorhandener alter Check dort bestehen bleiben; das frühere Ergebnis
wird nicht auf das neue Repository übertragen.

Die Veröffentlichung wird über `GITHUB_CHECK_PUBLISHING=true` aktiviert und
benötigt dieselbe App-Konfiguration wie ADR 0027 sowie `checks: write` und
`pull_requests: read`. Sie ändert keine Branch-Schutzregeln: Soll der Check einen
Merge verhindern, muss er dort explizit als verpflichtend eingerichtet sein.
Ohne Assessment-Handler entstehen weiterhin keine produktiven Ergebnisse.

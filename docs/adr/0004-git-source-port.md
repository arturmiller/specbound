# 0004: Hosting-unabhängiger Git-Source-Port

`GitSource` bindet einen Adapter an genau ein konfiguriertes Repository.
`resolve_tag` löst auch annotierte Tags auf die vollständige Commit-ID auf.
`fetch` nimmt einen Ref oder eine solche Commit-ID entgegen und liefert die
Dateien zusammen mit der aufgelösten unveränderlichen Commit-ID. Ein später
verschobener Tag ändert einen bereits geladenen Snapshot nicht. Aufrufer, die
eine Version dauerhaft binden, speichern und verwenden die Commit-ID.

Snapshots enthalten Bytes unter relativen POSIX-Dateipfaden; unsichere Pfade und
unvollständige Commit-IDs werden abgewiesen. Für fehlende, ungültige und nicht
erreichbare Quellen gibt es getrennte Port-Fehler. `verify_webhook` erhält die
unveränderten Request-Bytes und Header und liefert bei ungültiger oder fehlender
Signatur `False`. Das Signaturformat und die Schlüsselverwaltung gehören zum
jeweiligen Adapter. Der Fake im Vertragstest ist kein produktiver Git- oder
Webhook-Adapter. Ein echter GitHub-Adapter und dessen Installation folgen in
#40; dieser Port behauptet keine bereits bestehende GitHub-Anbindung.

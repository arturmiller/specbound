# PR Integration

Signierte GitHub-Ereignisse für geöffnete oder aktualisierte Pull Requests können für gebundene Repositories Assessment-Jobs vormerken. PR- und Baseline-Snapshots bleiben getrennt und referenzieren feste Commits.

## Beispiel

Mit installierten Python-Entwicklungsabhängigkeiten die PR-Nummer und den Head-Commit aus einem lokalen Beispielereignis lesen:

```sh
python services/api/examples/docs_examples.py pr
```

Die Ausgabe enthält example/repo, PR 17 und einen vollständigen Beispiel-Commit.

## Einschränkungen

- Das Beispiel sendet kein Webhook-Ereignis und erzeugt keinen Job. Live-Zustellungen benötigen eine konfigurierte, für GitHub erreichbare URL.
- Der Standard-Worker hat noch keinen produktiven Job-Handler. GitHub-Kommentare und Check-Runs sind noch nicht implementiert; die vorhandene App besitzt dafür keine Schreibrechte.

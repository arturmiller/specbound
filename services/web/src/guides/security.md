# Security

Geschützte API-Aufrufe benötigen eine gültige Identität und die passende Organisations- oder Teamberechtigung. GitHub-Webhooks werden anhand des unveränderten Bodys und einer Signatur geprüft.

## Beispiel

Mit installierten Python-Entwicklungsabhängigkeiten eine künstliche Signatur prüfen und danach den Body verändern:

```sh
python services/api/examples/docs_examples.py security
```

Die Ausgabe zeigt original: true und modified: false. Das Beispiel nutzt ausschließlich ein öffentliches Test-Secret.

## Einschränkungen

- Die Signaturprüfung allein richtet weder OIDC noch eine GitHub-App oder deren Berechtigungen ein.
- Der Docker-Daemon ist eine privilegierte Vertrauensgrenze. Der Standard-Worker erhält keinen Docker-Socket; beliebige Collector-Images sind nicht freigegeben.

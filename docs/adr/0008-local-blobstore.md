# 0008: BlobStore und lokaler MinIO-Dienst

Der `BlobStore`-Port definiert Put, Get und idempotentes Delete für Bytes unter
relativen Objektschlüsseln. Fehlende Objekte liefern `BlobNotFound`; fehlerhafte
Schlüssel und Speicherfehler sind unterscheidbar. Der S3-kompatible Adapter
erhält Endpoint, Bucket und Zugangsdaten ausdrücklich; er greift nicht auf
automatisch entdeckte Cloud-Credentials zu. Ein späterer Cloud-Adapter oder
Cloud-Betrieb ist für diesen lokalen Aufbau nicht nötig.

Compose startet MinIO und legt den lokalen Bucket über einen einmaligen
Initialisierungsdienst an. Die API erhält die Konfiguration als
`BLOBSTORE_ENDPOINT`, `BLOBSTORE_BUCKET`, `BLOBSTORE_ACCESS_KEY` und
`BLOBSTORE_SECRET_KEY`; der Adapter wird noch nicht von einem Produktworkflow
genutzt. Die Ports sind an `127.0.0.1` gebunden; das Volume `minio_data` bleibt
bei `docker compose down` erhalten. Die Standard-Credentials sind nur für die
lokale Entwicklung gedacht und können vor dem ersten Start ersetzt werden.

MinIO veröffentlicht für diese Version keine offiziellen Container-Builds.
Compose verwendet den [quelloffenen Community-Build](https://github.com/coollabsio/minio)
der MinIO-Version `RELEASE.2025-10-15T17-29-55Z`, auf einen Manifest-Digest
festgelegt. `MINIO_IMAGE` erlaubt eine bewusst gewählte lokale Alternative.

Vertragstest gegen den tatsächlich mit Compose gestarteten Dienst:

```sh
docker compose up -d minio
docker compose run --rm minio-init
cd services/api
BLOBSTORE_ENDPOINT=http://127.0.0.1:9000 BLOBSTORE_BUCKET=specbound \
  BLOBSTORE_ACCESS_KEY=specbound BLOBSTORE_SECRET_KEY=local-dev-only \
  python -m unittest discover -s tests -p 'test_blobstore_minio.py' -v
```

Die Python-Entwicklungsabhängigkeiten müssen installiert sein. Der Test legt nur
Objekte unter zufälligen Testschlüsseln an und entfernt sie anschließend. Dieselbe
Prüfung läuft in GitHub Actions gegen Compose; es wird kein AWS-Konto benötigt.

"""Export a stored GovernancePack as editable OSCAL and Specbound manifests."""

import json
from datetime import datetime, timezone
from io import BytesIO
from uuid import NAMESPACE_URL, uuid5
from zipfile import ZIP_DEFLATED, ZipFile

from app.git_source import GitSnapshot
from app.oscal_resources import load_profile
from app.resource_contracts import NS


def export_governance_pack(pack, *, include_bindings):
    original = pack["manifest"]["metadata"]
    controls = pack["controls"]
    catalog_id, version = original["id"], original["version"]
    profile_id = uuid5(NAMESPACE_URL, f"{NS}/profile/{catalog_id}").hex
    title = original.get("name", catalog_id)
    exported_at = datetime.now(timezone.utc).isoformat(timespec="seconds")

    def metadata(identity, name):
        return {
            "title": name,
            "last-modified": exported_at,
            "version": version,
            "oscal-version": "1.2.3",
            "props": [{"name": "resource-id", "ns": NS, "value": identity}],
        }

    def document(kind, identity, name, **content):
        return {
            kind: {
                "uuid": str(
                    uuid5(
                        NAMESPACE_URL,
                        f"{NS}/{kind}/{pack['commitUrl']}/{pack['manifestPath']}",
                    )
                ),
                "metadata": metadata(identity, name),
                **content,
            }
        }

    catalog = document(
        "catalog",
        catalog_id,
        title,
        controls=[
            {"id": control["id"], "title": control["id"]} for control in controls
        ],
    )
    profile = document(
        "profile",
        profile_id,
        f"{title} – Profil",
        imports=[
            {
                "href": "catalog.json",
                "include-controls": [
                    {"with-ids": [control["id"] for control in controls]}
                ],
            }
        ],
        merge={"as-is": True},
    )
    files = {"catalog.json": catalog, "profile.json": profile}
    if include_bindings:
        catalog["catalog"]["metadata"]["links"] = [
            {"href": "bindings.json", "rel": "specbound-control-bindings"}
        ]
        files["bindings.json"] = {
            "apiVersion": "specbound.example/v1alpha1",
            "kind": "ControlBindings",
            "metadata": {
                "id": uuid5(NAMESPACE_URL, f"{NS}/bindings/{catalog_id}").hex,
                "name": title,
                "version": version,
            },
            "spec": {
                "catalog": {"id": catalog_id, "version": version},
                "controls": controls,
            },
        }
    encoded = {
        name: (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode()
        for name, value in files.items()
    }
    load_profile(GitSnapshot(pack["commit"], encoded), "profile.json")

    readme = (
        f"Quelle: {pack['manifestUrl']}\n"
        f"Katalog: {catalog_id} {version}\nProfil: {profile_id} {version}\n\n"
        "Vor der Registrierung Anforderungen, Control-Auswahl und gegebenenfalls Prüfbindungen "
        "fachlich prüfen und die Dateien gemeinsam in Git ablegen. Die Control-IDs dienen als Titel, "
        "da das bisherige Format keine Anforderungstexte enthält. Der Export legt keine Ressourcen an "
        "und überträgt keine Freigaben.\n"
    )
    if not include_bindings:
        readme += "Der Export enthält keine Prüfbindungen. Die Controls benötigen dafür eine separate Konfiguration.\n"
    result = BytesIO()
    with ZipFile(result, "w", compression=ZIP_DEFLATED) as archive:
        for name, value in encoded.items():
            archive.writestr(name, value)
        archive.writestr("README.txt", readme)
    return result.getvalue()

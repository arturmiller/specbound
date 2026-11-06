"""Validate governance manifests and their controls from an immutable snapshot."""

from app.git_source import GitSnapshot
from app.manifest_io import ManifestError, read_yaml, validate


def load_governance_pack(snapshot: GitSnapshot):
    manifest = read_yaml(snapshot.files, "pack.yaml")
    validate(manifest, "governance-pack.schema.json", "pack.yaml")
    controls = []
    ids = set()
    capabilities = set(manifest["requiresCapabilities"])
    for path in manifest["controls"]:
        if (
            not path.startswith("controls/")
            or not path.endswith((".yaml", ".yml"))
            or "\\" in path
            or any(part in ("", ".", "..") for part in path.split("/"))
        ):
            raise ManifestError("Invalid control path")
        control = read_yaml(snapshot.files, path)
        validate(control, "governance-control.schema.json", path)
        if control["id"] in ids:
            raise ManifestError("Duplicate control ID")
        if control["requiredEvidence"]["capability"] not in capabilities:
            raise ManifestError("Control requires an undeclared capability")
        ids.add(control["id"])
        controls.append(control)
    return {"revision": snapshot.commit, "manifest": manifest, "controls": controls}

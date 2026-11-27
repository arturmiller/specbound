"""Read a product manifest without database or web framework dependencies.

The license workers read product manifests at a pull request commit and must
not depend on the API's web framework.
"""

from app.manifest_io import read_yaml
from app.manifest_source import checked_manifest_path, content_digest
from app.resource_contracts import HERE, validate


def load_product(snapshot, manifest_path):
    checked_manifest_path(manifest_path)
    document = read_yaml(snapshot.files, manifest_path)
    validate(document, HERE / "product.schema.json")
    repositories = document["spec"]["repositories"]
    names = [item["repository"].lower() for item in repositories]
    if len(set(names)) != len(names) or any(len(name) > 200 for name in names):
        raise ValueError("Duplicate or oversized product repository")
    implemented = document["spec"].get("implementedRequirements", [])
    control_ids = [item["controlId"] for item in implemented]
    if len(set(control_ids)) != len(control_ids):
        raise ValueError("A control implementation is declared more than once")
    return {
        **document["metadata"],
        "document": document,
        "resolved": {
            "repositories": repositories,
            "profile": document["spec"]["profile"],
            **(
                {"licenseUse": document["spec"]["licenseUse"]}
                if "licenseUse" in document["spec"]
                else {}
            ),
            **({"implementedRequirements": implemented} if implemented else {}),
        },
        "dependencies": [manifest_path],
        "contentDigest": content_digest({"product": snapshot.files[manifest_path]}),
    }


def check_implemented_requirements(resolved, selected_control_ids):
    """A product may only describe controls that its organization's profile selects."""
    selected = set(selected_control_ids)
    if any(
        item["controlId"] not in selected
        for item in resolved.get("implementedRequirements", [])
    ):
        raise ValueError(
            "Implemented requirement is not part of the referenced profile"
        )

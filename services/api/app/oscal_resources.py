"""Load native OSCAL requirements and their local, non-executable bindings."""

from app.manifest_io import read_yaml
from app.manifest_source import checked_manifest_path, content_digest
from app.resource_contracts import (
    HERE,
    imported_path,
    index_catalog,
    validate,
    verify_vendor,
)


def load_catalog(snapshot, manifest_path):
    checked_manifest_path(manifest_path)
    verify_vendor()
    document = read_yaml(snapshot.files, manifest_path)
    indexed = index_catalog(document)
    catalog = document["catalog"]
    links = [
        link
        for link in catalog["metadata"].get("links", [])
        if link.get("rel") == "specbound-control-bindings"
    ]
    if len(links) > 1:
        raise ValueError("Ambiguous control binding source")
    binding_path = imported_path(manifest_path, links[0]["href"]) if links else None
    bindings, dependencies = {}, [manifest_path]
    digest_input = {"catalog": snapshot.files[manifest_path]}
    if binding_path:
        binding_document = read_yaml(snapshot.files, binding_path)
        validate(binding_document, HERE / "control-bindings.schema.json")
        if binding_document["spec"]["catalog"] != indexed["identity"]:
            raise ValueError("Bindings refer to a different catalog ID/version")
        for binding in binding_document["spec"]["controls"]:
            control_id = binding["id"]
            if control_id not in indexed["controls"] or control_id in bindings:
                raise ValueError("Unknown or duplicate control binding")
            pending = [(rule, 0) for rule in binding["assertions"]]
            count = 0
            while pending:
                rule, depth = pending.pop()
                count += 1
                if count > 256 or depth > 16:
                    raise ValueError(
                        "Binding rule complexity exceeds the supported limit"
                    )
                for field in ("expectedParameter", "allowedParameter"):
                    if field in rule and rule[field] not in indexed["parameters"]:
                        raise ValueError("Binding refers to an unknown parameter")
                pending.extend(
                    (child, depth + 1) for child in rule.get("assertions", [])
                )
            bindings[control_id] = binding
        dependencies.append(binding_path)
        digest_input["bindings"] = snapshot.files[binding_path]
    controls = [
        {
            "id": control["id"],
            "title": control["title"],
            "parts": control.get("parts", []),
            "parameters": control.get("params", []),
            "groupKey": indexed["controlGroups"][control["id"]],
            "binding": bindings.get(control["id"]),
            "methodStatus": "configured"
            if control["id"] in bindings
            else "not_configured",
        }
        for control in indexed["controls"].values()
    ]
    return {
        **indexed["identity"],
        "name": catalog["metadata"]["title"],
        "document": document,
        "resolved": {
            "groups": indexed["groups"],
            "controls": controls,
            "bindingPath": binding_path,
        },
        "dependencies": dependencies,
        "contentDigest": content_digest(digest_input),
    }

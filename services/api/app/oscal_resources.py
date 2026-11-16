"""Load native OSCAL requirements and their local, non-executable bindings."""

import copy

from app.manifest_io import read_yaml
from app.manifest_source import checked_manifest_path, content_digest
from app.resource_contracts import (
    HERE,
    ROOT,
    compile_bindings,
    imported_path,
    index_catalog,
    resolve_profile,
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


def load_profile(snapshot, manifest_path):
    checked_manifest_path(manifest_path)
    document = read_yaml(snapshot.files, manifest_path)
    validate(document, ROOT / "oscal/1.2.3/oscal_profile_schema.json")
    imports = document["profile"]["imports"]
    if len(imports) != 1 or not isinstance(imports[0].get("href"), str):
        raise ValueError("A profile must import exactly one relative catalog")
    catalog_path = imported_path(manifest_path, imports[0]["href"])
    catalog = load_catalog(snapshot, catalog_path)
    resolved = resolve_profile(
        document, {catalog_path: catalog["document"]}, profile_path=manifest_path
    )
    binding_path = catalog["resolved"]["bindingPath"]
    bindings = (
        compile_bindings(read_yaml(snapshot.files, binding_path), resolved)
        if binding_path
        else []
    )
    compiled = {control["id"]: control for control in bindings}
    definitions = {
        control["id"]: control for control in catalog["resolved"]["controls"]
    }
    controls = []
    for selected in resolved["controls"]:
        control = copy.deepcopy(definitions[selected["id"]])
        control["binding"] = compiled.get(selected["id"])
        control["parameters"] = [
            {**parameter, "values": resolved["parameters"][parameter["id"]]}
            if resolved["parameters"].get(parameter["id"]) is not None
            else parameter
            for parameter in control["parameters"]
        ]
        controls.append(control)
    digest_input = {
        "profile": snapshot.files[manifest_path],
        "catalog": snapshot.files[catalog_path],
    }
    if binding_path:
        digest_input["bindings"] = snapshot.files[binding_path]
    return {
        **resolved["profile"],
        "name": document["profile"]["metadata"]["title"],
        "document": document,
        "resolved": {
            "groups": catalog["resolved"]["groups"],
            "controls": controls,
            "bindingPath": binding_path,
            "selectedControlIds": [control["id"] for control in controls],
            "parameters": resolved["parameters"],
            "catalog": {
                "resourceId": catalog["id"],
                "version": catalog["version"],
                "name": catalog["name"],
                "contentDigest": catalog["contentDigest"],
                "manifestPath": catalog_path,
            },
        },
        "dependencies": [manifest_path, *catalog["dependencies"]],
        "contentDigest": content_digest(digest_input),
    }

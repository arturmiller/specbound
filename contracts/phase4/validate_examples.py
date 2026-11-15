"""Offline reference checks for ADR 0035; no API, registry writes or execution."""

import copy
import hashlib
import json
import posixpath
from pathlib import Path
from urllib.parse import urlsplit

import regex
from jsonschema import Draft202012Validator, FormatChecker
from jsonschema.exceptions import ValidationError
from jsonschema.validators import extend, validator_for
from referencing import Registry, Resource

ROOT = Path(__file__).resolve().parents[1]
HERE = Path(__file__).resolve().parent
NS = "https://specbound.example/ns/resource"


def read(path):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("Duplicate JSON key")
            result[key] = value
        return result

    return json.loads(Path(path).read_text(encoding="utf-8"), object_pairs_hook=pairs)


def schema_registry():
    registry = Registry()
    for path in [*ROOT.glob("v1/*.json"), *HERE.glob("*.schema.json")]:
        schema = read(path)
        registry = registry.with_resource(schema["$id"], Resource.from_contents(schema))
    return registry


def validate(value, path):
    schema = read(path)

    def unicode_pattern(_validator, pattern, instance, _schema):
        if isinstance(instance, str) and not regex.search(pattern, instance):
            yield ValidationError(f"{instance!r} does not match {pattern!r}")

    validator = extend(validator_for(schema), {"pattern": unicode_pattern})
    validator(
        schema, registry=schema_registry(), format_checker=FormatChecker()
    ).validate(value)


def verify_vendor():
    for entry in read(ROOT / "oscal/1.2.3/sources.json")["files"]:
        path = ROOT / "oscal/1.2.3" / entry["name"]
        if hashlib.sha256(path.read_bytes()).hexdigest() != entry["sha256"]:
            raise ValueError("Vendored OSCAL schema differs from its pin")


def identity(body):
    metadata = body["metadata"]
    if metadata["oscal-version"] != "1.2.3":
        raise ValueError("Unsupported OSCAL version")
    matches = [
        p["value"]
        for p in metadata.get("props", [])
        if p.get("ns") == NS and p.get("name") == "resource-id"
    ]
    if len(matches) != 1:
        raise ValueError("Exactly one namespaced resource-id is required")
    result = {"id": matches[0], "version": metadata["version"]}
    Draft202012Validator(
        read(HERE / "product.schema.json")["properties"]["spec"]["properties"][
            "profile"
        ]
    ).validate(result)
    return result


def imported_path(profile_path, href):
    parsed = urlsplit(href)
    if (
        parsed.scheme
        or parsed.netloc
        or parsed.query
        or parsed.fragment
        or "\\" in href
        or "%" in href
        or href.startswith("/")
    ):
        raise ValueError("Only relative snapshot imports are supported")
    path = posixpath.normpath(posixpath.join(posixpath.dirname(profile_path), href))
    if (
        path in (".", "..")
        or path.startswith("../")
        or not path.endswith((".json", ".yaml", ".yml"))
    ):
        raise ValueError("Import escapes the repository or is not a document")
    return path


def resolve_example_profile(document, catalogs, *, profile_path):
    """Demonstrate the supported subset, not a complete OSCAL resolver."""
    validate(document, ROOT / "oscal/1.2.3/oscal_profile_schema.json")
    profile = document["profile"]
    profile_identity = identity(profile)
    if (
        set(profile) - {"uuid", "metadata", "imports", "merge", "modify"}
        or len(profile["imports"]) != 1
        or profile.get("merge") != {"as-is": True}
    ):
        raise ValueError("Unsupported profile structure or merge")
    imported = profile["imports"][0]
    if (
        set(imported) != {"href", "include-controls"}
        or len(imported["include-controls"]) != 1
    ):
        raise ValueError("Only explicit control selection is supported")
    selector = imported["include-controls"][0]
    if set(selector) != {"with-ids"}:
        raise ValueError("Unsupported control selector")
    selected = selector["with-ids"]
    if len(set(selected)) != len(selected):
        raise ValueError("Duplicate control selection")
    path = imported_path(profile_path, imported["href"])
    if path not in catalogs:
        raise ValueError("Catalog is not in the pinned snapshot")
    catalog_document = catalogs[path]
    validate(catalog_document, ROOT / "oscal/1.2.3/oscal_catalog_schema.json")
    catalog = catalog_document["catalog"]
    catalog_identity = identity(catalog)
    controls, parameters, parameter_owners = {}, {}, {}

    def collect(node, depth=0, owner=None):
        if depth > 12:
            raise ValueError("Catalog nesting limit exceeded")
        for parameter in node.get("params", []):
            if owner is None:
                raise ValueError("Only control-local parameters are supported")
            if (
                set(parameter)
                - {"id", "label", "usage", "values", "props", "links", "remarks"}
                or "id" not in parameter
            ):
                raise ValueError("Unsupported parameter semantics")
            if parameter["id"] in parameters:
                raise ValueError("Duplicate parameter ID")
            parameters[parameter["id"]] = parameter.get("values")
            parameter_owners[parameter["id"]] = owner
        for control in node.get("controls", []):
            if control.get("controls") or control["id"] in controls:
                raise ValueError("Nested or duplicate control")
            controls[control["id"]] = control
            collect(control, depth + 1, control["id"])
        for group in node.get("groups", []):
            collect(group, depth + 1)

    collect(catalog)
    if any(control_id not in controls for control_id in selected):
        raise ValueError("Selected control does not exist")
    parameters = {
        key: value
        for key, value in parameters.items()
        if parameter_owners[key] in selected
    }
    modify = profile.get("modify", {})
    if set(modify) - {"set-parameters"}:
        raise ValueError("Unsupported profile modification")
    changed = set()
    for change in modify.get("set-parameters", []):
        if (
            set(change) != {"param-id", "values"}
            or change["param-id"] not in parameters
            or change["param-id"] in changed
        ):
            raise ValueError("Unknown, duplicate or unsupported parameter change")
        changed.add(change["param-id"])
        parameters[change["param-id"]] = change["values"]
    links = [
        link
        for link in catalog["metadata"].get("links", [])
        if link.get("rel") == "specbound-control-bindings"
    ]
    if len(links) > 1:
        raise ValueError("Ambiguous control binding source")
    binding_path = imported_path(path, links[0]["href"]) if links else None
    return {
        "profile": profile_identity,
        "catalog": catalog_identity,
        "catalogPath": path,
        "bindingPath": binding_path,
        "controls": [copy.deepcopy(controls[i]) for i in selected],
        "allControlIds": set(controls),
        "parameters": parameters,
    }


def compile_example_bindings(document, resolved):
    validate(document, HERE / "control-bindings.schema.json")
    if document["spec"]["catalog"] != resolved["catalog"]:
        raise ValueError("Bindings refer to a different catalog")
    selected = {c["id"] for c in resolved["controls"]}
    result, seen = [], set()

    def reject_constant(_value):
        raise ValueError("Non-JSON parameter")

    def parameter(key):
        values = resolved["parameters"].get(key)
        if not values:
            raise ValueError("Missing parameter value")
        return values

    def compile_rule(rule, depth=0):
        if depth > 16 or rule.get("operator") not in {
            "equals",
            "exists",
            "all",
            "any",
            "spdx-allowlist",
        }:
            raise ValueError("Unsupported rule operator or depth")
        rule = copy.deepcopy(rule)
        if "expectedParameter" in rule:
            if rule["operator"] != "equals" or "expected" in rule:
                raise ValueError("Ambiguous expected parameter")
            values = parameter(rule.pop("expectedParameter"))
            if len(values) != 1:
                raise ValueError("A scalar expectation requires one value")
            value = json.loads(values[0], parse_constant=reject_constant)
            if isinstance(value, (dict, list)):
                raise ValueError("Expected parameter must encode a JSON scalar")
            rule["expected"] = value
        if "allowedParameter" in rule:
            if rule["operator"] != "spdx-allowlist" or "allowed" in rule:
                raise ValueError("Ambiguous allowlist parameter")
            rule["allowed"] = list(parameter(rule.pop("allowedParameter")))
        if "assertions" in rule:
            rule["assertions"] = [
                compile_rule(item, depth + 1) for item in rule["assertions"]
            ]
        return rule

    for control in document["spec"]["controls"]:
        if control["id"] in seen or control["id"] not in resolved["allControlIds"]:
            raise ValueError("Unknown or duplicate control binding")
        seen.add(control["id"])
        if control["id"] in selected:
            compiled = copy.deepcopy(control)
            compiled["assertions"] = [
                compile_rule(rule) for rule in compiled["assertions"]
            ]
            result.append(compiled)
    if result:
        compiled_document = copy.deepcopy(document)
        compiled_document["spec"]["controls"] = result
        validate(compiled_document, HERE / "control-bindings.schema.json")
    return result


def check_examples():
    verify_vendor()
    examples = HERE / "examples"
    for name, path in [
        ("product", "products/audio-visualizer.json"),
        ("resource-source", "sources/profile.json"),
        ("workspace", "workspace.json"),
    ]:
        validate(read(examples / path), HERE / f"{name}.schema.json")
    profile = read(examples / "profiles/application-baseline.json")
    resolved = resolve_example_profile(
        profile,
        {"catalogs/application.json": read(examples / "catalogs/application.json")},
        profile_path="profiles/application-baseline.json",
    )
    if (
        read(examples / "products/audio-visualizer.json")["spec"]["profile"]
        != resolved["profile"]
    ):
        raise ValueError("Product references a different profile")
    source = read(examples / "sources/profile.json")["spec"]
    if (
        source["expected"] != resolved["profile"]
        or source["manifestPath"] != "profiles/application-baseline.json"
    ):
        raise ValueError("Registered source does not identify the profile")
    checks = compile_example_bindings(
        read(examples / resolved["bindingPath"]), resolved
    )
    for folder in ("example", "second"):
        validate(
            read(examples / f"evidence/{folder}/provider.json"),
            ROOT / "v1/evidence-provider-pack.schema.json",
        )
        validate(
            read(examples / f"sources/evidence-{folder}.json"),
            HERE / "resource-source.schema.json",
        )
    return checks


if __name__ == "__main__":
    result = check_examples()
    print(
        f"OSCAL 1.2.3 examples and local contracts valid; {len(result)} selected control bindings resolved."
    )

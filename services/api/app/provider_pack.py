"""Validate a provider manifest and its locally declared schema files."""

import json

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError

from app.git_source import GitSnapshot
from app.manifest_io import ManifestError, read_yaml, validate


def _safe_path(path, prefix, suffixes):
    if (
        not path.startswith(prefix + "/")
        or not path.endswith(suffixes)
        or "\\" in path
        or any(part in ("", ".", "..") for part in path.split("/"))
    ):
        raise ManifestError("Invalid provider file path")


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def _invalid_constant(_value):
    raise ValueError("invalid JSON constant")


def _schema(files, path):
    try:
        content = files[path]
        if len(content) > 2 * 1024 * 1024:
            raise ValueError("schema exceeds size limit")
        document = json.loads(
            content.decode("utf-8-sig"),
            object_pairs_hook=_pairs,
            parse_constant=_invalid_constant,
        )
        if (
            not isinstance(document, dict)
            or document.get("$schema") != "https://json-schema.org/draft/2020-12/schema"
        ):
            raise ValueError("unsupported schema dialect")
        pending = [document]
        while pending:
            item = pending.pop()
            if isinstance(item, dict):
                for key in ("$ref", "$dynamicRef", "$recursiveRef"):
                    if key in item and (
                        not isinstance(item[key], str) or not item[key].startswith("#")
                    ):
                        raise ValueError("external schema references are unsupported")
                pending.extend(item.values())
            elif isinstance(item, list):
                pending.extend(item)
        Draft202012Validator.check_schema(document)
        return document
    except (KeyError, ValueError, UnicodeError, SchemaError, RecursionError) as exc:
        raise ManifestError(f"Invalid declared JSON Schema: {path}") from exc


def load_provider_pack(snapshot: GitSnapshot):
    manifest = read_yaml(snapshot.files, "provider.yaml")
    validate(manifest, "evidence-provider-pack.schema.json", "provider.yaml")
    runtime = manifest["runtime"]
    paths = set()
    for path in (runtime["input"], runtime["output"]):
        _safe_path(path, "contracts", (".json",))
        paths.add(path)
    seen = set()
    for capability in manifest["capabilities"]:
        identity = (capability["id"], capability["version"])
        if identity in seen:
            raise ManifestError("Duplicate capability")
        seen.add(identity)
        path = capability["outputSchema"]
        _safe_path(path, "schemas", (".json",))
        paths.add(path)
    for path in manifest.get("tests", []):
        _safe_path(path, "tests", (".yaml", ".yml", ".json"))
        if path not in snapshot.files:
            raise ManifestError("Declared test fixture is missing")
    schemas = {path: _schema(snapshot.files, path) for path in sorted(paths)}
    return {"revision": snapshot.commit, "manifest": manifest, "schemas": schemas}

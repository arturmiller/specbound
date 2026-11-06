"""Load bounded, unambiguous YAML manifests and local JSON Schemas."""

import json
from functools import lru_cache
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator


class ManifestError(ValueError):
    """The pinned manifest or a referenced document is invalid."""


class _UniqueLoader(yaml.SafeLoader):
    def construct_mapping(self, node, deep=False):
        result = {}
        for key_node, value_node in node.value:
            key = self.construct_object(key_node, deep=deep)
            if not isinstance(key, str) or key in result:
                raise ValueError("duplicate or non-string key")
            result[key] = self.construct_object(value_node, deep=deep)
        return result


def read_yaml(files, path):
    try:
        data = files[path]
        if len(data) > 2 * 1024 * 1024:
            raise ValueError("file exceeds limit")
        content = data.decode("utf-8-sig")
        if any(
            isinstance(token, (yaml.AliasToken, yaml.AnchorToken))
            for token in yaml.scan(content)
        ):
            raise ValueError("YAML aliases are unsupported")
        document = yaml.load(content, Loader=_UniqueLoader)
        json.dumps(document, allow_nan=False)
        return document
    except (
        KeyError,
        ValueError,
        TypeError,
        UnicodeError,
        yaml.YAMLError,
        RecursionError,
    ) as exc:
        raise ManifestError(f"Cannot load manifest file: {path}") from exc


@lru_cache(maxsize=8)
def validator(schema_name):
    app_dir = Path(__file__).resolve().parents[1]
    candidates = (
        app_dir / "contracts" / "v1",
        app_dir.parent.parent / "contracts" / "v1",
    )
    schema_path = next(
        (
            directory / schema_name
            for directory in candidates
            if (directory / schema_name).is_file()
        ),
        None,
    )
    if schema_path is None:
        raise RuntimeError("Local manifest schema is not installed")
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


def validate(document, schema_name, path):
    errors = list(validator(schema_name).iter_errors(document))
    if errors:
        raise ManifestError(f"Invalid manifest file: {path}")

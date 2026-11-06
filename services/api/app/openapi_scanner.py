"""Discover explicitly named OpenAPI/JSON Schema files in a pinned Git snapshot."""

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from urllib.parse import quote

import yaml

from app.git_source import GitSource, GitSourceError

MAX_FILE_BYTES = 2 * 1024 * 1024


@dataclass(frozen=True)
class ScanError:
    path: str
    reason: str


@dataclass(frozen=True)
class ScanResult:
    subjects: tuple[dict, ...]
    files_scanned: tuple[str, ...]
    errors: tuple[ScanError, ...]
    commit: str | None


class _UniqueLoader(yaml.SafeLoader):
    def construct_mapping(self, node, deep=False):
        result = {}
        for key_node, value_node in node.value:
            key = self.construct_object(key_node, deep=deep)
            if not isinstance(key, str) or key in result:
                raise ValueError("duplicate or non-string key")
            result[key] = self.construct_object(value_node, deep=deep)
        return result


def _unique_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def _candidate(path: str) -> bool:
    name = path.rsplit("/", 1)[-1].lower()
    return name in ("openapi.yaml", "openapi.yml", "openapi.json") or name.endswith(
        (".openapi.yaml", ".openapi.yml", ".openapi.json", ".schema.json")
    )


def _parse(path: str, content: bytes):
    if len(content) > MAX_FILE_BYTES:
        raise ValueError("file exceeds size limit")
    text = content.decode("utf-8-sig")
    if path.lower().endswith(".json"):
        return json.loads(text, object_pairs_hook=_unique_pairs)
    if any(
        isinstance(token, (yaml.AliasToken, yaml.AnchorToken))
        for token in yaml.scan(text)
    ):
        raise ValueError("YAML anchors and aliases are unsupported")
    return yaml.load(text, Loader=_UniqueLoader)


def _pointer(*parts):
    return "/" + "/".join(
        str(part).replace("~", "~0").replace("/", "~1") for part in parts
    )


def _entries(path: str, document):
    if not isinstance(document, dict):
        raise ValueError("document must be an object")
    if path.lower().endswith(".schema.json"):
        if (
            not isinstance(document.get("$schema"), str)
            or not document["$schema"].strip()
        ):
            raise ValueError("JSON Schema must declare $schema")
        definitions = document.get("$defs", {})
        if not isinstance(definitions, dict) or any(
            not isinstance(name, str) or not name or not isinstance(value, (dict, bool))
            for name, value in definitions.items()
        ):
            raise ValueError("invalid JSON Schema definitions")
        return [("api.schema", "", document.get("title") or path)] + [
            ("api.schema", _pointer("$defs", name), name)
            for name in sorted(definitions)
        ]

    version = document.get("openapi")
    if not isinstance(version, str) or not version.startswith(("3.0.", "3.1.")):
        raise ValueError("expected OpenAPI 3.0 or 3.1")
    paths = document.get("paths", {})
    components = document.get("components", {})
    if not isinstance(paths, dict) or not isinstance(components, dict):
        raise ValueError("invalid paths or components")
    schemas = components.get("schemas", {})
    if not isinstance(schemas, dict):
        raise ValueError("invalid components.schemas")
    if any(
        not isinstance(key, str)
        or not key.startswith(("/", "x-"))
        or (key.startswith("/") and not isinstance(value, dict))
        for key, value in paths.items()
    ):
        raise ValueError("invalid path entry")
    if any(
        not isinstance(key, str) or not key or not isinstance(value, (dict, bool))
        for key, value in schemas.items()
    ):
        raise ValueError("invalid schema entry")
    return [
        ("api.path", _pointer("paths", key), key)
        for key in sorted(paths)
        if key.startswith("/")
    ] + [
        ("api.schema", _pointer("components", "schemas", key), key)
        for key in sorted(schemas)
    ]


def scan_repository(
    source: GitSource,
    ref: str,
    *,
    product_id: str,
    repository_id: str,
    observed_at: datetime,
) -> ScanResult:
    if (
        not isinstance(product_id, str)
        or not product_id.strip()
        or not isinstance(repository_id, str)
        or not repository_id.strip()
    ):
        raise ValueError("product and repository IDs are required")
    if (
        not isinstance(observed_at, datetime)
        or observed_at.tzinfo is None
        or observed_at.utcoffset() is None
    ):
        raise ValueError("observed_at must include a timezone")
    timestamp = observed_at.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    try:
        snapshot = source.fetch(ref)
    except GitSourceError:
        return ScanResult(
            (), (), (ScanError("", "Source unavailable or reference invalid"),), None
        )
    candidates = tuple(path for path in snapshot.files if _candidate(path))
    if not candidates:
        return ScanResult(
            (), (), (ScanError("", "No supported source files found"),), snapshot.commit
        )
    subjects = []
    errors = []
    for path in candidates:
        try:
            entries = _entries(path, _parse(path, snapshot.files[path]))
            for kind, pointer, name in entries:
                if not isinstance(name, str) or not name.strip():
                    raise ValueError("subject name must be a nonempty string")
            file_subjects = []
            for kind, pointer, name in entries:
                identity = json.dumps(
                    [product_id, repository_id, path, kind, pointer],
                    ensure_ascii=False,
                    separators=(",", ":"),
                )
                source_ref = f"repo:{quote(repository_id, safe='')}/{quote(path, safe='/')}#{quote(pointer, safe='/~')}"
                file_subjects.append(
                    {
                        "schemaVersion": 1,
                        "id": "subject:"
                        + hashlib.sha256(identity.encode("utf-8")).hexdigest(),
                        "type": kind,
                        "labels": {"name": name},
                        "scope": {
                            "productId": product_id,
                            "targetRevision": snapshot.commit,
                        },
                        "provenance": {
                            "sourceRef": source_ref,
                            "sourceRevision": snapshot.commit,
                            "collectorRevision": "openapi-scanner-v1",
                        },
                        "observedAt": timestamp,
                    }
                )
            subjects.extend(file_subjects)
        except (ValueError, UnicodeError, yaml.YAMLError, RecursionError):
            errors.append(ScanError(path, "Unsupported or malformed source file"))
    return ScanResult(tuple(subjects), candidates, tuple(errors), snapshot.commit)

"""Validate collector requests and observations against a validated provider pack."""

import json
import math
from functools import lru_cache

from jsonschema import Draft202012Validator, FormatChecker
from jsonschema.exceptions import ValidationError
from referencing import Registry, Resource
from referencing.exceptions import Unresolvable

from app.manifest_io import validator


class CollectorContractError(ValueError):
    """A collector request, response or declared capability is invalid."""


def _ensure_json(value):
    json.dumps(value, allow_nan=False)
    pending = [value]
    while pending:
        item = pending.pop()
        if isinstance(item, dict):
            if any(not isinstance(key, str) for key in item):
                raise ValueError("JSON object keys must be strings")
            pending.extend(item.values())
        elif isinstance(item, list):
            pending.extend(item)
        elif item is None or isinstance(item, (str, bool, int)):
            continue
        elif isinstance(item, float) and math.isfinite(item):
            continue
        else:
            raise ValueError("Value is not JSON")


@lru_cache(maxsize=1)
def _core_validators():
    names = ("common", "subject", "collector-request", "collector-response")
    schemas = {name: validator(f"{name}.schema.json").schema for name in names}
    registry = Registry().with_resources(
        (schema["$id"], Resource.from_contents(schema)) for schema in schemas.values()
    )
    checker = FormatChecker(formats=["date-time"])
    return {
        name: Draft202012Validator(
            schemas[name], registry=registry, format_checker=checker
        )
        for name in ("collector-request", "collector-response")
    }


def _validate(schema, value, label):
    try:
        _ensure_json(value)
        Draft202012Validator(
            schema,
            registry=Registry(),
            format_checker=FormatChecker(formats=["date-time"]),
        ).validate(value)
    except (
        ValueError,
        TypeError,
        ValidationError,
        Unresolvable,
        RecursionError,
    ) as exc:
        raise CollectorContractError(f"Invalid {label}") from exc


def _core_validate(kind, value):
    try:
        _ensure_json(value)
        _core_validators()[kind].validate(value)
    except (
        ValueError,
        TypeError,
        ValidationError,
        Unresolvable,
        RecursionError,
    ) as exc:
        raise CollectorContractError(f"Invalid {kind}") from exc


def _provider(provider):
    try:
        manifest, schemas = provider["manifest"], provider["schemas"]
        declared = {
            f"{item['id']}/{item['version']}": item["outputSchema"]
            for item in manifest["capabilities"]
        }
        return manifest, schemas, declared
    except (KeyError, TypeError) as exc:
        raise CollectorContractError("Invalid provider pack") from exc


def validate_request(provider, request):
    _core_validate("collector-request", request)
    manifest, schemas, declared = _provider(provider)
    if not set(request["capabilities"]).issubset(declared):
        raise CollectorContractError("Requested capability is not declared")
    subject_scope, scope = request["subject"]["scope"], request["scope"]
    if any(scope.get(key) != value for key, value in subject_scope.items()):
        raise CollectorContractError("Subject and request scope differ")
    try:
        schema = schemas[manifest["runtime"]["input"]]
    except (KeyError, TypeError) as exc:
        raise CollectorContractError("Provider input schema is missing") from exc
    _validate(schema, request, "provider input")


def validate_response(provider, request, response):
    validate_request(provider, request)
    _core_validate("collector-response", response)
    manifest, schemas, declared = _provider(provider)
    try:
        output_schema = schemas[manifest["runtime"]["output"]]
    except (KeyError, TypeError) as exc:
        raise CollectorContractError("Provider output schema is missing") from exc
    _validate(output_schema, response, "provider output")
    requested = set(request["capabilities"])
    seen = set()
    for observation in response["observations"]:
        capability = observation["capability"]
        if (
            capability not in requested
            or observation["subjectId"] != request["subject"]["id"]
            or observation["scope"] != request["scope"]
        ):
            raise CollectorContractError(
                "Observation does not match the requested scope"
            )
        try:
            schema = schemas[declared[capability]]
        except (KeyError, TypeError) as exc:
            raise CollectorContractError("Capability output schema is missing") from exc
        _validate(schema, observation["value"], "capability observation")
        seen.add(capability)
    if seen != requested:
        raise CollectorContractError(
            "A requested capability is missing from the response"
        )

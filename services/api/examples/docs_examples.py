"""Run small offline examples used by the portal documentation."""

import hashlib
import hmac
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "services" / "api"))

from app.collector_contracts import validate_response  # noqa: E402
from app.git_source import GitSnapshot  # noqa: E402
from app.github_source import verify_github_signature  # noqa: E402
from app.governance_pack import load_governance_pack  # noqa: E402
from app.provider_pack import load_provider_pack  # noqa: E402
from app.pull_request_events import parse_pr_event  # noqa: E402

FIXTURES = ROOT / "services" / "api" / "tests" / "fixtures"
CAPABILITY = "net.internet-reachability/v1"


def getting_started():
    from app.main import app
    from fastapi.testclient import TestClient

    with TestClient(app) as client:
        response = client.get("/healthz")
        response.raise_for_status()
        return response.json()


def packs():
    source = FIXTURES / "governance"
    snapshot = GitSnapshot(
        "a" * 40,
        {
            "pack.yaml": (source / "pack.yaml").read_bytes(),
            "controls/SEC-NET-001.yaml": (source / "control.yaml").read_bytes(),
        },
    )
    pack = load_governance_pack(snapshot)
    return {
        "pack": pack["manifest"]["metadata"]["id"],
        "control": pack["controls"][0]["id"],
    }


def evidence():
    source = FIXTURES / "provider"
    generic = (source / "schema.json").read_bytes()
    value_schema = json.dumps(
        {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "type": "object",
            "properties": {"publicly_reachable": {"type": "boolean"}},
            "required": ["publicly_reachable"],
            "additionalProperties": False,
        }
    ).encode()
    provider = load_provider_pack(
        GitSnapshot(
            "a" * 40,
            {
                "provider.yaml": (source / "provider.yaml").read_bytes(),
                "contracts/collect-request.json": generic,
                "contracts/observation.json": generic,
                "schemas/reachability.json": value_schema,
                "tests/reachability.yaml": b"name: example\n",
            },
        )
    )
    scope = {"productId": "example", "environment": "test", "targetRevision": "b" * 40}
    request = {
        "schemaVersion": 1,
        "scope": scope,
        "credentialsRef": None,
        "capabilities": [CAPABILITY],
        "subject": {
            "schemaVersion": 1,
            "id": "db-1",
            "type": "database",
            "scope": scope,
            "provenance": {"sourceRef": "repo:example"},
            "observedAt": "2026-01-01T00:00:00Z",
        },
    }
    response = {
        "schemaVersion": 1,
        "observations": [
            {
                "subjectId": "db-1",
                "capability": CAPABILITY,
                "scope": scope,
                "observedAt": "2026-01-01T00:00:00Z",
                "provenance": {"sourceRef": "collector:example"},
                "value": {"publicly_reachable": False},
            }
        ],
    }
    validate_response(provider, request, response)
    return {
        "capability": CAPABILITY,
        "observations": len(response["observations"]),
        "valid": True,
    }


def security():
    secret, body = b"example-secret-only", b'{"action":"opened"}'
    signature = "sha256=" + hmac.new(secret, body, hashlib.sha256).hexdigest()
    return {
        "original": verify_github_signature(secret, body, signature),
        "modified": verify_github_signature(secret, body + b" ", signature),
    }


def pr_integration():
    event = parse_pr_event(
        {
            "action": "opened",
            "number": 17,
            "repository": {"id": 99, "full_name": "example/repo"},
            "pull_request": {
                "id": 123456,
                "number": 17,
                "head": {"sha": "a" * 40},
                "base": {"repo": {"id": 99}},
            },
        }
    )
    return {
        "repository": event["repository"],
        "pr": event["number"],
        "head": event["head"],
    }


EXAMPLES = {
    "start": getting_started,
    "packs": packs,
    "evidence": evidence,
    "security": security,
    "pr": pr_integration,
}


def main():
    if len(sys.argv) != 2 or sys.argv[1] not in EXAMPLES:
        raise SystemExit("Choose one example: " + ", ".join(EXAMPLES))
    print(json.dumps(EXAMPLES[sys.argv[1]](), sort_keys=True))


if __name__ == "__main__":
    main()

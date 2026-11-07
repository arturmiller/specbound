"""Contract and Docker integration tests for the worker collector boundary."""

import copy
import json
import os
import sys
import unittest
from pathlib import Path

import docker
import yaml

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "services" / "api"))
sys.path.insert(0, str(ROOT / "services" / "worker"))

from app.git_source import GitSnapshot  # noqa: E402
from app.provider_pack import load_provider_pack  # noqa: E402
from collector_runner import ApprovedCollector, run_collector  # noqa: E402

IMAGE = "python:3.12-slim@sha256:4840d514c583a4d3d8cad3940e68dee6f0f6f3635c12fcd0a3d74c21a5b93a54"
SCRIPT = """\
import json, os, socket
r = json.loads(os.environ['SPECBOUND_REQUEST'])
assert os.getuid() == 65534
try:
    open('/not-writable', 'w')
    raise AssertionError('root filesystem is writable')
except OSError:
    pass
try:
    s = socket.create_connection(('1.1.1.1', 53), timeout=1)
    s.close()
    raise AssertionError('network is enabled')
except OSError:
    pass
print(json.dumps({'schemaVersion': 1, 'observations': [{
  'subjectId': r['subject']['id'], 'capability': r['capabilities'][0],
  'scope': r['scope'], 'observedAt': '2026-01-01T00:00:00Z',
  'provenance': {'sourceRef': 'collector:fixture'},
  'value': {'publicly_reachable': False}}]}))
"""


def fixture(command):
    source = ROOT / "services" / "api" / "tests" / "fixtures" / "provider"
    manifest = yaml.safe_load((source / "provider.yaml").read_text(encoding="utf-8"))
    manifest["runtime"]["image"] = IMAGE
    manifest["runtime"]["entrypoint"] = list(command)
    generic = (source / "schema.json").read_bytes()
    value_schema = json.dumps({
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object", "properties": {"publicly_reachable": {"type": "boolean"}},
        "required": ["publicly_reachable"], "additionalProperties": False,
    }).encode()
    provider = load_provider_pack(GitSnapshot("a" * 40, {
        "provider.yaml": yaml.safe_dump(manifest).encode(),
        "contracts/collect-request.json": generic,
        "contracts/observation.json": generic,
        "schemas/reachability.json": value_schema,
        "tests/reachability.yaml": b"name: fixture\n",
    }))
    scope = {"productId": "product-1", "environment": "test", "targetRevision": "b" * 40}
    request = {
        "schemaVersion": 1,
        "subject": {"schemaVersion": 1, "id": "subject-1", "type": "database",
                    "scope": scope, "provenance": {"sourceRef": "repo:fixture"},
                    "observedAt": "2026-01-01T00:00:00Z"},
        "scope": scope, "credentialsRef": None,
        "capabilities": ["net.internet-reachability/v1"],
    }
    return provider, request


class ApprovalTest(unittest.TestCase):
    def test_no_docker_access_for_unapproved_command_or_credential(self):
        command = ("python", "-c", SCRIPT)
        provider, request = fixture(command)
        approved = ApprovedCollector(IMAGE, command)
        wrong = copy.deepcopy(provider)
        wrong["manifest"]["runtime"]["entrypoint"] = ["python", "-c", "print('no')"]
        self.assertEqual(run_collector(None, wrong, request, approved).reason, "collector-not-approved")
        request["credentialsRef"] = "credential:fixture"
        self.assertEqual(run_collector(None, provider, request, approved).reason, "collector-not-approved")

    def test_mutable_image_is_not_an_approval(self):
        with self.assertRaises(ValueError):
            ApprovedCollector("python:latest", ("python", "-c", SCRIPT))


@unittest.skipUnless(os.environ.get("SPECBOUND_DOCKER_TESTS") == "1", "Docker integration disabled")
class DockerIntegrationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = docker.from_env()
        cls.client.ping()
        cls.client.images.get(IMAGE)

    def run_fixture(self, command, timeout_seconds=10):
        provider, request = fixture(command)
        before = {item.id for item in self.client.containers.list(all=True, filters={"label": "org.specbound.collector=true"})}
        result = run_collector(self.client, provider, request, ApprovedCollector(IMAGE, command), timeout_seconds=timeout_seconds)
        after = {item.id for item in self.client.containers.list(all=True, filters={"label": "org.specbound.collector=true"})}
        self.assertEqual(before, after, "collector container must be removed")
        return result

    def test_valid_observation_in_restricted_container(self):
        result = self.run_fixture(("python", "-c", SCRIPT))
        self.assertEqual(result.status, "OBSERVED")
        self.assertFalse(result.observations[0]["value"]["publicly_reachable"])

    def test_timeout_kills_and_removes_container(self):
        result = self.run_fixture(("python", "-c", "import time; time.sleep(30)"), 1)
        self.assertEqual((result.status, result.reason), ("UNKNOWN", "timeout"))

    def test_invalid_observation_is_unknown(self):
        result = self.run_fixture(("python", "-c", "print('{}')"))
        self.assertEqual((result.status, result.reason), ("UNKNOWN", "invalid-response"))

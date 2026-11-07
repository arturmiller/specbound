"""Collector request/response contract at the provider boundary."""

import copy
import json
import unittest
from pathlib import Path

from app.collector_contracts import (
    CollectorContractError,
    validate_request,
    validate_response,
)
from app.git_source import GitSnapshot
from app.provider_pack import load_provider_pack

FIXTURES = Path(__file__).parent.parent / "fixtures" / "provider"
CAPABILITY = "net.internet-reachability/v1"


class CollectorContractsTest(unittest.TestCase):
    def setUp(self):
        generic = (FIXTURES / "schema.json").read_bytes()
        result_schema = json.dumps(
            {
                "$schema": "https://json-schema.org/draft/2020-12/schema",
                "type": "object",
                "properties": {"publicly_reachable": {"type": "boolean"}},
                "required": ["publicly_reachable"],
                "additionalProperties": False,
            }
        ).encode()
        self.provider = load_provider_pack(
            GitSnapshot(
                "a" * 40,
                {
                    "provider.yaml": (FIXTURES / "provider.yaml").read_bytes(),
                    "contracts/collect-request.json": generic,
                    "contracts/observation.json": generic,
                    "schemas/reachability.json": result_schema,
                    "tests/reachability.yaml": b"name: fixture\n",
                },
            )
        )
        self.scope = {
            "productId": "product-1",
            "environment": "test",
            "targetRevision": "b" * 40,
        }
        self.request = {
            "schemaVersion": 1,
            "subject": {
                "schemaVersion": 1,
                "id": "subject-1",
                "type": "database",
                "scope": self.scope,
                "provenance": {"sourceRef": "repo:fixture"},
                "observedAt": "2026-01-01T00:00:00Z",
            },
            "scope": self.scope,
            "credentialsRef": "credential:fixture",
            "capabilities": [CAPABILITY],
        }
        self.response = {
            "schemaVersion": 1,
            "observations": [
                {
                    "subjectId": "subject-1",
                    "capability": CAPABILITY,
                    "scope": self.scope,
                    "observedAt": "2026-01-01T00:00:00Z",
                    "provenance": {"sourceRef": "collector:fixture"},
                    "value": {"publicly_reachable": False},
                }
            ],
        }

    def test_valid_request_and_observation_match_declared_schemas(self):
        validate_request(self.provider, self.request)
        validate_response(self.provider, self.request, self.response)

    def test_missing_or_undeclared_capability_is_rejected(self):
        request = copy.deepcopy(self.request)
        request["capabilities"] = ["storage.encryption/v1"]
        with self.assertRaises(CollectorContractError):
            validate_request(self.provider, request)
        response = copy.deepcopy(self.response)
        response["observations"] = []
        with self.assertRaises(CollectorContractError):
            validate_response(self.provider, self.request, response)

    def test_unresolvable_provider_schema_is_rejected(self):
        provider = copy.deepcopy(self.provider)
        provider["schemas"]["schemas/reachability.json"] = {"$ref": "#/$defs/missing"}
        with self.assertRaises(CollectorContractError):
            validate_response(provider, self.request, self.response)

    def test_wrong_schema_scope_and_subject_are_rejected(self):
        for change in ("value", "scope", "subject", "timestamp"):
            response = copy.deepcopy(self.response)
            item = response["observations"][0]
            if change == "value":
                item["value"] = {"publicly_reachable": "false"}
            if change == "scope":
                item["scope"]["targetRevision"] = "c" * 40
            if change == "subject":
                item["subjectId"] = "other"
            if change == "timestamp":
                item["observedAt"] = "not-a-time"
            with self.subTest(change=change), self.assertRaises(CollectorContractError):
                validate_response(self.provider, self.request, response)

    def test_runtime_input_output_contracts_are_enforced(self):
        provider = copy.deepcopy(self.provider)
        provider["schemas"]["contracts/collect-request.json"] = {
            "type": "object",
            "required": ["extra"],
        }
        with self.assertRaises(CollectorContractError):
            validate_request(provider, self.request)
        provider = copy.deepcopy(self.provider)
        provider["schemas"]["contracts/observation.json"] = {
            "type": "object",
            "required": ["extra"],
        }
        with self.assertRaises(CollectorContractError):
            validate_response(provider, self.request, self.response)

    def test_scope_credentials_and_unrequested_observations_are_rejected(self):
        request = copy.deepcopy(self.request)
        request["subject"]["scope"] = {"productId": "other"}
        with self.assertRaises(CollectorContractError):
            validate_request(self.provider, request)
        request = copy.deepcopy(self.request)
        request["credentialsRef"] = "raw-secret"
        with self.assertRaises(CollectorContractError):
            validate_request(self.provider, request)
        response = copy.deepcopy(self.response)
        response["observations"][0]["capability"] = "storage.encryption/v1"
        with self.assertRaises(CollectorContractError):
            validate_response(self.provider, self.request, response)

    def test_non_json_observation_values_are_rejected(self):
        for value in ({1: "not a JSON object key"}, ("tuple",), float("nan")):
            response = copy.deepcopy(self.response)
            response["observations"][0]["value"] = value
            with self.subTest(value=value), self.assertRaises(CollectorContractError):
                validate_response(self.provider, self.request, response)

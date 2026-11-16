"""Native resource registration through the API, using immutable fixture snapshots."""

import copy
import json
import os
import unittest
from pathlib import Path
from unittest.mock import patch

from app.database import get_engine
from app.git_source import GitSnapshot
from app.identity import get_current_principal
from app.main import app
from app.pack_catalog import github_source_factory
from app.rule_engine import evaluate_assertions
from app.tables import pack_revisions
from fastapi.testclient import TestClient
from sqlalchemy import func, select


class ResourceFixtureSource:
    def __init__(self, repository):
        self.repository = repository
        self.commit = "a" * 40
        self.calls = []
        root = next(
            parent / "contracts/phase4/examples"
            for parent in Path(__file__).resolve().parents
            if (parent / "contracts/phase4/examples").is_dir()
        )
        self.files = {
            str(path.relative_to(root)).replace("\\", "/"): path.read_bytes()
            for path in root.rglob("*.json")
        }

    def resolve_tag(self, tag):
        return self.commit

    def fetch(self, ref):
        self.calls.append(ref)
        if ref not in ("heads/main", self.commit):
            raise ValueError("Expected an unambiguous ref or pinned commit")
        return GitSnapshot(self.commit, self.files)

    def close(self):
        pass


class ResourceRegistryTest(unittest.TestCase):
    def setUp(self):
        app.dependency_overrides[get_current_principal] = lambda: "user:owner"
        self.client = TestClient(app)
        self.org = self.client.post(
            "/organizations", json={"name": "Native resources"}
        ).json()["id"]
        self.source = ResourceFixtureSource("example/governance")
        app.dependency_overrides[github_source_factory] = lambda: (
            lambda _repo: self.source
        )
        self.env = patch.dict(os.environ, {"GITHUB_ORGANIZATION_ID": self.org})
        self.env.start()
        self.url = f"/organizations/{self.org}/resources"
        self.config = {
            "apiVersion": "specbound.example/v1alpha1",
            "kind": "ResourceSource",
            "metadata": {
                "id": "catalog-source",
                "version": "1.0.0",
                "name": "Application controls",
            },
            "spec": {
                "resourceType": "Catalog",
                "provider": "github",
                "repository": self.source.repository,
                "ref": "main",
                "refType": "branch",
                "manifestPath": "catalogs/application.json",
                "expected": {"id": "application-controls", "version": "1.0.0"},
            },
        }

    def tearDown(self):
        self.client.close()
        self.env.stop()
        app.dependency_overrides.clear()

    def post(self, *, preview=False, headers=None):
        return self.client.post(
            self.url,
            params={"preview": preview},
            json=self.config,
            headers=headers or {},
        )

    def test_preview_and_registration_keep_controls_groups_and_exact_sources(self):
        preview = self.post(preview=True)
        self.assertEqual(preview.status_code, 200, preview.text)
        self.assertEqual(preview.json()["state"], "preview")
        self.assertEqual(self.client.get(self.url).json(), [])
        with get_engine().connect() as db:
            self.assertEqual(
                db.execute(
                    select(func.count())
                    .select_from(pack_revisions)
                    .where(pack_revisions.c.organization_id == self.org)
                ).scalar_one(),
                0,
            )
        created = self.post(headers={"X-Expected-Commit": "a" * 40})
        self.assertEqual(created.status_code, 201, created.text)
        value = created.json()
        self.assertEqual(value["state"], "registered")
        self.assertEqual(
            [control["id"] for control in value["resolved"]["controls"]],
            ["SEC-API-001", "PY-LIC-001"],
        )
        self.assertEqual(
            value["resolved"]["groups"][1]["title"], "Application Governance"
        )
        self.assertEqual(
            value["resolved"]["controls"][1]["binding"]["requiredEvidence"][
                "capability"
            ],
            "python.package-license/v1",
        )
        self.assertIn(
            "/blob/" + "a" * 40 + "/catalogs/application.json",
            value["source"]["manifestUrl"],
        )
        self.assertEqual(value["source"]["files"][1]["path"], "checks/application.json")
        self.assertEqual(self.source.calls, ["heads/main", "heads/main"])
        self.assertEqual(self.client.get(self.url + "/" + value["id"]).json(), value)
        self.assertEqual(self.post().json(), value)

    def test_preview_ref_change_is_rejected_without_partial_registration(self):
        self.assertEqual(self.post(preview=True).status_code, 200)
        self.source.commit = "b" * 40
        response = self.post(headers={"X-Expected-Commit": "a" * 40})
        self.assertEqual(response.status_code, 409, response.text)
        self.assertEqual(self.client.get(self.url).json(), [])

    def test_duplicate_ids_bad_bindings_and_wrong_identity_fail_before_persistence(
        self,
    ):
        import json

        original = copy.deepcopy(self.source.files)
        for variant in ("duplicate", "binding", "identity"):
            self.source.files = copy.deepcopy(original)
            document = json.loads(self.source.files["catalogs/application.json"])
            if variant == "duplicate":
                document["catalog"]["groups"][0]["controls"].append(
                    copy.deepcopy(document["catalog"]["groups"][0]["controls"][0])
                )
            elif variant == "binding":
                document["catalog"]["metadata"]["links"][0]["href"] = (
                    "https://evil.example/rules.json"
                )
            else:
                document["catalog"]["metadata"]["props"][0]["value"] = "another-catalog"
            self.source.files["catalogs/application.json"] = json.dumps(
                document
            ).encode()
            with self.subTest(variant=variant):
                response = self.post()
                self.assertEqual(response.status_code, 422, response.text)
                self.assertEqual(self.client.get(self.url).json(), [])

    def test_immutable_identity_and_unbound_controls_are_visible(self):
        import json

        document = json.loads(self.source.files["catalogs/application.json"])
        del document["catalog"]["metadata"]["links"]
        self.source.files["catalogs/application.json"] = json.dumps(document).encode()
        first = self.post()
        self.assertEqual(first.status_code, 201, first.text)
        self.assertTrue(
            all(
                control["methodStatus"] == "not_configured"
                for control in first.json()["resolved"]["controls"]
            )
        )
        self.source.commit = "b" * 40
        document["catalog"]["groups"][0]["controls"][0]["title"] = "Changed requirement"
        self.source.files["catalogs/application.json"] = json.dumps(document).encode()
        self.assertEqual(self.post().status_code, 409)
        self.assertEqual(self.client.get(self.url).json(), [first.json()])

    def test_organization_and_agent_access_remain_enforced(self):
        app.dependency_overrides[get_current_principal] = lambda: "user:outsider"
        self.assertEqual(self.post(preview=True).status_code, 403)
        self.assertEqual(self.client.get(self.url).status_code, 403)
        self.assertEqual(self.source.calls, [])
        app.dependency_overrides[get_current_principal] = lambda: "agent:reader"
        self.assertEqual(self.post(preview=True).status_code, 403)
        self.assertEqual(self.source.calls, [])

    def test_excessive_version_is_rejected_by_the_contract_before_fetching(self):
        self.config["spec"]["expected"]["version"] = "1" * 129 + ".0.0"
        self.assertEqual(self.post().status_code, 422)
        self.assertEqual(self.source.calls, [])

    def profile_config(self):
        config = copy.deepcopy(self.config)
        config["metadata"]["id"] = "profile-source"
        config["spec"].update(
            resourceType="Profile",
            manifestPath="profiles/application-baseline.json",
            expected={"id": "application-baseline", "version": "1.0.0"},
        )
        return config

    def test_profile_selects_controls_explicitly_and_expands_its_parameters(self):
        document = json.loads(self.source.files["profiles/application-baseline.json"])
        document["profile"]["imports"][0]["include-controls"][0]["with-ids"] = [
            "PY-LIC-001"
        ]
        self.source.files["profiles/application-baseline.json"] = json.dumps(
            document
        ).encode()
        catalog = self.post()
        self.assertEqual(catalog.status_code, 201, catalog.text)
        self.config = self.profile_config()
        profile = self.post()
        self.assertEqual(profile.status_code, 201, profile.text)
        value = profile.json()
        self.assertEqual(value["resolved"]["selectedControlIds"], ["PY-LIC-001"])
        self.assertEqual(
            value["resolved"]["catalog"]["revisionId"], catalog.json()["id"]
        )
        control = value["resolved"]["controls"][0]
        self.assertEqual(
            control["binding"]["assertions"][0]["allowed"], ["MIT", "Apache-2.0", "ISC"]
        )
        self.assertEqual(
            control["parameters"][0]["values"], ["MIT", "Apache-2.0", "ISC"]
        )
        self.assertEqual(
            evaluate_assertions(
                control["binding"]["assertions"], {"licenseExpression": "GPL-3.0-only"}
            ).truth.value,
            "FAIL",
        )
        self.assertEqual(self.client.get(self.url + "/" + value["id"]).json(), value)

    def test_profile_requires_a_registered_catalog_and_rejects_unknown_controls(self):
        catalog_config = copy.deepcopy(self.config)
        self.config = self.profile_config()
        response = self.post()
        self.assertEqual(response.status_code, 422, response.text)
        self.assertIn("registered first", response.json()["detail"])
        self.assertEqual(self.client.get(self.url).json(), [])
        self.config = catalog_config
        catalog = self.post().json()
        self.config = self.profile_config()
        document = json.loads(self.source.files["profiles/application-baseline.json"])
        document["profile"]["imports"][0]["include-controls"][0]["with-ids"] = [
            "UNKNOWN-CONTROL"
        ]
        self.source.files["profiles/application-baseline.json"] = json.dumps(
            document
        ).encode()
        self.assertEqual(self.post().status_code, 422)
        self.assertEqual(self.client.get(self.url).json(), [catalog])

    def test_invalid_profile_parameters_fail_before_a_profile_is_saved(self):
        catalog = self.post().json()
        self.config = self.profile_config()
        original = json.loads(self.source.files["profiles/application-baseline.json"])
        for values in (["1e400"], ["true", "false"]):
            document = copy.deepcopy(original)
            document["profile"]["modify"]["set-parameters"].append(
                {"param-id": "auth-required", "values": values}
            )
            self.source.files["profiles/application-baseline.json"] = json.dumps(
                document
            ).encode()
            with self.subTest(values=values):
                self.assertEqual(self.post().status_code, 422)
                self.assertEqual(self.client.get(self.url).json(), [catalog])

    def test_changed_catalog_closure_requires_a_new_profile_version(self):
        catalog_config = copy.deepcopy(self.config)
        self.assertEqual(self.post().status_code, 201)
        self.config = self.profile_config()
        first = self.post()
        self.assertEqual(first.status_code, 201, first.text)
        self.source.commit = "b" * 40
        catalog = json.loads(self.source.files["catalogs/application.json"])
        catalog["catalog"]["metadata"]["version"] = "2.0.0"
        self.source.files["catalogs/application.json"] = json.dumps(catalog).encode()
        bindings = json.loads(self.source.files["checks/application.json"])
        bindings["spec"]["catalog"]["version"] = "2.0.0"
        self.source.files["checks/application.json"] = json.dumps(bindings).encode()
        profile_config = copy.deepcopy(self.config)
        self.config = catalog_config
        self.config["spec"]["expected"]["version"] = "2.0.0"
        self.assertEqual(self.post().status_code, 201)
        self.config = profile_config
        rejected = self.post()
        self.assertEqual(rejected.status_code, 409, rejected.text)
        self.assertEqual(
            self.client.get(self.url + "/" + first.json()["id"]).json(), first.json()
        )

    def test_selected_unbound_parameter_requires_a_value_after_profile_overrides(self):
        catalog = json.loads(self.source.files["catalogs/application.json"])
        del catalog["catalog"]["groups"][0]["controls"][0]["params"][0]["values"]
        self.source.files["catalogs/application.json"] = json.dumps(catalog).encode()
        bindings = json.loads(self.source.files["checks/application.json"])
        bindings["spec"]["controls"] = [
            binding
            for binding in bindings["spec"]["controls"]
            if binding["id"] != "SEC-API-001"
        ]
        self.source.files["checks/application.json"] = json.dumps(bindings).encode()
        profile = json.loads(self.source.files["profiles/application-baseline.json"])
        profile["profile"]["imports"][0]["include-controls"][0]["with-ids"] = [
            "SEC-API-001"
        ]
        del profile["profile"]["modify"]
        self.source.files["profiles/application-baseline.json"] = json.dumps(
            profile
        ).encode()
        registered_catalog = self.post()
        self.assertEqual(registered_catalog.status_code, 201, registered_catalog.text)
        self.config = self.profile_config()
        response = self.post()
        self.assertEqual(response.status_code, 422, response.text)
        self.assertEqual(self.client.get(self.url).json(), [registered_catalog.json()])

        profile["profile"]["modify"] = {
            "set-parameters": [{"param-id": "auth-required", "values": ["true"]}]
        }
        self.source.files["profiles/application-baseline.json"] = json.dumps(
            profile
        ).encode()
        response = self.post()
        self.assertEqual(response.status_code, 201, response.text)
        control = response.json()["resolved"]["controls"][0]
        self.assertEqual(control["methodStatus"], "not_configured")
        self.assertEqual(control["parameters"][0]["values"], ["true"])

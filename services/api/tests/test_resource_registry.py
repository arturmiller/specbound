"""Native resource registration through the API, using immutable fixture snapshots."""

import copy
import os
import unittest
from pathlib import Path
from unittest.mock import patch

from app.database import get_engine
from app.git_source import GitSnapshot
from app.identity import get_current_principal
from app.main import app
from app.pack_catalog import github_source_factory
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

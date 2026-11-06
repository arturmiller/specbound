"""Pack catalog through the authorized HTTP API and a pinned fixture source."""

import os
import unittest
from pathlib import Path
from unittest.mock import patch

from app.git_source import GitSnapshot
from app.identity import get_current_principal
from app.main import app
from app.pack_catalog import github_source_factory
from fastapi.testclient import TestClient

COMMIT = "a" * 40
FIXTURES = Path(__file__).parent / "fixtures" / "governance"


class FixtureSource:
    def __init__(self, repository):
        self.repository = repository
        self.commit = COMMIT

    def resolve_tag(self, tag):
        return self.commit

    def fetch(self, ref):
        if ref != self.commit:
            raise ValueError("expected pinned commit")
        return GitSnapshot(
            self.commit,
            {
                "pack.yaml": (FIXTURES / "pack.yaml").read_bytes(),
                "controls/SEC-NET-001.yaml": (FIXTURES / "control.yaml").read_bytes(),
            },
        )

    def close(self):
        pass


class ProviderFixtureSource(FixtureSource):
    def fetch(self, ref):
        if ref != self.commit:
            raise ValueError("expected pinned commit")
        fixtures = Path(__file__).parent / "fixtures" / "provider"
        schema = (fixtures / "schema.json").read_bytes()
        return GitSnapshot(
            self.commit,
            {
                "provider.yaml": (fixtures / "provider.yaml").read_bytes(),
                "contracts/collect-request.json": schema,
                "contracts/observation.json": schema,
                "schemas/reachability.json": schema,
                "tests/reachability.yaml": b"name: fixture\n",
            },
        )


class PackCatalogTest(unittest.TestCase):
    def setUp(self):
        if not os.environ.get("DATABASE_URL"):
            self.fail("DATABASE_URL must point to a disposable migrated database")
        app.dependency_overrides[get_current_principal] = lambda: "user:owner"
        self.source = FixtureSource("example/packs")
        app.dependency_overrides[github_source_factory] = lambda: (
            lambda _repo: self.source
        )
        self.client = TestClient(app)
        self.org = self.client.post("/organizations", json={"name": "Catalog"}).json()[
            "id"
        ]
        self.env = patch.dict(os.environ, {"GITHUB_ORGANIZATION_ID": self.org})
        self.env.start()
        self.url = f"/organizations/{self.org}/packs"

    def tearDown(self):
        self.client.close()
        self.env.stop()
        app.dependency_overrides.clear()

    def test_connect_list_detail_and_tag_move(self):
        data = {"repository": "example/packs", "tag": "v1", "kind": "governance"}
        created = self.client.post(self.url, json=data)
        self.assertEqual(created.status_code, 201, created.text)
        entry = created.json()
        self.assertEqual(entry["commit"], COMMIT)
        self.assertEqual(entry["controls"][0]["id"], "SEC-NET-001")
        self.assertNotIn("branch", entry)
        self.assertEqual(self.client.get(self.url).json(), [entry])
        self.assertEqual(self.client.get(self.url + "/" + entry["id"]).json(), entry)
        self.source.commit = "b" * 40
        self.assertEqual(self.client.post(self.url, json=data).status_code, 409)
        self.assertEqual(
            self.client.get(self.url + "/" + entry["id"]).json()["commit"], COMMIT
        )

    def test_catalog_access_is_scoped_to_organization(self):
        app.dependency_overrides[get_current_principal] = lambda: "user:outsider"
        self.assertEqual(self.client.get(self.url).status_code, 403)
        self.assertEqual(
            self.client.post(
                self.url,
                json={"repository": "example/packs", "tag": "v1", "kind": "governance"},
            ).status_code,
            403,
        )

    def test_connect_provider_pack_preserves_capability_provenance(self):
        self.source = ProviderFixtureSource("example/provider")
        response = self.client.post(
            self.url,
            json={"repository": "example/provider", "tag": "v1", "kind": "provider"},
        )
        self.assertEqual(response.status_code, 201, response.text)
        result = response.json()
        self.assertEqual(result["commit"], COMMIT)
        self.assertEqual(result["capabilities"][0]["id"], "net.internet-reachability")
        self.assertEqual(
            result["capabilities"][0]["outputSchema"], "schemas/reachability.json"
        )

    def test_app_is_not_shared_with_another_organization(self):
        with patch.dict(os.environ, {"GITHUB_ORGANIZATION_ID": "another-org"}):
            response = self.client.post(
                self.url,
                json={"repository": "example/packs", "tag": "v1", "kind": "governance"},
            )
            self.assertEqual(response.status_code, 403)

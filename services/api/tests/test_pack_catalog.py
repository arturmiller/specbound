"""Pack catalog through the authorized HTTP API and a pinned fixture source."""

import os
import unittest
from io import BytesIO
from pathlib import Path
from unittest.mock import patch
from zipfile import ZipFile

import yaml
from app.database import get_engine
from app.git_source import GitSnapshot
from app.identity import get_current_principal
from app.main import app
from app.oscal_resources import load_profile
from app.pack_catalog import github_source_factory
from app.tables import pack_catalog, principals
from fastapi.testclient import TestClient
from sqlalchemy import update
from sqlalchemy.dialects.postgresql import insert

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

    def test_archived_pack_exports_valid_manifests_without_changing_approval(self):
        with get_engine().begin() as db:
            db.execute(
                insert(principals)
                .values(
                    id="user:owner", kind="user", issuer="test", subject="catalog-owner"
                )
                .on_conflict_do_nothing()
            )
        pack = self.client.post(
            self.url,
            json={"repository": "example/packs", "tag": "v1", "kind": "governance"},
        ).json()
        detail = self.url + "/" + pack["id"]
        approved = self.client.put(detail + "/approval")
        self.assertEqual(approved.status_code, 200, approved.text)
        approval = approved.json()
        for bindings in (True, False):
            result = self.client.get(
                detail + "/manifests", params={"include_bindings": bindings}
            )
            self.assertEqual(
                result.status_code,
                200,
                result.text[:300] if result.status_code != 200 else "",
            )
            self.assertEqual(result.headers["content-type"], "application/zip")
            with ZipFile(BytesIO(result.content)) as archive:
                files = {name: archive.read(name) for name in archive.namelist()}
            self.assertEqual("bindings.json" in files, bindings)
            native = load_profile(GitSnapshot(pack["commit"], files), "profile.json")
            self.assertEqual(native["resolved"]["selectedControlIds"], ["SEC-NET-001"])
            self.assertEqual(
                native["resolved"]["controls"][0]["binding"] is not None, bindings
            )
        self.assertEqual(self.client.get(detail).json(), pack)
        self.assertEqual(self.client.get(detail + "/approval").json(), approval)
        app.dependency_overrides[get_current_principal] = lambda: "user:outsider"
        self.assertEqual(self.client.get(detail + "/manifests").status_code, 403)

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

    def use_nested_provider_source(self):
        source = ProviderFixtureSource("example/providers")
        fetch = source.fetch
        source.calls = 0
        source.changed = False

        def nested(ref):
            source.calls += 1
            snapshot = fetch(source.commit if ref in ("main", "heads/main") else ref)
            files = {}
            for folder in ("one", "two"):
                for path, content in snapshot.files.items():
                    if path == "provider.yaml":
                        manifest = yaml.safe_load(content)
                        manifest["metadata"]["id"] += "." + folder
                        content = yaml.safe_dump(manifest).encode()
                        path = "manifest.yaml"
                    if source.changed and path == "schemas/reachability.json":
                        content = b'{"$schema":"https://json-schema.org/draft/2020-12/schema","type":"string"}'
                    files[f"packs/{folder}/{path}"] = content
            return GitSnapshot(snapshot.commit, files)

        source.fetch = nested
        self.source = source
        return source

    def test_two_manifests_in_one_repository_and_ref_are_independent(self):
        source = self.use_nested_provider_source()
        saved = []
        for folder in ("one", "two"):
            response = self.client.post(
                self.url,
                json={
                    "repository": source.repository,
                    "ref": "main",
                    "refType": "branch",
                    "manifestPath": f"packs/{folder}/manifest.yaml",
                    "kind": "provider",
                },
            )
            self.assertEqual(response.status_code, 201, response.text)
            saved.append(response.json())
        self.assertEqual(source.calls, 2, "Each registration must read one snapshot")
        self.assertNotEqual(saved[0]["id"], saved[1]["id"])
        self.assertEqual(saved[0]["ref"], "main")
        self.assertEqual(saved[0]["commit"], COMMIT)
        self.assertIn("schemas/reachability.json", saved[0]["schemas"])
        self.assertTrue(
            saved[0]["manifestUrl"].endswith(f"/{COMMIT}/packs/one/manifest.yaml")
        )
        self.assertEqual(
            self.client.get(self.url + "/" + saved[1]["id"]).json(), saved[1]
        )
        self.assertEqual(len(self.client.get(self.url).json()), 2)
        source.changed = True
        source.commit = "b" * 40
        conflict = self.client.post(
            self.url,
            json={
                "repository": source.repository,
                "ref": "main",
                "refType": "branch",
                "manifestPath": "packs/one/manifest.yaml",
                "kind": "provider",
            },
        )
        self.assertEqual(conflict.status_code, 409, conflict.text)
        self.assertEqual(len(self.client.get(self.url).json()), 2)
        self.assertEqual(
            self.client.get(self.url + "/" + saved[0]["id"]).json(), saved[0]
        )

    def test_unsafe_paths_missing_files_and_wrong_sources_do_not_register(self):
        source = self.use_nested_provider_source()
        for path in (
            "../manifest.yaml",
            "/manifest.yaml",
            "C:/manifest.json",
            "packs/missing.yaml",
        ):
            with self.subTest(path=path):
                response = self.client.post(
                    self.url,
                    json={
                        "repository": source.repository,
                        "ref": "main",
                        "refType": "branch",
                        "manifestPath": path,
                        "kind": "provider",
                    },
                )
                self.assertEqual(response.status_code, 422, response.text)
                self.assertEqual(self.client.get(self.url).json(), [])
        response = self.client.post(
            self.url,
            json={
                "repository": "different/repository",
                "ref": "main",
                "refType": "branch",
                "kind": "provider",
            },
        )
        self.assertEqual(response.status_code, 422)
        self.assertEqual(
            source.calls, 1, "Only the safe missing-file request may fetch"
        )

    def test_migrated_unknown_digest_cannot_rebind_identity_to_a_new_commit(self):
        source = self.use_nested_provider_source()
        request = {
            "repository": source.repository,
            "ref": "main",
            "refType": "branch",
            "manifestPath": "packs/one/manifest.yaml",
            "kind": "provider",
        }
        created = self.client.post(self.url, json=request)
        self.assertEqual(created.status_code, 201, created.text)
        revision_id = created.json()["id"]
        with get_engine().begin() as db:
            db.execute(
                update(pack_catalog)
                .where(pack_catalog.c.revision_id == revision_id)
                .values(content_digest=None)
            )
        legacy = self.client.get(self.url + "/" + revision_id).json()
        self.assertIsNone(legacy["contentDigest"])
        self.assertEqual(self.client.post(self.url, json=request).json(), legacy)
        source.changed = True
        source.commit = "b" * 40
        rejected = self.client.post(self.url, json=request)
        self.assertEqual(rejected.status_code, 409, rejected.text)
        self.assertEqual(self.client.get(self.url).json(), [legacy])

    def test_known_schema_contracts_are_public_without_exposing_pack_data(self):
        app.dependency_overrides.clear()
        response = self.client.get("/contracts/provider-pack")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json()["properties"]["kind"]["const"], "EvidenceProviderPack"
        )
        self.assertEqual(
            self.client.get("/contracts/https://evil.example/schema").status_code, 404
        )
        self.assertEqual(self.client.get(self.url).status_code, 401)

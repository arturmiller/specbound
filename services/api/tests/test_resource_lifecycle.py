"""Catalog removal retains immutable references, identity fences and authorization."""

import json
import unittest

from app.database import get_engine
from app.identity import get_current_principal
from app.main import app
from app.tables import audit_events
from sqlalchemy import select

from tests import test_resource_registry as fixtures


class ResourceLifecycleTest(unittest.TestCase):
    setUp = fixtures.ResourceRegistryTest.setUp
    tearDown = fixtures.ResourceRegistryTest.tearDown
    post = fixtures.ResourceRegistryTest.post
    profile_config = fixtures.ResourceRegistryTest.profile_config

    def test_remove_and_restore_keep_profile_references_and_record_only_changes(self):
        catalog = self.post().json()
        catalog_url = self.url + "/" + catalog["id"]
        self.config = self.profile_config()
        profile = self.post().json()
        for _ in range(2):
            response = self.client.delete(catalog_url)
            self.assertEqual(response.status_code, 204, response.text)
        self.assertEqual(self.client.get(self.url).json(), [profile])
        self.assertEqual(
            self.client.get(catalog_url).json(), {**catalog, "state": "archived"}
        )
        self.assertEqual(
            self.client.get(self.url + "/" + profile["id"]).json(), profile
        )
        self.assertEqual(
            len(self.client.get(self.url, params={"include_archived": True}).json()), 2
        )
        self.assertEqual(self.post(preview=True).status_code, 422)
        for _ in range(2):
            response = self.client.post(catalog_url + "/restore")
            self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual(response.json(), catalog)
        self.assertEqual(self.post(preview=True).status_code, 200)
        with get_engine().connect() as db:
            events = (
                db.execute(
                    select(audit_events).where(
                        audit_events.c.target_id == catalog["id"]
                    )
                )
                .mappings()
                .all()
            )
        self.assertCountEqual(
            [event["action"] for event in events],
            ["resource.archived", "resource.restored"],
        )
        self.assertTrue(all(event["actor_id"] == "user:owner" for event in events))

    def test_archive_is_not_silently_undone_by_registration_or_adoption(self):
        catalog = self.post().json()
        url = self.url + "/" + catalog["id"]
        self.assertEqual(self.client.delete(url).status_code, 204)
        self.assertEqual(self.post().status_code, 409)
        self.assertEqual(self.client.post(url + "/check", json={}).status_code, 409)
        self.source.commit = "b" * 40
        changed = json.loads(self.source.files["catalogs/application.json"])
        changed["catalog"]["groups"][0]["controls"][0]["title"] = "Changed"
        self.source.files["catalogs/application.json"] = json.dumps(changed).encode()
        self.assertEqual(self.post(preview=True).status_code, 409)
        self.assertEqual(self.client.get(url).json()["manifest"], catalog["manifest"])

    def test_only_owner_can_change_catalog_lifecycle_and_scope_is_checked(self):
        catalog = self.post().json()
        url = self.url + "/" + catalog["id"]
        team = self.client.post(
            f"/organizations/{self.org}/teams", json={"name": "Readers"}
        ).json()["id"]
        agent = self.client.post(
            f"/organizations/{self.org}/agents", json={"name": "Reader"}
        ).json()["id"]
        for principal in ("user:viewer", agent):
            self.client.post(
                f"/teams/{team}/members",
                json={"principalId": principal, "role": "viewer"},
            )
            app.dependency_overrides[get_current_principal] = lambda: principal
            self.assertEqual(self.client.get(url).status_code, 200)
            self.assertEqual(self.client.delete(url).status_code, 403)
            self.assertEqual(self.client.post(url + "/restore").status_code, 403)
            app.dependency_overrides[get_current_principal] = lambda: "user:owner"
        other = self.client.post("/organizations", json={"name": "Other"}).json()["id"]
        foreign = f"/organizations/{other}/resources/{catalog['id']}"
        self.assertEqual(self.client.delete(foreign).status_code, 404)
        self.assertEqual(self.client.post(foreign + "/restore").status_code, 404)
        self.assertEqual(self.client.get(url).json(), catalog)

    def test_another_commit_cannot_reactivate_the_same_archived_identity(self):
        catalog = self.post().json()
        url = self.url + "/" + catalog["id"]
        self.assertEqual(self.client.delete(url).status_code, 204)
        self.source.commit = "b" * 40
        self.assertEqual(self.post(preview=True).status_code, 409)
        self.assertEqual(self.post().status_code, 409)
        history = self.client.get(self.url, params={"include_archived": True}).json()
        self.assertEqual(history, [{**catalog, "state": "archived"}])
        self.assertEqual(self.client.post(url + "/restore").status_code, 200)
        self.assertEqual(self.post().status_code, 201)

    def test_profile_removal_is_not_enabled_by_the_catalog_endpoint(self):
        self.post()
        self.config = self.profile_config()
        profile = self.post().json()
        url = self.url + "/" + profile["id"]
        self.assertEqual(self.client.delete(url).status_code, 422)
        self.assertEqual(self.client.post(url + "/restore").status_code, 422)
        self.assertEqual(self.client.get(url).json(), profile)

"""Evidence registry authorization and stable paging across equal timestamps."""

import os
import unittest
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.database import get_engine
from app.identity import get_current_principal
from app.main import app
from app.tables import evidence_records
from fastapi.testclient import TestClient
from sqlalchemy import insert


class EvidenceRegistryTest(unittest.TestCase):
    def setUp(self):
        if not os.environ.get("DATABASE_URL"):
            self.fail("DATABASE_URL must point to a disposable migrated database")
        self.as_principal("user:owner")
        self.client = TestClient(app)
        self.org = self.client.post("/organizations", json={"name": "Evidence org"}).json()["id"]
        self.other_org = self.client.post("/organizations", json={"name": "Other org"}).json()["id"]
        self.team = self.client.post(f"/organizations/{self.org}/teams", json={"name": "Visible"}).json()["id"]
        hidden_team = self.client.post(f"/organizations/{self.org}/teams", json={"name": "Hidden"}).json()["id"]
        other_team = self.client.post(f"/organizations/{self.other_org}/teams", json={"name": "Other"}).json()["id"]
        self.product = self.client.post(f"/organizations/{self.org}/products", json={"name": "Visible", "ownerTeamId": self.team}).json()["id"]
        hidden_product = self.client.post(f"/organizations/{self.org}/products", json={"name": "Hidden", "ownerTeamId": hidden_team}).json()["id"]
        other_product = self.client.post(f"/organizations/{self.other_org}/products", json={"name": "Other", "ownerTeamId": other_team}).json()["id"]
        self.client.post(f"/teams/{self.team}/members", json={"principalId": "user:viewer", "role": "viewer"})
        prefix = uuid4().hex[:12]
        self.ids = [f"{prefix}-{suffix}" for suffix in ("a", "b", "c")]
        self.hidden_id = f"{prefix}-hidden"
        now = datetime(2026, 1, 1, tzinfo=timezone.utc)

        def record(item_id, organization, product):
            return {
                "id": item_id, "organization_id": organization, "product_id": product,
                "subject_id": "subject:fixture", "capability": "fixture.read/v1",
                "environment": "test", "target_revision": "a" * 40,
                "collector_revision": "b" * 40, "collector_image": "fixture@sha256:" + "c" * 64,
                "provenance": {"sourceRef": "collector:fixture"}, "value": {"result": True},
                "observed_at": now, "expires_at": now + timedelta(minutes=1), "ttl_seconds": 60,
            }

        with get_engine().begin() as db:
            db.execute(insert(evidence_records), [
                *(record(item_id, self.org, self.product) for item_id in self.ids),
                record(self.hidden_id, self.org, hidden_product),
                record(f"{prefix}-other", self.other_org, other_product),
            ])

    def tearDown(self):
        self.client.close()
        app.dependency_overrides.clear()

    @staticmethod
    def as_principal(principal):
        app.dependency_overrides[get_current_principal] = lambda: principal

    def test_pages_and_details_are_scoped_to_visible_teams(self):
        self.as_principal("user:viewer")
        url = f"/organizations/{self.org}/evidence"
        first = self.client.get(url, params={"limit": 2}).json()
        self.assertEqual([item["id"] for item in first["items"]], self.ids[::-1][:2])
        self.assertEqual(first["nextOffset"], 2)
        second = self.client.get(url, params={"limit": 2, "offset": 2}).json()
        self.assertEqual([item["id"] for item in second["items"]], [self.ids[0]])
        self.assertIsNone(second["nextOffset"])
        detail = self.client.get(f"{url}/{self.ids[0]}").json()
        self.assertEqual(detail["productId"], self.product)
        self.assertEqual(detail["collectorRevision"], "b" * 40)
        self.assertEqual(detail["provenance"]["sourceRef"], "collector:fixture")
        self.assertEqual(detail["value"], {"result": True})
        self.assertEqual(self.client.get(f"{url}/{self.hidden_id}").status_code, 404)
        self.assertEqual(self.client.get(f"/organizations/{self.other_org}/evidence").status_code, 403)
        self.as_principal("user:owner")
        self.assertEqual(len(self.client.get(url).json()["items"]), 4)

    def test_invalid_page_sizes_and_outsiders_are_denied(self):
        url = f"/organizations/{self.org}/evidence"
        for params in ({"limit": 0}, {"limit": 101}, {"offset": -1}, {"offset": 9223372036854775808}):
            self.assertEqual(self.client.get(url, params=params).status_code, 422)
        self.as_principal("user:outsider")
        self.assertEqual(self.client.get(url).status_code, 403)
        self.assertEqual(self.client.get(f"{url}/{self.ids[0]}").status_code, 403)

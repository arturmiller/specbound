"""Signed PR deliveries enqueue one job per product binding, PR and head SHA."""

import copy
import hashlib
import hmac
import json
import os
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch
from uuid import uuid4

from app.database import get_engine
from app.main import app
from app.tables import assessment_jobs, organizations, products, repo_bindings, teams
from fastapi.testclient import TestClient
from sqlalchemy import insert, select


class PullRequestEventsTest(unittest.TestCase):
    def setUp(self):
        if not os.environ.get("DATABASE_URL"):
            self.fail("DATABASE_URL must point to a disposable migrated database")
        self.org, self.team, self.product, self.binding = (
            str(uuid4()) for _ in range(4)
        )
        with get_engine().begin() as db:
            db.execute(
                insert(organizations).values(
                    id=self.org, name="Org", owner_principal_id="owner"
                )
            )
            db.execute(
                insert(teams).values(
                    id=self.team, organization_id=self.org, name="Team"
                )
            )
            db.execute(
                insert(products).values(
                    id=self.product, owner_team_id=self.team, name="Product"
                )
            )
            db.execute(
                insert(repo_bindings).values(
                    id=self.binding,
                    product_id=self.product,
                    provider="github",
                    repository="example/repo",
                )
            )
        self.settings = patch.dict(
            os.environ,
            {
                "GITHUB_WEBHOOK_SECRET": "fixture-secret",
                "GITHUB_INSTALLATION_ID": "12345",
                "GITHUB_ORGANIZATION_ID": self.org,
            },
        )
        self.settings.start()
        self.client = TestClient(app)
        self.payload = {
            "action": "opened",
            "installation": {"id": 12345},
            "repository": {"id": 99, "full_name": "Example/Repo"},
            "number": 17,
            "pull_request": {
                "id": 123456,
                "number": 17,
                "head": {"sha": "a" * 40},
                "base": {"repo": {"id": 99}},
            },
        }

    def tearDown(self):
        self.client.close()
        self.settings.stop()

    def send(self, payload, *, delivery=None, valid_signature=True):
        body = json.dumps(payload).encode()
        digest = hmac.new(b"fixture-secret", body, hashlib.sha256).hexdigest()
        return self.client.post(
            "/webhooks/github",
            content=body,
            headers={
                "X-Hub-Signature-256": "sha256="
                + (digest if valid_signature else "0" * 64),
                "X-GitHub-Event": "pull_request",
                "X-GitHub-Delivery": delivery or str(uuid4()),
            },
        )

    def jobs(self):
        with get_engine().begin() as db:
            return (
                db.execute(
                    select(assessment_jobs).where(
                        assessment_jobs.c.organization_id == self.org
                    )
                )
                .mappings()
                .all()
            )

    def test_duplicate_delivery_and_same_head_create_one_job(self):
        delivery = str(uuid4())
        self.assertEqual(
            self.send(
                self.payload, delivery=delivery, valid_signature=False
            ).status_code,
            401,
        )
        self.assertEqual(self.jobs(), [])
        self.assertEqual(self.send(self.payload, delivery=delivery).status_code, 202)
        self.assertEqual(self.send(self.payload, delivery=delivery).status_code, 202)
        self.assertEqual(self.send(self.payload).status_code, 202)
        jobs = self.jobs()
        self.assertEqual(len(jobs), 1)
        self.assertEqual(
            (
                jobs[0]["binding_id"],
                jobs[0]["pull_request_id"],
                jobs[0]["pull_request_number"],
                jobs[0]["head_sha"],
                jobs[0]["status"],
            ),
            (self.binding, 123456, 17, "a" * 40, "pending"),
        )
        changed = copy.deepcopy(self.payload)
        changed["action"] = "synchronize"
        changed["pull_request"]["head"]["sha"] = "b" * 40
        self.assertEqual(self.send(changed, delivery=delivery).status_code, 202)
        self.assertEqual(
            len(self.jobs()), 1, "a replayed delivery must not enqueue its altered body"
        )
        self.assertEqual(self.send(changed).status_code, 202)
        self.assertEqual({job["head_sha"] for job in self.jobs()}, {"a" * 40, "b" * 40})

    def test_other_repositories_actions_and_invalid_payloads_cannot_enqueue(self):
        unrelated = copy.deepcopy(self.payload)
        unrelated["repository"]["full_name"] = "elsewhere/repo"
        self.assertEqual(self.send(unrelated).status_code, 202)
        ignored = copy.deepcopy(self.payload)
        ignored["action"] = "closed"
        self.assertEqual(self.send(ignored).status_code, 202)
        bad = copy.deepcopy(self.payload)
        bad["pull_request"]["head"]["sha"] = "main"
        self.assertEqual(self.send(bad).status_code, 400)
        bad = copy.deepcopy(self.payload)
        bad["pull_request"]["base"]["repo"]["id"] = 100
        self.assertEqual(self.send(bad).status_code, 400)
        self.assertEqual(self.jobs(), [])

    def test_same_repository_in_another_organization_is_not_enqueued(self):
        org, team, product, binding = (str(uuid4()) for _ in range(4))
        with get_engine().begin() as db:
            db.execute(
                insert(organizations).values(
                    id=org, name="Other", owner_principal_id="other"
                )
            )
            db.execute(insert(teams).values(id=team, organization_id=org, name="Team"))
            db.execute(
                insert(products).values(id=product, owner_team_id=team, name="Product")
            )
            db.execute(
                insert(repo_bindings).values(
                    id=binding,
                    product_id=product,
                    provider="github",
                    repository="example/repo",
                )
            )
        self.assertEqual(self.send(self.payload).status_code, 202)
        with get_engine().begin() as db:
            foreign = db.execute(
                select(assessment_jobs).where(assessment_jobs.c.organization_id == org)
            ).first()
        self.assertIsNone(foreign)
        self.assertEqual(len(self.jobs()), 1)

    def test_concurrent_deliveries_for_one_head_are_idempotent(self):
        if get_engine().dialect.name != "postgresql":
            self.skipTest("PostgreSQL concurrent delivery behavior")
        barrier = threading.Barrier(4)

        def deliver(_):
            barrier.wait(timeout=10)
            return self.send(self.payload).status_code

        with ThreadPoolExecutor(max_workers=4) as pool:
            self.assertEqual(list(pool.map(deliver, range(4))), [202] * 4)
        self.assertEqual(len(self.jobs()), 1)

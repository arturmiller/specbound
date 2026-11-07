"""Lease fencing, retries and idempotent PR assessment result finalization."""

import os
import sys
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from pathlib import Path
from uuid import uuid4

import test_rule_evaluation as fixtures
from app.database import get_engine
from app.job_queue import LeaseLost, claim_next, fail_job, finish_job
from app.snapshots import create_snapshot
from app.tables import (
    assessment_jobs,
    assessment_snapshots,
    github_events,
    products,
    repo_bindings,
)
from sqlalchemy import delete, func, insert, select

NOW = fixtures.NOW


class WorkerQueueTest(unittest.TestCase):
    def setUp(self):
        if not os.environ.get("DATABASE_URL"):
            self.fail("DATABASE_URL must point to a disposable migrated database")
        self.f = fixtures.RuleEvaluationTest(methodName="runTest")
        self.f.setUp()
        self.f.save_evidence()
        self.evaluation = self.f.evaluate()
        self.delivery, self.job = str(uuid4()), str(uuid4())
        with get_engine().begin() as db:
            db.execute(
                insert(github_events).values(
                    delivery_id=self.delivery,
                    installation_id="12345",
                    organization_id=self.f.org,
                    event_type="pull_request",
                    payload={},
                )
            )
            db.execute(
                insert(assessment_jobs).values(
                    id=self.job,
                    organization_id=self.f.org,
                    product_id=self.f.product,
                    binding_id=self.f.binding,
                    delivery_id=self.delivery,
                    pull_request_id=123456,
                    pull_request_number=17,
                    head_sha=fixtures.COMMIT,
                    status="pending",
                )
            )

    def claim(self, now=NOW):
        with get_engine().begin() as db:
            return claim_next(db, self.f.org, now=now, lease_seconds=2)

    def build(self, db, now):
        return create_snapshot(
            db,
            self.f.org,
            self.f.product,
            context="pull_request",
            binding_id=self.f.binding,
            pull_request_number=17,
            environment="test",
            git_sha=fixtures.COMMIT,
            pack_sha="a" * 40,
            evaluation_ids=[self.evaluation["id"]],
            now=now,
        )["id"]

    def finish(self, lease, now, build=None):
        with get_engine().begin() as db:
            return finish_job(
                db,
                lease["id"],
                lease["leaseToken"],
                clock=lambda: now,
                build_snapshot=build or (lambda conn: self.build(conn, now)),
            )

    def state(self):
        with get_engine().begin() as db:
            return (
                db.execute(
                    select(assessment_jobs).where(assessment_jobs.c.id == self.job)
                )
                .mappings()
                .one()
            )

    def test_crashed_worker_is_reclaimed_and_old_lease_cannot_commit(self):
        first = self.claim()
        self.assertEqual(first["id"], self.job)
        self.assertIsNone(self.claim(now=NOW + timedelta(seconds=1)))
        recovered = self.claim(now=NOW + timedelta(seconds=3))
        self.assertNotEqual(first["leaseToken"], recovered["leaseToken"])
        called = []
        with self.assertRaises(LeaseLost):
            self.finish(
                first, NOW + timedelta(seconds=3), lambda _: called.append(True)
            )
        self.assertEqual(called, [])
        result = self.finish(recovered, NOW + timedelta(seconds=3))
        self.assertEqual(self.state()["status"], "completed")
        self.assertEqual(
            self.finish(
                recovered,
                NOW + timedelta(seconds=3),
                lambda _: self.fail("duplicate callback"),
            ),
            result,
        )
        with get_engine().begin() as db:
            count = db.execute(
                select(func.count())
                .select_from(assessment_snapshots)
                .where(
                    assessment_snapshots.c.organization_id == self.f.org,
                    assessment_snapshots.c.context == "pull_request",
                    assessment_snapshots.c.git_sha == fixtures.COMMIT,
                )
            ).scalar_one()
        self.assertEqual(count, 1)

    def test_retry_limit_moves_job_to_dead_letter(self):
        for attempt in range(3):
            lease = self.claim(now=NOW + timedelta(seconds=attempt))
            self.assertEqual(lease["attempts"], attempt + 1)
            with get_engine().begin() as db:
                fail_job(
                    db,
                    self.job,
                    lease["leaseToken"],
                    now=NOW + timedelta(seconds=attempt),
                )
        self.assertEqual(self.state()["status"], "dead")
        self.assertIsNone(self.claim(now=NOW + timedelta(seconds=4)))

    def test_failed_snapshot_factory_does_not_leave_partial_snapshot(self):
        lease = self.claim()

        def invalid_factory(db):
            self.build(db, NOW)
            return "not-an-existing-snapshot"

        with get_engine().begin() as db:
            with self.assertRaises(ValueError):
                finish_job(
                    db,
                    self.job,
                    lease["leaseToken"],
                    clock=lambda: NOW,
                    build_snapshot=invalid_factory,
                )
            count = db.execute(
                select(func.count())
                .select_from(assessment_snapshots)
                .where(assessment_snapshots.c.organization_id == self.f.org)
            ).scalar_one()
            self.assertEqual(count, 0)
        self.assertEqual(self.state()["status"], "running")

    def test_concurrent_workers_claim_at_most_once(self):
        if get_engine().dialect.name != "postgresql":
            self.skipTest("PostgreSQL SKIP LOCKED behavior")
        barrier = threading.Barrier(4)

        def claim(_):
            barrier.wait(timeout=10)
            return self.claim()

        with ThreadPoolExecutor(max_workers=4) as pool:
            claims = list(pool.map(claim, range(4)))
        self.assertEqual(len([item for item in claims if item is not None]), 1)

    def test_expiration_during_finalization_rolls_back_snapshot(self):
        lease = self.claim()
        moments = iter((NOW, NOW + timedelta(seconds=3)))
        with get_engine().begin() as db:
            with self.assertRaises(LeaseLost):
                finish_job(
                    db,
                    self.job,
                    lease["leaseToken"],
                    clock=lambda: next(moments),
                    build_snapshot=lambda connection: self.build(connection, NOW),
                )
            count = db.execute(
                select(func.count())
                .select_from(assessment_snapshots)
                .where(assessment_snapshots.c.organization_id == self.f.org)
            ).scalar_one()
            self.assertEqual(count, 0)

    def test_expired_final_attempt_goes_to_dead_letter(self):
        for attempt in range(3):
            self.assertEqual(
                self.claim(now=NOW + timedelta(seconds=3 * attempt))["attempts"],
                attempt + 1,
            )
        self.assertIsNone(self.claim(now=NOW + timedelta(seconds=9)))
        self.assertEqual(self.state()["status"], "dead")

    def test_worker_poll_prepares_and_commits_once(self):
        root = Path(__file__).resolve().parents[3]
        sys.path.insert(0, str(root / "services" / "worker"))
        from queue_worker import poll_once

        prepares = []

        def prepare(job):
            prepares.append(job["id"])
            return lambda db: self.build(db, NOW)

        self.assertTrue(
            poll_once(
                get_engine(), self.f.org, prepare, clock=lambda: NOW, lease_seconds=2
            )
        )
        self.assertFalse(
            poll_once(
                get_engine(), self.f.org, prepare, clock=lambda: NOW, lease_seconds=2
            )
        )
        self.assertEqual(prepares, [self.job])
        self.assertEqual(self.state()["status"], "completed")

    def test_worker_handler_failures_retry_then_dead_letter_without_exposing_error(
        self,
    ):
        root = Path(__file__).resolve().parents[3]
        sys.path.insert(0, str(root / "services" / "worker"))
        from queue_worker import poll_once

        def fail(_job):
            raise RuntimeError("sensitive detail")

        for _ in range(3):
            self.assertTrue(
                poll_once(
                    get_engine(), self.f.org, fail, clock=lambda: NOW, lease_seconds=2
                )
            )
        self.assertEqual(self.state()["status"], "dead")
        self.assertEqual(self.state()["last_error"], "processor-failed")
        self.assertFalse(
            poll_once(
                get_engine(), self.f.org, fail, clock=lambda: NOW, lease_seconds=2
            )
        )

    def test_deleting_a_product_also_removes_its_completed_job(self):
        if get_engine().dialect.name != "postgresql":
            self.skipTest("PostgreSQL foreign-key cascade behavior")
        lease = self.claim()
        self.finish(lease, NOW)
        with get_engine().begin() as db:
            db.execute(
                delete(repo_bindings).where(
                    repo_bindings.c.product_id == self.f.product
                )
            )
            db.execute(delete(products).where(products.c.id == self.f.product))
            self.assertIsNone(
                db.execute(
                    select(assessment_jobs.c.id).where(assessment_jobs.c.id == self.job)
                ).first()
            )

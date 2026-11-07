"""Persist separate PR and baseline snapshots without crossing evidence scope."""

import os
import unittest
from datetime import timedelta

import test_rule_evaluation as fixtures
from app.coverage import run_openapi_scan
from app.database import get_engine
from app.snapshots import create_snapshot, get_snapshot, list_snapshots


class AssessmentSnapshotsTest(unittest.TestCase):
    def setUp(self):
        if not os.environ.get("DATABASE_URL"):
            self.fail("DATABASE_URL must point to a disposable migrated database")
        self.fixture = fixtures.RuleEvaluationTest(methodName="runTest")
        self.fixture.setUp()

    def evaluation(self, environment):
        self.fixture.scope["environment"] = environment
        self.fixture.save_evidence()
        return self.fixture.evaluate()

    def create(
        self,
        context,
        evaluation,
        *,
        environment,
        pr=None,
        now=fixtures.NOW,
        org=None,
        pack="a" * 40,
    ):
        f = self.fixture
        with get_engine().begin() as db:
            return create_snapshot(
                db,
                org or f.org,
                f.product,
                context=context,
                binding_id=f.binding,
                pull_request_number=pr,
                environment=environment,
                git_sha=fixtures.COMMIT,
                pack_sha=pack,
                evaluation_ids=[evaluation["id"]],
                now=now,
            )

    def test_pr_and_production_baseline_are_separate_and_keep_evidence(self):
        f = self.fixture
        pr_evaluation = self.evaluation("pr")
        prod_evaluation = self.evaluation("production")
        pr = self.create("pull_request", pr_evaluation, environment="pr", pr=17)
        baseline = self.create("baseline", prod_evaluation, environment="production")
        self.assertNotEqual(pr["id"], baseline["id"])
        self.assertEqual((pr["context"], pr["pullRequestNumber"]), ("pull_request", 17))
        self.assertEqual(
            (baseline["context"], baseline["pullRequestNumber"]), ("baseline", None)
        )
        self.assertEqual(pr["evidenceIds"], pr_evaluation["evidenceIds"])
        self.assertEqual(baseline["evidenceIds"], prod_evaluation["evidenceIds"])
        self.assertEqual(pr["counts"]["PASS"], 1)
        with get_engine().begin() as db:
            self.assertEqual(get_snapshot(db, f.org, pr["id"]), pr)
            self.assertIsNone(get_snapshot(db, f.other, pr["id"]))
            self.assertEqual(
                {item["id"] for item in list_snapshots(db, f.org, f.product)},
                {pr["id"], baseline["id"]},
            )

    def test_invalid_context_scope_and_stale_evidence_are_rejected(self):
        f = self.fixture
        evaluation = self.evaluation("pr")
        with self.assertRaises(ValueError):
            self.create("pull_request", evaluation, environment="pr")
        with self.assertRaises(ValueError):
            self.create("baseline", evaluation, environment="pr", pr=17)
        with self.assertRaises(ValueError):
            self.create("baseline", evaluation, environment="production")
        with self.assertRaises(ValueError):
            self.create("baseline", evaluation, environment="pr", pack="c" * 40)
        with self.assertRaises(ValueError):
            self.create(
                "baseline",
                evaluation,
                environment="pr",
                now=fixtures.NOW + timedelta(seconds=60),
            )
        with self.assertRaises(LookupError):
            self.create("baseline", evaluation, environment="pr", org=f.other)

    def test_newer_scan_invalidates_old_evaluation_for_new_snapshots(self):
        f = self.fixture
        evaluation = self.evaluation("pr")
        with get_engine().begin() as db:
            run_openapi_scan(
                db,
                f.binding,
                fixtures.Source(),
                "main",
                fixtures.NOW + timedelta(seconds=1),
            )
        with self.assertRaises(ValueError):
            self.create(
                "baseline",
                evaluation,
                environment="pr",
                now=fixtures.NOW + timedelta(seconds=1),
            )


if __name__ == "__main__":
    unittest.main()

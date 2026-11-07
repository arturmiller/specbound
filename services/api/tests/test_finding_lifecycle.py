"""Findings are stable per context and preserve assessment history."""

import copy
import os
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta

import test_assessment_snapshots as snapshots_fixture
import test_rule_evaluation as rule_fixture
from app.database import get_engine
from app.findings import apply_snapshot, get_history, list_findings


class FindingLifecycleTest(unittest.TestCase):
    def setUp(self):
        if not os.environ.get("DATABASE_URL"):
            self.fail("DATABASE_URL must point to a disposable migrated database")
        self.snapshots = snapshots_fixture.AssessmentSnapshotsTest(methodName="runTest")
        self.snapshots.setUp()
        self.f = self.snapshots.fixture
        self.f.scope["environment"] = "production"
        self.f.save_evidence()

    def make_snapshot(self, outcome, seconds, *, context="baseline", pr=None):
        control = copy.deepcopy(self.f.control)
        if outcome == "FAIL":
            control["assertions"][0]["expected"] = True
        if outcome == "UNKNOWN":
            control["assertions"][0]["operator"] = "unsupported"
        evaluation = self.f.evaluate(control=control)
        self.assertEqual(evaluation["status"], outcome)
        return self.snapshots.create(
            context,
            evaluation,
            environment="production",
            pr=pr,
            now=rule_fixture.NOW + timedelta(seconds=seconds),
        )

    def apply(self, snapshot):
        with get_engine().begin() as db:
            return apply_snapshot(db, self.f.org, snapshot["id"])

    def list(self):
        with get_engine().begin() as db:
            return list_findings(db, self.f.org, self.f.product)

    def history(self, finding_id):
        with get_engine().begin() as db:
            return get_history(db, self.f.org, finding_id)

    def test_repeated_failures_share_finding_and_pass_resolves_with_history(self):
        first = self.make_snapshot("FAIL", 0)
        self.apply(first)
        finding = self.list()[0]
        self.assertEqual(finding["status"], "open")
        second = self.make_snapshot("FAIL", 1)
        self.apply(second)
        self.assertEqual(len(self.list()), 1)
        self.assertEqual(self.list()[0]["id"], finding["id"])
        unknown = self.make_snapshot("UNKNOWN", 2)
        self.apply(unknown)
        self.assertEqual(self.list()[0]["status"], "open")
        passed = self.make_snapshot("PASS", 3)
        self.apply(passed)
        self.assertEqual(self.list()[0]["status"], "resolved")
        self.apply(passed)
        self.assertEqual(
            [item["outcome"] for item in self.history(finding["id"])],
            ["FAIL", "FAIL", "UNKNOWN", "PASS"],
        )
        self.apply(first)
        self.assertEqual(self.list()[0]["status"], "resolved")
        self.assertEqual(len(self.history(finding["id"])), 4)

    def test_pr_and_baseline_have_distinct_fingerprints(self):
        baseline = self.make_snapshot("FAIL", 0)
        pr = self.make_snapshot("FAIL", 1, context="pull_request", pr=17)
        self.apply(baseline)
        self.apply(pr)
        findings = self.list()
        self.assertEqual(len(findings), 2)
        self.assertEqual(len({item["fingerprint"] for item in findings}), 2)
        passed = self.make_snapshot("PASS", 2)
        self.apply(passed)
        states = {item["context"]: item["status"] for item in self.list()}
        self.assertEqual(states, {"baseline": "resolved", "pull_request": "open"})

    def test_concurrent_replay_is_idempotent_on_postgresql(self):
        if get_engine().dialect.name != "postgresql":
            self.skipTest("PostgreSQL transaction locking")
        snapshot = self.make_snapshot("FAIL", 0)
        barrier = threading.Barrier(4)

        def apply_concurrently(_):
            barrier.wait(timeout=10)
            return self.apply(snapshot)

        with ThreadPoolExecutor(max_workers=4) as pool:
            list(pool.map(apply_concurrently, range(4)))
        findings = self.list()
        self.assertEqual(len(findings), 1)
        self.assertEqual(len(self.history(findings[0]["id"])), 1)

    def test_late_failure_cannot_open_a_finding_after_a_newer_pass(self):
        old_failure = self.make_snapshot("FAIL", 0)
        newer_pass = self.make_snapshot("PASS", 1)
        self.apply(newer_pass)
        self.apply(old_failure)
        self.assertEqual(self.list(), [])
        with get_engine().begin() as db:
            with self.assertRaises(LookupError):
                apply_snapshot(db, self.f.other, newer_pass["id"])


if __name__ == "__main__":
    unittest.main()

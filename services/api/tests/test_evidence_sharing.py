"""One collector observation is stored once and shared by two control outcomes."""

import copy
import os
import sys
import unittest
from pathlib import Path

import test_rule_evaluation as fixtures
from app.database import get_engine
from app.evidence_sharing import store_and_evaluate
from app.tables import evidence_records, rule_evaluations
from sqlalchemy import func, select

ROOT = Path(__file__).resolve().parents[3]


class EvidenceSharingTest(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.RuleEvaluationTest(methodName="runTest")
        self.fixture.setUp()

    def controls(self):
        first = copy.deepcopy(self.fixture.control)
        second = copy.deepcopy(first)
        second["id"] = "TEST-2"
        second["assertions"][0]["expected"] = True
        return [first, second]

    def execute(self, provider, request, response, *, controls=None, revision="a" * 40):
        f = self.fixture
        with get_engine().begin() as db:
            return store_and_evaluate(
                db,
                f.org,
                provider,
                request,
                response,
                controls or self.controls(),
                revision,
                ttl_seconds=60,
                now=fixtures.NOW,
                scan_id=f.scan_id,
                binding_id=f.binding,
                ref="main",
            )

    def counts(self):
        with get_engine().begin() as db:
            return (
                db.execute(
                    select(func.count())
                    .select_from(evidence_records)
                    .where(evidence_records.c.organization_id == self.fixture.org)
                ).scalar_one(),
                db.execute(
                    select(func.count())
                    .select_from(rule_evaluations)
                    .where(rule_evaluations.c.organization_id == self.fixture.org)
                ).scalar_one(),
            )

    def test_one_observation_is_shared_by_two_independent_results(self):
        f = self.fixture
        result = self.execute(f.provider, f.request, f.response)
        self.assertEqual(self.counts(), (1, 2))
        self.assertEqual(
            [item["status"] for item in result["evaluations"]], ["PASS", "FAIL"]
        )
        self.assertEqual(len({item["id"] for item in result["evaluations"]}), 2)
        self.assertTrue(
            all(
                item["evidenceIds"] == [result["evidence"]["id"]]
                for item in result["evaluations"]
            )
        )

    def test_failure_rolls_back_observation_and_evaluations(self):
        f = self.fixture
        with get_engine().begin() as db:
            with self.assertRaises(ValueError):
                store_and_evaluate(
                    db,
                    f.org,
                    f.provider,
                    f.request,
                    f.response,
                    self.controls(),
                    "not-a-commit",
                    ttl_seconds=60,
                    now=fixtures.NOW,
                    scan_id=f.scan_id,
                    binding_id=f.binding,
                    ref="main",
                )
            count = db.execute(
                select(func.count())
                .select_from(evidence_records)
                .where(evidence_records.c.organization_id == f.org)
            ).scalar_one()
            self.assertEqual(
                count,
                0,
                "savepoint must roll back even if the caller catches the error",
            )
        self.assertEqual(self.counts(), (0, 0))
        wrong = self.controls()
        wrong[1]["requiredEvidence"]["capability"] = "other.example/v1"
        with self.assertRaises(ValueError):
            self.execute(f.provider, f.request, f.response, controls=wrong)
        self.assertEqual(self.counts(), (0, 0))

    @unittest.skipUnless(
        os.environ.get("SPECBOUND_DOCKER_TESTS") == "1", "Docker integration disabled"
    )
    def test_real_collector_runs_once_then_both_controls_reuse_its_observation(self):
        import docker

        sys.path.insert(0, str(ROOT / "services" / "worker"))
        sys.path.insert(0, str(ROOT / "services" / "worker" / "tests"))
        from collector_runner import ApprovedCollector, run_collector
        from test_collector_runner import IMAGE, SCRIPT, fixture

        command = ("python", "-c", SCRIPT)
        provider, _ = fixture(command)
        f = self.fixture
        result = run_collector(
            docker.from_env(), provider, f.request, ApprovedCollector(IMAGE, command)
        )
        self.assertEqual(result.status, "OBSERVED")
        stored = self.execute(
            provider,
            f.request,
            {"schemaVersion": 1, "observations": list(result.observations)},
        )
        self.assertEqual(self.counts(), (1, 2))
        self.assertEqual(
            [item["status"] for item in stored["evaluations"]], ["PASS", "FAIL"]
        )
        self.assertTrue(
            all(
                item["evidenceIds"] == [stored["evidence"]["id"]]
                for item in stored["evaluations"]
            )
        )

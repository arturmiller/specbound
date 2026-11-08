"""Persist separate PR and baseline snapshots without crossing evidence scope."""

import os
import unittest
from datetime import timedelta

import test_rule_evaluation as fixtures
from app.coverage import run_openapi_scan
from app.database import get_engine
from app.findings import apply_snapshot
from app.identity import get_current_principal
from app.main import app
from app.snapshots import create_snapshot, get_snapshot, list_snapshots
from fastapi.testclient import TestClient


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

    def test_exact_report_contains_provenance_and_forbids_foreign_org(self):
        f = self.fixture
        f.save_evidence()
        control = {
            **f.control,
            "assertions": [
                {"path": "publicly_reachable", "operator": "equals", "expected": True}
            ],
        }
        evaluation = f.evaluate(control=control)
        pr = self.create("pull_request", evaluation, environment="test", pr=17)
        baseline = self.create("baseline", evaluation, environment="test")
        with get_engine().begin() as db:
            apply_snapshot(db, f.org, pr["id"])
        app.dependency_overrides[get_current_principal] = lambda: "owner"
        try:
            with TestClient(app) as client:
                response = client.get(f"/assessments/{pr['id']}")
                self.assertEqual(response.status_code, 200, response.text)
                report = response.json()
                self.assertEqual(report["assessment"]["id"], pr["id"])
                self.assertNotEqual(report["assessment"]["id"], baseline["id"])
                self.assertEqual(report["assessment"]["gitSha"], fixtures.COMMIT)
                self.assertEqual(
                    report["evaluations"][0]["control"]["id"], control["id"]
                )
                self.assertTrue(
                    report["evaluations"][0]["subject"]["provenance"][
                        "sourceRef"
                    ].startswith("repo:")
                )
                self.assertEqual(
                    report["evidence"][0]["value"], {"publicly_reachable": False}
                )
                self.assertEqual(report["findings"][0]["outcome"], "FAIL")
                app.dependency_overrides[get_current_principal] = lambda: (
                    "foreign-owner"
                )
                self.assertEqual(
                    client.get(f"/assessments/{pr['id']}").status_code, 403
                )
        finally:
            app.dependency_overrides.clear()

    def test_overview_limits_findings_and_products_to_visible_teams(self):
        f = self.fixture
        f.save_evidence()
        control = {
            **f.control,
            "assertions": [
                {"path": "publicly_reachable", "operator": "equals", "expected": True}
            ],
        }
        evaluation = f.evaluate(control=control)
        snapshot = self.create("pull_request", evaluation, environment="test", pr=17)
        with get_engine().begin() as db:
            apply_snapshot(db, f.org, snapshot["id"])
        app.dependency_overrides[get_current_principal] = lambda: "owner"
        try:
            with TestClient(app) as client:
                second_team = client.post(
                    f"/organizations/{f.org}/teams", json={"name": "Private"}
                ).json()["id"]
                second_product = client.post(
                    f"/organizations/{f.org}/products",
                    json={"name": "Private product", "ownerTeamId": second_team},
                ).json()["id"]
                self.assertEqual(
                    client.post(
                        f"/teams/{f.team}/members",
                        json={"principalId": "user:viewer", "role": "viewer"},
                    ).status_code,
                    201,
                )
                app.dependency_overrides[get_current_principal] = lambda: "user:viewer"
                result = client.get(f"/organizations/{f.org}/overview")
                self.assertEqual(result.status_code, 200, result.text)
                body = result.json()
                self.assertEqual([p["id"] for p in body["products"]], [f.product])
                self.assertNotIn(second_product, [p["id"] for p in body["products"]])
                self.assertEqual(body["findings"][0]["snapshotId"], snapshot["id"])
                app.dependency_overrides[get_current_principal] = lambda: "outsider"
                self.assertEqual(
                    client.get(f"/organizations/{f.org}/overview").status_code, 403
                )
        finally:
            app.dependency_overrides.clear()

    def test_missing_provider_is_unknown_with_explicit_coverage(self):
        f = self.fixture
        evaluation = f.evaluate()
        self.assertEqual(evaluation["status"], "UNKNOWN")
        snapshot = self.create("pull_request", evaluation, environment="test", pr=17)
        app.dependency_overrides[get_current_principal] = lambda: "owner"
        try:
            with TestClient(app) as client:
                overview = client.get(f"/organizations/{f.org}/overview").json()
                assessment = next(
                    item
                    for item in overview["assessments"]
                    if item["id"] == snapshot["id"]
                )
                self.assertEqual(assessment["counts"]["UNKNOWN"], 1)
                self.assertEqual(assessment["counts"]["PASS"], 0)
                self.assertEqual(assessment["context"], "pull_request")
                self.assertEqual(assessment["pullRequestNumber"], 17)
                self.assertTrue(assessment["createdAt"])
                self.assertIn("Nachweis fehlt", assessment["evaluations"][0]["reason"])
                report = client.get(f"/assessments/{snapshot['id']}").json()
                self.assertEqual(report["evaluations"][0]["status"], "UNKNOWN")
                self.assertEqual(
                    report["evaluations"][0]["coverage"]["status"], "covered"
                )
                self.assertEqual(report["evidence"], [])
        finally:
            app.dependency_overrides.clear()

    def test_report_keeps_missing_coverage_and_not_applicable_distinct(self):
        f = self.fixture
        unknown = f.evaluate(scan_id=None)
        self.assertEqual(unknown["status"], "UNKNOWN")
        unknown_snapshot = self.create(
            "pull_request", unknown, environment="test", pr=17
        )
        not_applicable = f.evaluate(
            control={**f.control, "target": {"kind": "api.schema"}}
        )
        self.assertEqual(not_applicable["status"], "NOT_APPLICABLE")
        na_snapshot = self.create(
            "pull_request", not_applicable, environment="test", pr=18
        )
        app.dependency_overrides[get_current_principal] = lambda: "owner"
        try:
            with TestClient(app) as client:
                no_coverage = client.get(
                    f"/assessments/{unknown_snapshot['id']}"
                ).json()["evaluations"][0]
                self.assertEqual(no_coverage["status"], "UNKNOWN")
                self.assertIsNone(no_coverage["coverage"])
                self.assertIn("Quellabdeckung", no_coverage["reason"])
                na = client.get(f"/assessments/{na_snapshot['id']}").json()[
                    "evaluations"
                ][0]
                self.assertEqual(na["status"], "NOT_APPLICABLE")
                self.assertTrue(na["reason"])
                self.assertEqual(na["coverage"]["status"], "covered")
        finally:
            app.dependency_overrides.clear()

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

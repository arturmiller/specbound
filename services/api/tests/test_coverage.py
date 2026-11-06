"""Persist real scanner outcomes and apply them to affected assessments."""

import os
import unittest
from datetime import datetime, timezone

from app.assessment import Applicability, AssessmentStatus, RuleOutcome
from app.coverage import assess_with_scan, get_scan, run_openapi_scan
from app.database import get_engine
from app.git_source import GitSnapshot, SourceNotFound
from app.identity import get_current_principal
from app.main import app
from fastapi.testclient import TestClient

COMMIT = "a" * 40
WHEN = datetime(2026, 1, 1, tzinfo=timezone.utc)


class FixtureSource:
    def __init__(self, files=None):
        self.files = files

    def fetch(self, ref):
        if self.files is None:
            raise SourceNotFound("source missing")
        return GitSnapshot(COMMIT, self.files)


class CoverageIntegrationTest(unittest.TestCase):
    def setUp(self):
        if not os.environ.get("DATABASE_URL"):
            self.fail("DATABASE_URL must point to a disposable migrated database")
        app.dependency_overrides[get_current_principal] = lambda: "user:owner"
        self.client = TestClient(app)
        org = self.client.post("/organizations", json={"name": "Coverage"}).json()["id"]
        team = self.client.post(
            f"/organizations/{org}/teams", json={"name": "Owner"}
        ).json()["id"]
        self.product = self.client.post(
            f"/organizations/{org}/products",
            json={"name": "Product", "ownerTeamId": team},
        ).json()["id"]
        self.binding = self.client.post(
            f"/products/{self.product}/repositories",
            json={"provider": "example", "repository": "org/repo"},
        ).json()["id"]

    def tearDown(self):
        self.client.close()
        app.dependency_overrides.clear()

    def scan(self, files):
        with get_engine().begin() as db:
            return run_openapi_scan(
                db, self.binding, FixtureSource(files), "main", WHEN
            )

    def assess(self, scan_id, *, binding=None, commit=COMMIT):
        with get_engine().begin() as db:
            return assess_with_scan(
                db,
                scan_id=scan_id,
                product_id=self.product,
                binding_id=binding or self.binding,
                ref="main",
                expected_commit=commit,
                applicability=Applicability.APPLICABLE,
                evidence_ids=("evidence:1",),
                outcome=RuleOutcome.PASS,
                outcome_reason="OK",
            )

    def test_missing_source_is_persisted_and_cannot_produce_pass(self):
        scan = self.scan(None)
        self.assertEqual(scan["status"], "failed")
        self.assertIsNone(scan["commit"])
        self.assertEqual(scan["files"], [])
        with get_engine().begin() as db:
            self.assertEqual(get_scan(db, scan["id"])["status"], "failed")
        self.assertEqual(self.assess(scan["id"]).status, AssessmentStatus.UNKNOWN)
        self.assertEqual(self.assess(None).status, AssessmentStatus.UNKNOWN)

    def test_covered_scope_is_persisted_and_must_match_repository_and_commit(self):
        files = {"openapi.json": b'{"openapi":"3.1.0","paths":{"/pets":{}}}'}
        scan = self.scan(files)
        self.assertEqual(scan["status"], "covered")
        self.assertEqual(scan["commit"], COMMIT)
        self.assertEqual(scan["files"], ["openapi.json"])
        with get_engine().begin() as db:
            self.assertEqual(get_scan(db, scan["id"])["files"], ["openapi.json"])
        self.assertEqual(self.assess(scan["id"]).status, AssessmentStatus.PASS)
        self.assertEqual(
            self.assess(scan["id"], commit="b" * 40).status, AssessmentStatus.UNKNOWN
        )
        self.assertEqual(
            self.assess(scan["id"], binding="different").status,
            AssessmentStatus.UNKNOWN,
        )
        missing = self.scan(None)
        self.assertEqual(missing["status"], "failed")
        self.assertEqual(self.assess(scan["id"]).status, AssessmentStatus.UNKNOWN)

    def test_partial_scope_cannot_produce_pass(self):
        scan = self.scan(
            {
                "openapi.json": b'{"openapi":"3.1.0","paths":{}}',
                "broken.openapi.json": b"{",
            }
        )
        self.assertEqual(scan["status"], "partial")
        self.assertEqual(scan["files"], ["broken.openapi.json", "openapi.json"])
        self.assertEqual(scan["errors"][0]["path"], "broken.openapi.json")
        self.assertEqual(self.assess(scan["id"]).status, AssessmentStatus.UNKNOWN)

    def test_unresolved_references_do_not_claim_complete_coverage(self):
        for target in ("missing.yaml#/Pet", "#/components/schemas/Absent"):
            with self.subTest(target=target):
                payload = (
                    '{"openapi":"3.1.0","paths":{"/pets":{"$ref":"' + target + '"}}}'
                ).encode()
                scan = self.scan({"openapi.json": payload})
                self.assertEqual(scan["status"], "partial")
                self.assertEqual(len(scan["subjects"]), 1)
                self.assertEqual(
                    self.assess(scan["id"]).status, AssessmentStatus.UNKNOWN
                )


if __name__ == "__main__":
    unittest.main()

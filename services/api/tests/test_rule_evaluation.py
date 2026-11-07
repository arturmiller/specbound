"""Rule assessments persist reasons and require current, scoped evidence and coverage."""

import copy
import os
import unittest
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.coverage import run_openapi_scan
from app.database import get_engine
from app.evidence_records import store_evidence
from app.git_source import GitSnapshot
from app.rule_evaluation import evaluate_and_store, get_evaluation
from app.tables import organizations, products, repo_bindings, teams
from sqlalchemy import insert
from test_evidence_records import CAPABILITY, provider_fixture

NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)
COMMIT = "b" * 40


class Source:
    def fetch(self, ref):
        return GitSnapshot(
            COMMIT, {"openapi.json": b'{"openapi":"3.1.0","paths":{"/pets":{}}}'}
        )


class RuleEvaluationTest(unittest.TestCase):
    def setUp(self):
        if not os.environ.get("DATABASE_URL"):
            self.fail("DATABASE_URL must point to a disposable migrated database")
        self.org, self.other, self.team, self.product, self.binding = (
            str(uuid4()) for _ in range(5)
        )
        with get_engine().begin() as db:
            db.execute(
                insert(organizations),
                [
                    {"id": self.org, "name": "One", "owner_principal_id": "owner"},
                    {"id": self.other, "name": "Other", "owner_principal_id": "other"},
                ],
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
                    provider="git",
                    repository="org/repo",
                )
            )
            scan = run_openapi_scan(db, self.binding, Source(), "main", NOW)
        self.scan_id = scan["id"]
        self.subject = scan["subjects"][0]
        self.scope = {
            "productId": self.product,
            "environment": "test",
            "targetRevision": COMMIT,
        }
        self.provider = provider_fixture()
        self.request = {
            "schemaVersion": 1,
            "subject": self.subject,
            "scope": self.scope,
            "credentialsRef": None,
            "capabilities": [CAPABILITY],
        }
        self.response = {
            "schemaVersion": 1,
            "observations": [
                {
                    "subjectId": self.subject["id"],
                    "capability": CAPABILITY,
                    "scope": self.scope,
                    "observedAt": NOW.isoformat(),
                    "provenance": {"sourceRef": "collector:fixture"},
                    "value": {"publicly_reachable": False},
                }
            ],
        }
        self.control = {
            "id": "TEST-1",
            "target": {"kind": "api.path"},
            "requiredEvidence": {"capability": CAPABILITY},
            "assertions": [
                {"path": "publicly_reachable", "operator": "equals", "expected": False}
            ],
        }

    def save_evidence(self):
        with get_engine().begin() as db:
            return store_evidence(
                db,
                self.org,
                self.provider,
                self.request,
                self.response,
                ttl_seconds=60,
                now=NOW,
            )[0]

    def evaluate(
        self, *, control=None, subject=None, now=NOW, scan_id="default", org=None
    ):
        with get_engine().begin() as db:
            return evaluate_and_store(
                db,
                org or self.org,
                self.scope,
                subject or self.subject,
                control or self.control,
                "a" * 40,
                now=now,
                scan_id=self.scan_id if scan_id == "default" else scan_id,
                binding_id=self.binding,
                ref="main",
            )

    def test_pass_fail_unknown_na_and_expired_are_persisted(self):
        evidence = self.save_evidence()
        passed = self.evaluate(now=NOW + timedelta(seconds=59))
        self.assertEqual(
            (passed["status"], passed["evidenceIds"]), ("PASS", [evidence["id"]])
        )
        with get_engine().begin() as db:
            self.assertEqual(get_evaluation(db, self.org, passed["id"]), passed)
            self.assertIsNone(get_evaluation(db, self.other, passed["id"]))
        failed_control = copy.deepcopy(self.control)
        failed_control["assertions"][0]["expected"] = True
        failed = self.evaluate(control=failed_control)
        self.assertEqual(failed["status"], "FAIL")
        unknown = self.evaluate(scan_id=None)
        self.assertEqual(unknown["status"], "UNKNOWN")
        self.assertEqual(unknown["evidenceIds"], [])
        backdated = self.evaluate(now=NOW - timedelta(seconds=1))
        self.assertEqual(backdated["status"], "UNKNOWN")
        self.assertIn("Quellabdeckung", backdated["reason"])
        na_control = copy.deepcopy(self.control)
        na_control["target"]["kind"] = "database"
        self.assertEqual(self.evaluate(control=na_control)["status"], "NOT_APPLICABLE")
        stale = self.evaluate(now=NOW + timedelta(seconds=60))
        self.assertEqual((stale["status"], stale["evidenceIds"]), ("UNKNOWN", []))
        for item in (passed, failed, unknown, stale):
            self.assertTrue(item["reason"])

    def test_unverified_subject_scope_and_ambiguous_evidence_are_unknown(self):
        self.save_evidence()
        modified = copy.deepcopy(self.subject)
        modified["scope"]["targetRevision"] = "c" * 40
        self.assertEqual(self.evaluate(subject=modified)["status"], "UNKNOWN")
        self.save_evidence()
        self.assertEqual(self.evaluate()["status"], "UNKNOWN")
        with self.assertRaises(LookupError):
            self.evaluate(org=self.other)


if __name__ == "__main__":
    unittest.main()

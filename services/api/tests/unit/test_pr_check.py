"""Commit-specific checks fail closed on stale or insufficient evidence."""

import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from app.pr_check import assess_snapshot, publish_check
from app.tables import (
    evidence_records,
    metadata,
    repo_bindings,
    rule_evaluations,
    scanner_coverage,
)
from sqlalchemy import create_engine, insert

NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)
SHA = "a" * 40


class CheckTest(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://")
        metadata.create_all(
            self.engine,
            tables=[
                repo_bindings,
                scanner_coverage,
                rule_evaluations,
                evidence_records,
            ],
        )
        self.snapshot = {
            "organization_id": "org",
            "product_id": "product",
            "binding_id": "binding",
            "environment": "test",
            "git_sha": SHA,
            "pack_sha": "b" * 40,
            "evaluation_ids": ["evaluation"],
            "counts": {"PASS": 1, "FAIL": 0, "UNKNOWN": 0, "NOT_APPLICABLE": 0},
            "evaluations": [
                {
                    "id": "evaluation",
                    "status": "PASS",
                    "subjectId": "subject",
                    "controlId": "control",
                    "evidenceIds": ["evidence"],
                }
            ],
        }
        with self.engine.begin() as db:
            db.execute(
                insert(repo_bindings).values(
                    id="binding",
                    product_id="product",
                    provider="github",
                    repository="org/repo",
                )
            )
            db.execute(
                insert(scanner_coverage).values(
                    id=1,
                    binding_id="binding",
                    scanner="openapi-v1",
                    ref="main",
                    status="covered",
                    source_revision=SHA,
                    observed_at=NOW,
                    files=[],
                    errors=[],
                )
            )
            db.execute(
                insert(rule_evaluations).values(
                    id="evaluation",
                    organization_id="org",
                    product_id="product",
                    subject_id="subject",
                    environment="test",
                    target_revision=SHA,
                    control_id="control",
                    governance_revision="b" * 40,
                    scan_id=1,
                    status="PASS",
                    evidence_ids=["evidence"],
                    control={"requiredEvidence": {"capability": "cap"}},
                    subject={},
                    evaluated_at=NOW,
                )
            )
            db.execute(
                insert(evidence_records).values(
                    id="evidence",
                    organization_id="org",
                    product_id="product",
                    subject_id="subject",
                    capability="cap",
                    environment="test",
                    target_revision=SHA,
                    observed_at=NOW,
                    expires_at=NOW + timedelta(seconds=60),
                    ttl_seconds=60,
                )
            )

    def tearDown(self):
        self.engine.dispose()

    def test_success_requires_current_evidence_and_coverage(self):
        with self.engine.connect() as db:
            self.assertEqual(assess_snapshot(db, self.snapshot, NOW)[0], "success")
            self.assertEqual(
                assess_snapshot(db, self.snapshot, NOW + timedelta(seconds=60)),
                ("failure", None),
            )
            self.snapshot["counts"]["UNKNOWN"] = 1
            self.assertEqual(assess_snapshot(db, self.snapshot, NOW), ("failure", None))

    def test_no_evaluations_is_not_a_pass(self):
        self.snapshot.update(
            counts=dict.fromkeys(("PASS", "FAIL", "UNKNOWN", "NOT_APPLICABLE"), 0),
            evaluations=[],
            evaluation_ids=[],
        )
        with self.engine.connect() as db:
            self.assertEqual(assess_snapshot(db, self.snapshot, NOW), ("failure", None))

    def test_fail_and_unknown_are_never_success(self):
        with self.engine.connect() as db:
            for status in ("FAIL", "UNKNOWN"):
                self.snapshot["counts"] = {
                    "PASS": 0,
                    "FAIL": 0,
                    "UNKNOWN": 0,
                    "NOT_APPLICABLE": 0,
                }
                self.snapshot["counts"][status] = 1
                self.snapshot["evaluations"][0]["status"] = status
                self.assertEqual(
                    assess_snapshot(db, self.snapshot, NOW), ("failure", None)
                )

    def test_check_is_bound_to_exact_sha_and_old_head_cannot_publish(self):
        class Source:
            repository = "org/repo"
            app_id = "42"

            def __init__(self):
                self.head = SHA
                self.posts = []

            def _token(self, *, permissions):
                assert permissions == {"pull_requests": "read", "checks": "write"}
                return "token"

            def _request(self, method, path, token, **kwargs):
                if "/pulls/" in path:
                    return {"head": {"sha": self.head}}
                if method == "GET":
                    return {"check_runs": []}
                self.posts.append(kwargs["json"])
                return {"id": 1}

        source = Source()
        job = {"id": "job", "pull_request_number": 7, "head_sha": SHA}
        with self.engine.connect() as db:
            source.head = "c" * 40
            self.assertIsNone(publish_check(db, source, job, self.snapshot, "", NOW))
            self.assertEqual(source.posts, [])
            source.head = SHA
            with patch(
                "app.pr_check.assess_snapshot",
                return_value=("success", NOW + timedelta(seconds=60)),
            ):
                publish_check(db, source, job, self.snapshot, "", NOW)
        self.assertEqual(source.posts[0]["head_sha"], SHA)
        self.assertEqual(source.posts[0]["conclusion"], "success")

    def test_superseded_existing_check_is_failed_on_its_own_sha(self):
        class Source:
            repository = "org/repo"
            app_id = "42"

            def __init__(self):
                self.patched = []

            def _token(self, *, permissions):
                return "token"

            def _request(self, method, path, token, **kwargs):
                if "/pulls/" in path:
                    return {"head": {"sha": "c" * 40}}
                if method == "GET":
                    self.path = path
                    return {
                        "check_runs": [
                            {
                                "id": 10,
                                "name": "Specbound assessment",
                                "external_id": "job",
                                "app": {"id": 42},
                            }
                        ]
                    }
                self.patched.append((method, path, kwargs["json"]))
                return {"id": 10}

        source = Source()
        publish_check(
            None,
            source,
            {"id": "job", "pull_request_number": 7, "head_sha": SHA},
            {},
            "",
            NOW,
        )
        self.assertIn(SHA, source.path)
        self.assertEqual(source.patched[0][0], "PATCH")
        self.assertEqual(source.patched[0][2]["conclusion"], "failure")
        self.assertNotIn("head_sha", source.patched[0][2])


if __name__ == "__main__":
    unittest.main()

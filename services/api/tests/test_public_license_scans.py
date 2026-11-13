"""Portal scan requests and worker leases use real scoped PostgreSQL data."""

import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

from app.database import get_engine
from app.identity import get_current_principal
from app.main import app
from app.tables import (
    assessment_snapshots,
    evidence_records,
    findings,
    principals,
    public_license_scans,
)
from fastapi.testclient import TestClient
from sqlalchemy import func, insert, select, update

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "worker"))
from public_license_worker import claim, finish, poll_once  # noqa: E402


class PublicLicenseScansTest(unittest.TestCase):
    def setUp(self):
        self.owner = f"user:{uuid4()}"
        self.viewer = f"user:{uuid4()}"
        self.other = f"user:{uuid4()}"
        with get_engine().begin() as db:
            for principal in (self.owner, self.viewer, self.other):
                db.execute(
                    insert(principals).values(
                        id=principal, kind="user", issuer="test", subject=principal
                    )
                )
        app.dependency_overrides[get_current_principal] = lambda: self.owner
        self.client = TestClient(app)
        self.org = self.client.post(
            "/organizations", json={"name": "License test"}
        ).json()["id"]
        self.team = self.client.post(
            f"/organizations/{self.org}/teams", json={"name": "Review team"}
        ).json()["id"]
        self.product = self.client.post(
            f"/organizations/{self.org}/products",
            json={"name": "Test product", "ownerTeamId": self.team},
        ).json()["id"]
        self.binding = self.client.post(
            f"/products/{self.product}/repositories",
            json={"provider": "github", "repository": "example/public"},
        ).json()["id"]
        self.url = (
            f"/products/{self.product}/repositories/{self.binding}/public-license-scans"
        )

    def tearDown(self):
        self.client.close()
        app.dependency_overrides.clear()

    def test_scan_job_worker_and_result_survive_reload_without_fake_assessment(self):
        response = self.client.post(self.url, json={"ref": "main"})
        self.assertEqual(response.status_code, 201, response.text)
        job = response.json()
        self.assertEqual(job["status"], "pending")
        self.assertEqual(
            self.client.post(self.url, json={"ref": "main"}).status_code, 409
        )
        result = {
            "requestedRef": "main",
            "sourceRevision": "a" * 40,
            "coverage": "covered",
            "files": ["uv.lock"],
            "unsupportedFiles": [],
            "packages": [{"name": "sample", "version": "1.0", "status": "FAIL"}],
        }
        self.assertTrue(
            poll_once(
                get_engine(),
                execute=lambda repository, ref: {"status": "ok", "result": result},
            )
        )
        stored = self.client.get(self.url).json()[0]
        self.assertEqual(
            (stored["id"], stored["status"], stored["result"]),
            (job["id"], "completed", result),
        )
        with get_engine().connect() as db:
            for table in (assessment_snapshots, evidence_records, findings):
                self.assertEqual(
                    db.execute(
                        select(func.count())
                        .select_from(table)
                        .where(table.c.organization_id == self.org)
                    ).scalar_one(),
                    0,
                )

    def test_license_evidence_assessment_and_finding_lifecycle(self):
        def run_scan(expression):
            job = self.client.post(self.url, json={"ref": "main"}).json()
            artifact = {
                "sourceUrl": "https://files.pythonhosted.org/packages/ab/sample.whl.metadata",
                "sourceKind": "distribution-metadata",
                "artifactSha256": "a" * 64,
                "metadataSha256": "b" * 64,
                "licenseExpression": expression,
            }
            package = {
                "path": "uv.lock",
                "name": "sample",
                "version": "1.0",
                "source": "pypi",
                "markers": [],
                "licenseExpression": expression,
                "metadata": {"status": "OBSERVED", "artifacts": [artifact]},
            }
            result = {
                "sourceRevision": "a" * 40,
                "sourceCoverage": "covered",
                "coverage": "covered",
                "files": ["uv.lock"],
                "unsupportedFiles": [],
                "packages": [package],
            }
            self.assertTrue(
                poll_once(
                    get_engine(), execute=lambda *_: {"status": "ok", "result": result}
                )
            )
            stored = next(
                item
                for item in self.client.get(self.url).json()
                if item["id"] == job["id"]
            )
            self.assertIsNotNone(stored["assessmentId"], stored)
            return job, stored

        job, failed = run_scan("GPL-3.0-only")
        with get_engine().connect() as db:
            snapshot = (
                db.execute(
                    select(assessment_snapshots).where(
                        assessment_snapshots.c.id == failed["assessmentId"]
                    )
                )
                .mappings()
                .one()
            )
            evidence = (
                db.execute(
                    select(evidence_records).where(
                        evidence_records.c.producer_scan_id == job["id"]
                    )
                )
                .mappings()
                .one()
            )
            finding = (
                db.execute(
                    select(findings).where(findings.c.organization_id == self.org)
                )
                .mappings()
                .one()
            )
            self.assertEqual(
                (snapshot["context"], snapshot["pull_request_number"]),
                ("repository", None),
            )
            self.assertEqual(
                snapshot["pack_sha"], "22c819b631d60fc0f561f376379e9de85edfe96c"
            )
            self.assertEqual(
                (
                    evidence["producer_kind"],
                    evidence["collector_revision"],
                    evidence["collector_image"],
                ),
                ("public-license-scan", None, None),
            )
            self.assertEqual(finding["status"], "open")
        app.dependency_overrides[get_current_principal] = lambda: self.other
        self.assertEqual(
            self.client.get(f"/assessments/{failed['assessmentId']}").status_code, 403
        )
        app.dependency_overrides[get_current_principal] = lambda: self.owner
        self.assertEqual(
            self.client.get(f"/assessments/{failed['assessmentId']}").status_code, 200
        )
        unknown_job, unknown = run_scan(None)
        with get_engine().connect() as db:
            self.assertEqual(
                db.execute(
                    select(findings.c.status).where(findings.c.id == finding["id"])
                ).scalar_one(),
                "open",
            )
            self.assertEqual(
                db.execute(
                    select(func.count())
                    .select_from(evidence_records)
                    .where(evidence_records.c.producer_scan_id == unknown_job["id"])
                ).scalar_one(),
                0,
            )
        self.assertEqual(
            self.client.get(f"/assessments/{unknown['assessmentId']}").json()[
                "assessment"
            ]["counts"]["UNKNOWN"],
            1,
        )
        run_scan("MIT")
        with get_engine().connect() as db:
            self.assertEqual(
                db.execute(
                    select(findings.c.status).where(findings.c.id == finding["id"])
                ).scalar_one(),
                "resolved",
            )

    def test_viewer_can_read_but_cannot_start_or_access_other_organization(self):
        self.assertEqual(
            self.client.post(
                f"/teams/{self.team}/members",
                json={"principalId": self.viewer, "role": "viewer"},
            ).status_code,
            201,
        )
        app.dependency_overrides[get_current_principal] = lambda: self.viewer
        self.assertEqual(self.client.get(self.url).status_code, 200)
        self.assertEqual(
            self.client.post(self.url, json={"ref": "main"}).status_code, 403
        )
        app.dependency_overrides[get_current_principal] = lambda: self.other
        self.assertEqual(self.client.get(self.url).status_code, 403)
        self.assertEqual(
            self.client.post(self.url, json={"ref": "main"}).status_code, 403
        )

    def test_input_and_failure_are_explicit(self):
        self.assertEqual(
            self.client.post(
                self.url, json={"ref": "main", "command": "sh"}
            ).status_code,
            422,
        )
        self.assertEqual(self.client.post(self.url, json={"ref": ""}).status_code, 422)
        self.assertEqual(
            self.client.post(self.url, json={"ref": "main"}).status_code, 201
        )
        poll_once(
            get_engine(),
            execute=lambda *_: {"status": "error", "errorCode": "rate-limited"},
        )
        run = self.client.get(self.url).json()[0]
        self.assertEqual(
            (run["status"], run["errorCode"], run["result"]),
            ("failed", "rate-limited", None),
        )

    def test_expired_lease_cannot_publish_old_result(self):
        job = self.client.post(self.url, json={"ref": "main"}).json()
        now = datetime.now(timezone.utc)
        with get_engine().begin() as db:
            old = claim(db, now=now)
            db.execute(
                update(public_license_scans)
                .where(public_license_scans.c.id == job["id"])
                .values(lease_until=now - timedelta(seconds=1))
            )
            new = claim(db, now=now)
            self.assertFalse(finish(db, old, {"status": "ok", "result": {}}, now=now))
            self.assertTrue(
                finish(
                    db,
                    new,
                    {"status": "ok", "result": {"sourceRevision": "a" * 40}},
                    now=now,
                )
            )

    def test_changed_repository_cannot_receive_an_old_scan_result(self):
        job = self.client.post(self.url, json={"ref": "main"}).json()
        now = datetime.now(timezone.utc)
        with get_engine().begin() as db:
            lease = claim(db, now=now)
        changed = self.client.patch(
            f"/products/{self.product}/repositories/{self.binding}",
            json={"provider": "github", "repository": "different/repo"},
        )
        self.assertEqual(changed.status_code, 200)
        with get_engine().begin() as db:
            self.assertTrue(
                finish(
                    db,
                    lease,
                    {"status": "ok", "result": {"sourceRevision": "a" * 40}},
                    now=now,
                )
            )
            row = (
                db.execute(
                    select(public_license_scans).where(
                        public_license_scans.c.id == job["id"]
                    )
                )
                .mappings()
                .one()
            )
            self.assertEqual(
                (row["status"], row["error_code"], row["result"]),
                ("failed", "source-changed", None),
            )
        self.assertEqual(self.client.get(self.url).json(), [])


if __name__ == "__main__":
    unittest.main()

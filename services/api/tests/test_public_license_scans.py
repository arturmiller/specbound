"""Portal scan requests and worker leases use real scoped PostgreSQL data."""

import copy
import json
import os
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from app.database import get_engine
from app.identity import get_current_principal
from app.main import app
from app.pack_catalog import github_source_factory
from app.tables import (
    assessment_snapshots,
    evidence_records,
    findings,
    principals,
    public_license_scans,
)
from fastapi.testclient import TestClient
from sqlalchemy import func, insert, select, update

from tests.test_resource_registry import ResourceFixtureSource

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

    def configure_native_product(
        self, *, allowed=None, unbound=False, license_controls=1, attach_existing=False
    ):
        self.source = ResourceFixtureSource("example/governance")
        if allowed:
            profile = json.loads(
                self.source.files["profiles/application-baseline.json"]
            )
            profile["profile"]["modify"]["set-parameters"][0]["values"] = allowed
            self.source.files["profiles/application-baseline.json"] = json.dumps(
                profile
            ).encode()
        if unbound:
            catalog = json.loads(self.source.files["catalogs/application.json"])
            catalog["catalog"]["groups"][0]["controls"].append(
                {"id": "UNBOUND-001", "title": "Manual governance requirement"}
            )
            self.source.files["catalogs/application.json"] = json.dumps(
                catalog
            ).encode()
            profile = json.loads(
                self.source.files["profiles/application-baseline.json"]
            )
            profile["profile"]["imports"][0]["include-controls"][0]["with-ids"].append(
                "UNBOUND-001"
            )
            self.source.files["profiles/application-baseline.json"] = json.dumps(
                profile
            ).encode()
        if license_controls > 1:
            catalog = json.loads(self.source.files["catalogs/application.json"])
            profile = json.loads(
                self.source.files["profiles/application-baseline.json"]
            )
            bindings = json.loads(self.source.files["checks/application.json"])
            original = next(
                control
                for control in catalog["catalog"]["groups"][0]["controls"]
                if control["id"] == "PY-LIC-001"
            )
            for index in range(2, license_controls + 1):
                control_id = f"PY-LIC-{index:03}"
                control = {**copy.deepcopy(original), "id": control_id}
                control.pop("params", None)
                catalog["catalog"]["groups"][0]["controls"].append(control)
                profile["profile"]["imports"][0]["include-controls"][0][
                    "with-ids"
                ].append(control_id)
                bindings["spec"]["controls"].append(
                    {
                        "id": control_id,
                        "target": {"kind": "python.package"},
                        "requiredEvidence": {"capability": "python.package-license/v1"},
                        "assertions": [
                            {
                                "operator": "spdx-allowlist",
                                "path": "licenseExpression",
                                "allowed": ["MIT"],
                            }
                        ],
                    }
                )
            self.source.files["catalogs/application.json"] = json.dumps(
                catalog
            ).encode()
            self.source.files["profiles/application-baseline.json"] = json.dumps(
                profile
            ).encode()
            self.source.files["checks/application.json"] = json.dumps(bindings).encode()
        app.dependency_overrides[github_source_factory] = lambda: (
            lambda _repo: self.source
        )
        directory = tempfile.TemporaryDirectory(prefix="native-license-test-")
        self.addCleanup(directory.cleanup)
        workspace_path = Path(directory.name) / "workspace.json"
        workspace_path.write_text(
            json.dumps({"organizationId": self.org, "defaultOwnerTeamId": self.team}),
            encoding="utf-8",
        )
        environment = patch.dict(
            os.environ,
            {
                "GITHUB_ORGANIZATION_ID": self.org,
                "SPECBOUND_WORKSPACE_CONFIG": str(workspace_path),
            },
        )
        environment.start()
        self.addCleanup(environment.stop)
        for kind, path, resource_id in (
            ("Catalog", "catalogs/application.json", "application-controls"),
            ("Profile", "profiles/application-baseline.json", "application-baseline"),
            ("Product", "products/audio-visualizer.json", "audio-visualizer"),
        ):
            root = f"/organizations/{self.org}/resources"
            config = {
                "apiVersion": "specbound.example/v1alpha1",
                "kind": "ResourceSource",
                "metadata": {"id": "source", "version": "1.0.0", "name": "Source"},
                "spec": {
                    "resourceType": kind,
                    "provider": "github",
                    "repository": self.source.repository,
                    "ref": "main",
                    "manifestPath": path,
                    "expected": {"id": resource_id, "version": "1.0.0"},
                },
            }
            if attach_existing and kind == "Product":
                product = json.loads(self.source.files[path])
                root += f"?product_id={self.product}"
                self.assertEqual(
                    self.client.post(root + "&preview=true", json=config).status_code,
                    409,
                )
                product["spec"]["repositories"] = [
                    {"provider": "github", "repository": "example/public"}
                ]
                self.source.files[path] = json.dumps(product).encode()
                self.assertEqual(self.client.post(root, json=config).status_code, 422)
                preview = self.client.post(root + "&preview=true", json=config)
                self.assertEqual(preview.status_code, 200, preview.text)
                candidate = preview.json()
                self.assertEqual(candidate["resolved"]["productId"], self.product)
                headers = {
                    "X-Expected-Commit": candidate["source"]["commit"],
                    "X-Review-Digest": candidate["reviewDigest"],
                }
                self.assertEqual(
                    self.client.post(
                        root,
                        json=config,
                        headers={**headers, "X-Review-Digest": "0" * 64},
                    ).status_code,
                    409,
                )
                response = self.client.post(root, json=config, headers=headers)
            else:
                response = self.client.post(root, json=config)
            self.assertEqual(response.status_code, 201, response.text)
        self.product = response.json()["resolved"]["productId"]
        self.binding = self.client.get(f"/products/{self.product}/repositories").json()[
            0
        ]["id"]
        self.url = (
            f"/products/{self.product}/repositories/{self.binding}/public-license-scans"
        )

    @staticmethod
    def observed_result(expression, *, partial=False):
        return {
            "sourceRevision": "b" * 40,
            "coverage": "partial" if partial else "covered",
            "sourceCoverage": "partial" if partial else "covered",
            "files": ["uv.lock"],
            "unsupportedFiles": ["other/poetry.lock"] if partial else [],
            "packages": [
                {
                    "path": "uv.lock",
                    "name": "sample",
                    "version": "1.0",
                    "source": "pypi",
                    "markers": [],
                    "licenseExpression": expression,
                    "status": "FAIL",
                    "metadata": {
                        "status": "OBSERVED",
                        "artifacts": [
                            {
                                "sourceUrl": "https://files.pythonhosted.org/packages/ab/sample.whl.metadata",
                                "sourceKind": "distribution-metadata",
                                "artifactSha256": "a" * 64,
                                "metadataSha256": "b" * 64,
                                "licenseExpression": expression,
                            }
                        ],
                    },
                }
            ],
        }

    def finish_profile_scan(self, result):
        job = self.client.post(self.url, json={"ref": "main"})
        self.assertEqual(job.status_code, 201, job.text)
        self.assertTrue(
            poll_once(
                get_engine(),
                execute=lambda _repository, _ref: {"status": "ok", "result": result},
                job_id=job.json()["id"],
            )
        )
        stored = self.client.get(self.url).json()[0]
        self.assertIsNotNone(stored["assessmentId"], stored)
        return self.client.get("/assessments/" + stored["assessmentId"]).json()

    def test_adopting_a_manifest_keeps_existing_product_repository_and_report(self):
        before = self.finish_profile_scan(self.observed_result("GPL-3.0-only"))
        product, binding = self.product, self.binding
        self.configure_native_product(attach_existing=True)
        self.assertEqual((self.product, self.binding), (product, binding))
        self.assertEqual(
            len(self.client.get(f"/organizations/{self.org}/products").json()), 1
        )
        self.assertEqual(
            self.client.get(f"/assessments/{before['assessment']['id']}").json(), before
        )
        following = self.client.post(self.url, json={"ref": "main"})
        self.assertEqual(following.status_code, 201, following.text)
        self.assertEqual(following.json()["governanceContext"]["mode"], "profile")
        self.assertTrue(
            poll_once(
                get_engine(),
                execute=lambda *_: {
                    "status": "ok",
                    "result": self.observed_result("MIT"),
                },
                job_id=following.json()["id"],
            )
        )

    def test_native_profile_is_frozen_at_start_and_overrides_the_example_policy(self):
        self.configure_native_product(allowed=["GPL-3.0-only"])
        job = self.client.post(self.url, json={"ref": "main"}).json()
        frozen = copy.deepcopy(job["governanceContext"])
        self.assertEqual(frozen["mode"], "profile")
        self.assertEqual(
            frozen["profile"]["resolved"]["selectedControlIds"],
            ["SEC-API-001", "PY-LIC-001"],
        )
        calls_before = len(self.source.calls)
        self.source.commit = "c" * 40
        profile = json.loads(self.source.files["profiles/application-baseline.json"])
        profile["profile"]["modify"]["set-parameters"][0]["values"] = ["MIT"]
        self.source.files["profiles/application-baseline.json"] = json.dumps(
            profile
        ).encode()
        self.assertTrue(
            poll_once(
                get_engine(),
                execute=lambda _repository, _ref: {
                    "status": "ok",
                    "result": self.observed_result("GPL-3.0-only"),
                },
            )
        )
        stored = self.client.get(self.url).json()[0]
        report = self.client.get("/assessments/" + stored["assessmentId"]).json()
        self.assertEqual(report["assessment"]["governanceContext"], frozen)
        self.assertEqual(
            len(self.source.calls),
            calls_before,
            "Worker must not re-resolve source refs",
        )
        self.assertEqual(report["assessment"]["packSha"], "a" * 40)
        self.assertEqual(report["evaluations"][0]["status"], "PASS", report)
        self.assertEqual(report["findings"], [])
        self.assertEqual(report["evidence"][0]["producerKind"], "public-license-scan")

    def test_selected_unsupported_and_unbound_controls_stay_visible_without_fake_na(
        self,
    ):
        self.configure_native_product(unbound=True)
        report = self.finish_profile_scan(self.observed_result("GPL-3.0-only"))
        controls = {
            item["controlId"]: item for item in report["assessment"]["controls"]
        }
        self.assertEqual(
            (
                controls["SEC-API-001"]["executionStatus"],
                controls["SEC-API-001"]["status"],
            ),
            ("unsupported", "UNKNOWN"),
        )
        self.assertEqual(
            (
                controls["UNBOUND-001"]["executionStatus"],
                controls["UNBOUND-001"]["status"],
            ),
            ("not_evaluated", "UNKNOWN"),
        )
        self.assertEqual(
            (
                controls["PY-LIC-001"]["executionStatus"],
                controls["PY-LIC-001"]["status"],
            ),
            ("evaluated", "FAIL"),
        )
        self.assertEqual(len(report["evaluations"]), 1)
        self.assertEqual(len(report["findings"]), 1)

    def test_native_missing_observations_and_partial_pass_do_not_close_findings(self):
        self.configure_native_product()
        initial = self.finish_profile_scan(self.observed_result("GPL-3.0-only"))
        finding_id = initial["findings"][0]["id"]
        empty = self.finish_profile_scan(
            {
                "sourceRevision": "b" * 40,
                "coverage": "UNKNOWN",
                "sourceCoverage": "UNKNOWN",
                "files": [],
                "unsupportedFiles": ["poetry.lock"],
                "packages": [],
                "reason": "no supported lockfile",
            }
        )
        self.assertEqual(empty["evaluations"], [])
        self.assertEqual(
            {item["status"] for item in empty["assessment"]["controls"]}, {"UNKNOWN"}
        )
        self.assertEqual(len(empty["assessment"]["controls"]), 2)
        self.assertEqual(empty["sourceScan"]["reason"], "no supported lockfile")
        self.assertEqual(empty["sourceScan"]["unsupportedFiles"], ["poetry.lock"])
        partial = self.finish_profile_scan(self.observed_result("MIT", partial=True))
        self.assertEqual(partial["findings"][0]["state"], "open")
        complete = self.finish_profile_scan(self.observed_result("MIT"))
        self.assertEqual(complete["findings"][0]["id"], finding_id)
        self.assertEqual(complete["findings"][0]["state"], "resolved")

    def test_historical_job_does_not_receive_a_current_profile(self):
        job = self.client.post(self.url, json={"ref": "main"}).json()
        with get_engine().begin() as db:
            db.execute(
                update(public_license_scans)
                .where(public_license_scans.c.id == job["id"])
                .values(governance_context=None)
            )
        self.assertTrue(
            poll_once(
                get_engine(),
                execute=lambda _repo, _ref: {
                    "status": "ok",
                    "result": self.observed_result("GPL-3.0-only"),
                },
            )
        )
        stored = self.client.get(self.url).json()[0]
        report = self.client.get("/assessments/" + stored["assessmentId"]).json()
        self.assertIsNone(report["assessment"]["governanceContext"])
        self.assertIsNone(report["assessment"]["controls"])

    def test_control_capacity_preserves_the_assessment_and_explicit_remaining_gaps(
        self,
    ):
        from app.frozen_governance import plan_public_scan

        self.configure_native_product(license_controls=6)
        job = self.client.post(self.url, json={"ref": "main"}).json()
        policy, gaps = plan_public_scan(job["governanceContext"], 200)
        self.assertEqual(len(policy["controls"]) * 200, 1000)
        self.assertEqual(gaps, {"PY-LIC-006": "evaluation-limit"})
        result = self.observed_result("GPL-3.0-only")
        result["packages"] = [
            {**copy.deepcopy(result["packages"][0]), "name": f"sample-{index}"}
            for index in range(3)
        ]
        with patch("app.frozen_governance.MAX_EVALUATIONS", 4):
            self.assertTrue(
                poll_once(
                    get_engine(),
                    execute=lambda *_args: {"status": "ok", "result": result},
                )
            )
        stored = self.client.get(self.url).json()[0]
        self.assertIsNotNone(stored["assessmentId"], stored)
        self.assertNotIn("assessmentError", stored["result"])
        report = self.client.get("/assessments/" + stored["assessmentId"]).json()
        self.assertEqual(len(report["evaluations"]), 3)
        self.assertEqual(len(report["assessment"]["controls"]), 7)
        self.assertEqual(len(report["evidence"]), 3)
        self.assertEqual(len(report["findings"]), 3)
        control = next(
            item
            for item in report["assessment"]["controls"]
            if item["controlId"] == "PY-LIC-002"
        )
        self.assertEqual(
            (control["executionStatus"], control["status"], control["reason"]),
            ("not_evaluated", "UNKNOWN", "evaluation-limit"),
        )

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
        def run_scan(expression, partial=False):
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
                "sourceCoverage": "partial" if partial else "covered",
                "coverage": "partial" if partial else "covered",
                "files": ["uv.lock"],
                "unsupportedFiles": ["other/poetry.lock"] if partial else [],
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

        job, failed = run_scan("GPL-3.0-only", partial=True)
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
            self.assertEqual(snapshot["counts"]["FAIL"], 1)
        _, partial_pass = run_scan("MIT", partial=True)
        with get_engine().connect() as db:
            self.assertEqual(
                db.execute(
                    select(findings.c.status).where(findings.c.id == finding["id"])
                ).scalar_one(),
                "open",
            )
            counts = db.execute(
                select(assessment_snapshots.c.counts).where(
                    assessment_snapshots.c.id == partial_pass["assessmentId"]
                )
            ).scalar_one()
            self.assertEqual(counts["PASS"], 1)
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

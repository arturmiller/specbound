"""Full product-scoped requirements projections, including fourteen observations."""

import copy
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from app.database import get_engine
from app.identity import get_current_principal
from app.main import app
from app.snapshots import create_snapshot
from app.tables import public_license_scans
from sqlalchemy import update

from tests import test_public_license_scans as scans
from tests import test_rule_evaluation as rules


class ProductRequirementsTest(unittest.TestCase):
    setUp = scans.PublicLicenseScansTest.setUp
    tearDown = scans.PublicLicenseScansTest.tearDown
    configure_native_product = scans.PublicLicenseScansTest.configure_native_product
    observed_result = staticmethod(scans.PublicLicenseScansTest.observed_result)
    finish_profile_scan = scans.PublicLicenseScansTest.finish_profile_scan

    def test_all_fourteen_evaluations_and_exact_selected_evidence_survive_history(self):
        self.configure_native_product()
        result = self.observed_result("GPL-3.0-only")
        result["packages"] = [
            {**copy.deepcopy(result["packages"][0]), "name": f"package-{index + 1:02}"}
            for index in range(14)
        ]
        first = self.finish_profile_scan(result)
        snapshot_id = first["assessment"]["id"]
        response = self.client.get(
            f"/products/{self.product}/requirements", params={"assessment": snapshot_id}
        )
        self.assertEqual(response.status_code, 200, response.text)
        value = response.json()
        self.assertEqual(len(value["controls"]), 2)
        licensing = next(
            control for control in value["controls"] if control["id"] == "PY-LIC-001"
        )
        self.assertEqual(len(licensing["evaluations"]), 14)
        self.assertEqual(len(value["evidence"]), 14)
        self.assertEqual(
            {item["id"] for item in value["evidence"]},
            {
                evidence_id
                for evaluation in licensing["evaluations"]
                for evidence_id in evaluation["evidenceIds"]
            },
        )
        self.assertTrue(
            all(
                item["producerKind"] == "public-license-scan"
                for item in value["evidence"]
            )
        )
        self.assertTrue(
            all(item["freshness"] == "current" for item in value["evidence"])
        )
        later = self.finish_profile_scan(self.observed_result("MIT"))
        latest = self.client.get(f"/products/{self.product}/requirements").json()
        self.assertEqual(latest["selectionId"], later["assessment"]["id"])
        with patch(
            "app.product_requirements.get_product_governance",
            side_effect=AssertionError(
                "Historical selection must not load today's profile"
            ),
        ):
            historical = self.client.get(
                f"/products/{self.product}/requirements",
                params={"assessment": snapshot_id},
            ).json()
        self.assertEqual(historical["controls"], value["controls"])
        self.assertEqual(historical["evidence"], value["evidence"])
        with patch("app.product_requirements.datetime") as clock:
            clock.now.return_value = datetime.now(timezone.utc) + timedelta(days=2)
            expired = self.client.get(
                f"/products/{self.product}/requirements",
                params={"assessment": snapshot_id},
            ).json()
        self.assertTrue(
            all(item["freshness"] == "expired" for item in expired["evidence"])
        )

    def test_product_team_and_selection_fences_and_pending_run(self):
        self.configure_native_product()
        current = self.client.get(
            f"/products/{self.product}/requirements", params={"assessment": "current"}
        ).json()
        self.assertEqual(current["provenanceStatus"], "profile")
        self.assertEqual(len(current["controls"]), 2)
        job = self.client.post(self.url, json={"ref": "main"}).json()
        pending = self.client.get(
            f"/products/{self.product}/requirements",
            params={"assessment": "scan:" + job["id"]},
        ).json()
        self.assertEqual(pending["run"]["status"], "pending")
        self.assertEqual(len(pending["controls"]), 2)
        self.assertTrue(
            all(item["result"]["status"] == "UNKNOWN" for item in pending["controls"])
        )
        with get_engine().begin() as db:
            db.execute(
                update(public_license_scans)
                .where(public_license_scans.c.id == job["id"])
                .values(
                    status="failed",
                    error_code="source-not-found",
                    finished_at=datetime.now(timezone.utc),
                )
            )
        other = self.client.post(
            f"/organizations/{self.org}/products",
            json={"name": "Another", "ownerTeamId": self.team},
        ).json()["id"]
        self.assertEqual(
            self.client.get(
                f"/products/{other}/requirements",
                params={"assessment": "scan:" + job["id"]},
            ).status_code,
            404,
        )
        self.assertEqual(
            self.client.get(
                f"/products/{self.product}/requirements",
                params={"assessment": "missing"},
            ).status_code,
            404,
        )
        self.client.post(
            f"/teams/{self.team}/members",
            json={"principalId": self.viewer, "role": "viewer"},
        )
        app.dependency_overrides[get_current_principal] = lambda: self.viewer
        self.assertEqual(
            self.client.get(f"/products/{self.product}/requirements").status_code, 200
        )
        app.dependency_overrides[get_current_principal] = lambda: self.other
        self.assertEqual(
            self.client.get(f"/products/{self.product}/requirements").status_code, 403
        )

    def test_historical_ambiguous_evidence_keeps_its_recorded_reason(self):
        fixture = rules.RuleEvaluationTest(methodName="runTest")
        fixture.setUp()
        self.addCleanup(fixture.tearDown)
        fixture.save_evidence()
        fixture.save_evidence()
        evaluation = fixture.evaluate()
        app.dependency_overrides[get_current_principal] = lambda: "owner"
        self.assertEqual(evaluation["reason"], "Aktuelle Nachweise sind mehrdeutig")
        with get_engine().begin() as db:
            snapshot = create_snapshot(
                db,
                fixture.org,
                fixture.product,
                context="repository",
                binding_id=fixture.binding,
                pull_request_number=None,
                environment=fixture.scope["environment"],
                git_sha=rules.COMMIT,
                pack_sha="a" * 40,
                evaluation_ids=[evaluation["id"]],
                now=rules.NOW,
            )
        response = self.client.get(
            f"/products/{fixture.product}/requirements",
            params={"assessment": snapshot["id"]},
        )
        self.assertEqual(response.status_code, 200, response.text)
        value = response.json()
        self.assertEqual(value["provenanceStatus"], "historical-unknown")
        self.assertIsNone(value["context"])
        self.assertEqual(
            value["controls"][0]["evaluations"][0]["reason"],
            "Aktuelle Nachweise sind mehrdeutig",
        )
        self.assertEqual(value["evidence"], [])

    def test_partial_and_observationless_scan_causes_remain_in_the_projection(self):
        self.configure_native_product()
        self.finish_profile_scan(self.observed_result("GPL-3.0-only"))
        partial = self.finish_profile_scan(self.observed_result("MIT", partial=True))
        response = self.client.get(
            f"/products/{self.product}/requirements",
            params={"assessment": partial["assessment"]["id"]},
        ).json()
        control = next(
            item for item in response["controls"] if item["id"] == "PY-LIC-001"
        )
        self.assertEqual(control["evaluations"][0]["status"], "PASS")
        self.assertEqual(control["evaluations"][0]["coverage"]["status"], "partial")
        self.assertEqual(
            response["sourceScan"]["unsupportedFiles"], ["other/poetry.lock"]
        )
        self.assertEqual(response["findings"][0]["state"], "open")
        empty = self.finish_profile_scan(
            {
                "sourceRevision": "b" * 40,
                "sourceCoverage": "UNKNOWN",
                "coverage": "UNKNOWN",
                "packages": [],
                "files": [],
                "unsupportedFiles": ["poetry.lock"],
                "reason": "no supported lockfile",
            }
        )
        value = self.client.get(
            f"/products/{self.product}/requirements",
            params={"assessment": empty["assessment"]["id"]},
        ).json()
        self.assertTrue(all(not item["evaluations"] for item in value["controls"]))
        self.assertEqual(value["sourceScan"]["reason"], "no supported lockfile")
        self.assertEqual(value["sourceScan"]["coverage"], "UNKNOWN")

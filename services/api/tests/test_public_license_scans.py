"""Portal scan requests and worker leases use real scoped PostgreSQL data."""

import copy
import hashlib
import hmac
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
from app.git_source import GitSnapshot
from app.identity import get_current_principal
from app.main import app
from app.pack_catalog import github_source_factory
from app.pr_check import publish_check_once
from app.product_governance import load_product
from app.tables import (
    assessment_jobs,
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
from pr_license_worker import prepare_pr_license_scan  # noqa: E402
from public_license_worker import claim, finish, poll_once  # noqa: E402
from queue_worker import poll_once as poll_pr_once  # noqa: E402


class Checks:
    app_id = "456"

    def __init__(self, repository, head):
        self.repository = repository
        self.head = head
        self.published = []

    def _token(self, *, permissions):
        return "fixture-token"

    def _request(self, method, path, token, **kwargs):
        if method == "GET" and path.endswith("/pulls/17"):
            return {"head": {"sha": self.head}}
        if method == "GET" and path.endswith("/check-runs"):
            return {
                "check_runs": [
                    {
                        "name": "Specbound assessment",
                        "external_id": self.published[0]["external_id"],
                        "app": {"id": self.app_id},
                        "id": 1,
                    }
                ]
                if self.published
                else []
            }
        if method == "POST" and path.endswith("/check-runs"):
            self.published.append(kwargs["json"])
            return {"id": 1}
        if method == "PATCH" and path.endswith("/check-runs/1"):
            self.published.append(kwargs["json"])
            return {"id": 1}
        raise AssertionError((method, path))

    def close(self):
        pass


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
        self,
        *,
        allowed=None,
        unbound=False,
        license_controls=1,
        attach_existing=False,
        repository="example/public",
        license_only=False,
        license_use=None,
        library_use=False,
        governance_repository="example/governance",
    ):
        self.source = ResourceFixtureSource(governance_repository)
        if library_use:
            self.add_library_use_enhancement()
        if license_use:
            product = json.loads(self.source.files["products/audio-visualizer.json"])
            product["spec"]["licenseUse"] = license_use
            self.source.files["products/audio-visualizer.json"] = json.dumps(
                product
            ).encode()
            bindings = json.loads(self.source.files["checks/application.json"])
            for control in bindings["spec"]["controls"]:
                if control["id"] == "PY-LIC-001":
                    control["assertions"][0]["allowApprovedUse"] = True
            self.source.files["checks/application.json"] = json.dumps(bindings).encode()
        if license_only:
            profile = json.loads(
                self.source.files["profiles/application-baseline.json"]
            )
            profile["profile"]["imports"][0]["include-controls"][0]["with-ids"] = [
                "PY-LIC-001",
                *(["PY-LIC-001.1"] if library_use else []),
            ]
            self.source.files["profiles/application-baseline.json"] = json.dumps(
                profile
            ).encode()
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
                    {"provider": "github", "repository": repository}
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

    def add_library_use_enhancement(self):
        """The organization permits LGPL for declared, unmodified library use."""
        catalog = json.loads(self.source.files["catalogs/application.json"])
        base = next(
            control
            for control in catalog["catalog"]["groups"][0]["controls"]
            if control["id"] == "PY-LIC-001"
        )
        base["controls"] = [
            {
                "id": "PY-LIC-001.1",
                "title": "Weak copyleft for unmodified library use",
                "params": [{"id": "license-library-allowlist"}],
                "parts": [{"name": "statement", "prose": "Unmodified libraries."}],
            }
        ]
        self.source.files["catalogs/application.json"] = json.dumps(catalog).encode()
        profile = json.loads(self.source.files["profiles/application-baseline.json"])
        profile["profile"]["imports"][0]["include-controls"][0]["with-ids"].append(
            "PY-LIC-001.1"
        )
        profile["profile"]["modify"]["set-parameters"].append(
            {"param-id": "license-library-allowlist", "values": ["LGPL-3.0-only"]}
        )
        self.source.files["profiles/application-baseline.json"] = json.dumps(
            profile
        ).encode()
        bindings = json.loads(self.source.files["checks/application.json"])
        for control in bindings["spec"]["controls"]:
            if control["id"] == "PY-LIC-001":
                control["assertions"][0]["libraryUse"] = {
                    "control": "PY-LIC-001.1",
                    "allowedParameter": "license-library-allowlist",
                }
        bindings["spec"]["controls"].append(
            {
                "id": "PY-LIC-001.1",
                "target": {"kind": "python.package"},
                "requiredEvidence": {"capability": "python.package-license/v1"},
                "assertions": [
                    {
                        "operator": "spdx-library-use",
                        "path": "licenseExpression",
                        "control": "PY-LIC-001.1",
                        "allowedParameter": "license-library-allowlist",
                        "baseAllowedParameter": "license-allowlist",
                    }
                ],
            }
        )
        self.source.files["checks/application.json"] = json.dumps(bindings).encode()

    def send_pull_request(self, repository, head, *, action="synchronize"):
        body = json.dumps(
            {
                "action": action,
                "installation": {"id": 12345},
                "number": 17,
                "repository": {"id": 123, "full_name": repository},
                "pull_request": {
                    "id": 100,
                    "number": 17,
                    "head": {"sha": head},
                    "base": {"repo": {"id": 123}},
                },
            }
        ).encode()
        mac = hmac.new(b"test-only", body, hashlib.sha256).hexdigest()
        with patch.dict(
            os.environ,
            {
                "GITHUB_WEBHOOK_SECRET": "test-only",
                "GITHUB_INSTALLATION_ID": "12345",
                "GITHUB_ORGANIZATION_ID": self.org,
            },
        ):
            response = self.client.post(
                "/webhooks/github",
                content=body,
                headers={
                    "X-Hub-Signature-256": "sha256=" + mac,
                    "X-GitHub-Delivery": str(uuid4()),
                    "X-GitHub-Event": "pull_request",
                },
            )
        self.assertEqual(response.status_code, 202, response.text)

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
                    "artifactHashes": ["a" * 64],
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

    def test_signed_pr_scan_publishes_commit_check_and_portal_evidence(self):
        repository = f"example/{self.binding}"
        response = self.client.patch(
            f"/products/{self.product}/repositories/{self.binding}",
            json={"provider": "github", "repository": repository},
        )
        self.assertEqual(response.status_code, 200, response.text)
        self.configure_native_product(
            allowed=["MIT"],
            attach_existing=True,
            repository=repository,
            license_only=True,
            license_use="customer-distribution",
        )

        engine = get_engine()
        for index, (expression, scenario, verdict) in enumerate(
            [
                ("LGPL-3.0-only", "complete", "failure"),
                ("MIT", "complete", "success"),
                ("MIT", "partial", "failure"),
                ("MIT", "no-lockfile", "failure"),
                ("MIT", "wrong-commit", "failure"),
                ("MIT", "timeout", "failure"),
            ]
        ):
            with self.subTest(scenario=scenario, expression=expression):
                head = f"{index + 1:040x}"
                body = json.dumps(
                    {
                        "action": "opened" if index == 0 else "synchronize",
                        "installation": {"id": 12345},
                        "number": 17,
                        "repository": {"id": 123, "full_name": repository},
                        "pull_request": {
                            "id": 100,
                            "number": 17,
                            "head": {"sha": head},
                            "base": {"repo": {"id": 123}},
                        },
                    }
                ).encode()
                mac = hmac.new(b"test-only", body, hashlib.sha256).hexdigest()
                with patch.dict(
                    os.environ,
                    {
                        "GITHUB_WEBHOOK_SECRET": "test-only",
                        "GITHUB_INSTALLATION_ID": "12345",
                        "GITHUB_ORGANIZATION_ID": self.org,
                    },
                ):
                    response = self.client.post(
                        "/webhooks/github",
                        content=body,
                        headers={
                            "X-Hub-Signature-256": "sha256=" + mac,
                            "X-GitHub-Delivery": str(uuid4()),
                            "X-GitHub-Event": "pull_request",
                        },
                    )
                self.assertEqual(response.status_code, 202, response.text)

                def execute(source, ref):
                    self.assertEqual((source, ref), (repository, head))
                    if scenario == "timeout":
                        return {"status": "error", "errorCode": "timeout"}
                    result = self.observed_result(
                        expression, partial=scenario == "partial"
                    )
                    if expression == "LGPL-3.0-only":
                        result["packages"][0].update(
                            name="psycopg-binary", version="3.3.3"
                        )
                    result["sourceRevision"] = (
                        "f" * 40 if scenario == "wrong-commit" else head
                    )
                    if scenario == "no-lockfile":
                        result.update(
                            sourceCoverage="UNKNOWN",
                            coverage="UNKNOWN",
                            files=[],
                            packages=[],
                        )
                    return {"status": "ok", "result": result}

                self.assertTrue(
                    poll_pr_once(
                        engine,
                        self.org,
                        lambda lease: prepare_pr_license_scan(
                            engine, lease, execute=execute
                        ),
                    )
                )
                with engine.connect() as db:
                    job = (
                        db.execute(
                            select(assessment_jobs).where(
                                assessment_jobs.c.organization_id == self.org,
                                assessment_jobs.c.head_sha == head,
                            )
                        )
                        .mappings()
                        .one()
                    )
                self.assertEqual(job["status"], "completed")
                snapshot = job["result_snapshot_id"]
                response = self.client.get(f"/assessments/{snapshot}")
                self.assertEqual(response.status_code, 200, response.text)
                result = response.json()
                self.assertEqual(result["assessment"]["pullRequestNumber"], 17)
                self.assertEqual(result["assessment"]["gitSha"], head)
                self.assertEqual(
                    result["pullRequestUrl"], f"https://github.com/{repository}/pull/17"
                )
                if scenario in {"wrong-commit", "timeout", "no-lockfile"}:
                    self.assertEqual(result["evidence"], [])
                    self.assertEqual(result["sourceScan"]["files"], [])
                    if scenario != "no-lockfile":
                        self.assertIsNone(result["sourceScan"]["sourceRevision"])
                else:
                    self.assertEqual(result["sourceScan"]["sourceRevision"], head)
                    self.assertEqual(result["sourceScan"]["files"], ["uv.lock"])
                    self.assertEqual(len(result["evidence"]), 1)
                if expression == "LGPL-3.0-only":
                    self.assertEqual(result["findings"][0]["outcome"], "FAIL")

                requirements = self.client.get(
                    f"/products/{self.product}/requirements",
                    params={"assessment": snapshot},
                ).json()
                option = next(
                    option
                    for option in requirements["options"]
                    if option["id"] == snapshot
                )
                self.assertEqual(
                    (option["context"], option["pullRequestNumber"]),
                    ("pull_request", 17),
                )
                github = Checks(repository, head)
                self.assertTrue(
                    publish_check_once(
                        engine,
                        self.org,
                        lambda _: github,
                        "https://portal.example",
                        clock=lambda: datetime.now(timezone.utc),
                    )
                )
                self.assertEqual(len(github.published), 1)
                self.assertEqual(github.published[0]["head_sha"], head)
                self.assertEqual(github.published[0]["conclusion"], verdict)
                self.assertEqual(
                    github.published[0]["details_url"],
                    f"https://portal.example/assessments/{snapshot}",
                )
                self.assertIn(
                    f"[Specbound-Ergebnis öffnen](<https://portal.example/assessments/{snapshot}>)",
                    github.published[0]["output"]["summary"],
                )
                if expression == "LGPL-3.0-only":
                    proof = "https://proof.example.test/protected/psycopg-release"
                    endpoint = f"/products/{self.product}/license-approvals"
                    grant = {
                        "assessmentId": snapshot,
                        "evaluationId": result["evaluations"][0]["id"],
                        "kind": "conditions-met",
                        "reason": "Reviewed distribution of LGPL library.",
                        "conditions": "Include notices and permit replacement.",
                        "proofUrl": proof,
                    }
                    self.client.post(
                        f"/teams/{self.team}/members",
                        json={
                            "principalId": self.viewer,
                            "role": "maintainer",
                        },
                    )
                    app.dependency_overrides[get_current_principal] = lambda: (
                        self.viewer
                    )
                    self.assertEqual(
                        self.client.post(endpoint, json=grant).status_code, 403
                    )
                    app.dependency_overrides[get_current_principal] = lambda: self.owner
                    approved = self.client.post(endpoint, json=grant)
                    self.assertEqual(approved.status_code, 201, approved.text)
                    approval_id = approved.json()["id"]
                    self.assertEqual(
                        self.client.get(endpoint + "/" + approval_id).json()[
                            "proofUrl"
                        ],
                        proof,
                    )
                    with patch.dict(os.environ, {"PR_LICENSE_SCAN_ENABLED": "true"}):
                        recheck = self.client.post(
                            f"/assessments/{snapshot}/license-recheck"
                        )
                        self.assertEqual(recheck.status_code, 202, recheck.text)
                        self.assertEqual(
                            self.client.post(
                                f"/assessments/{snapshot}/license-recheck"
                            ).status_code,
                            409,
                        )
                    self.assertTrue(
                        poll_pr_once(
                            engine,
                            self.org,
                            lambda lease: prepare_pr_license_scan(
                                engine, lease, execute=execute
                            ),
                        )
                    )
                    self.assertTrue(
                        publish_check_once(
                            engine,
                            self.org,
                            lambda _: github,
                            "https://portal.example",
                            clock=lambda: datetime.now(timezone.utc),
                        )
                    )
                    self.assertEqual(github.published[-1]["conclusion"], "success")
                    with engine.begin() as db:
                        updated = (
                            db.execute(
                                select(assessment_jobs).where(
                                    assessment_jobs.c.id == job["id"]
                                )
                            )
                            .mappings()
                            .one()
                        )
                    latest = self.client.get(
                        "/assessments/" + updated["result_snapshot_id"]
                    )
                    self.assertNotIn(proof, latest.text)
                    value = latest.json()["evidence"][0]["value"]
                    self.assertEqual(value["licenseExpression"], "LGPL-3.0-only")
                    self.assertEqual(value["licenseApproval"]["id"], approval_id)
                    self.assertEqual(
                        self.client.get(f"/assessments/{snapshot}").json()[
                            "assessment"
                        ]["counts"]["FAIL"],
                        1,
                    )
                    self.assertEqual(
                        self.client.get(f"/assessments/{snapshot}").json()[
                            "pullRequestUrl"
                        ],
                        f"https://github.com/{repository}/pull/17",
                    )
                    self.assertTrue(
                        self.client.post(
                            endpoint + "/" + approval_id + "/revoke"
                        ).json()["revoked"]
                    )
                    self.assertTrue(
                        publish_check_once(
                            engine,
                            self.org,
                            lambda _: github,
                            "https://portal.example",
                            clock=lambda: (
                                datetime.now(timezone.utc) + timedelta(minutes=6)
                            ),
                        )
                    )
                    self.assertEqual(github.published[-1]["conclusion"], "failure")

    def test_library_use_declared_at_the_pull_request_commit_permits_lgpl(self):
        repository = f"example/{self.binding}"
        response = self.client.patch(
            f"/products/{self.product}/repositories/{self.binding}",
            json={"provider": "github", "repository": repository},
        )
        self.assertEqual(response.status_code, 200, response.text)
        # The product manifest lives in the pull request's own repository; the
        # registered revision does not declare library use yet.
        self.configure_native_product(
            allowed=["MIT"],
            attach_existing=True,
            repository=repository,
            license_only=True,
            license_use="customer-distribution",
            library_use=True,
            governance_repository=repository,
        )
        registered = json.loads(self.source.files["products/audio-visualizer.json"])
        engine = get_engine()

        def head_manifest(declared=True, paths=None, profile_version=None):
            document = copy.deepcopy(registered)
            if declared:
                document["spec"]["implementedRequirements"] = [
                    {
                        "controlId": "PY-LIC-001.1",
                        "description": "Installed unmodified from PyPI and imported.",
                    }
                ]
            if paths:
                document["spec"]["repositories"][0]["paths"] = paths
            if profile_version:
                document["spec"]["profile"]["version"] = profile_version
            return document

        def lgpl(path="uv.lock", *, hashes=("a" * 64,)):
            result = self.observed_result("LGPL-3.0-only")
            package = result["packages"][0]
            package.update(
                path=path,
                name="psycopg-c",
                version="3.3.3",
                artifactHashes=list(hashes),
            )
            result["files"] = [path]
            return result

        def other_lockfile(result):
            extra = copy.deepcopy(result["packages"][0])
            extra.update(path="tools/uv.lock", name="gpl-tool")
            extra["metadata"]["artifacts"][0]["licenseExpression"] = "GPL-3.0-only"
            result["packages"].append(extra)
            result["files"] = sorted([*result["files"], "tools/uv.lock"])
            return result

        scenarios = [
            ("declared", head_manifest(), lgpl(), "success"),
            ("undeclared", head_manifest(declared=False), lgpl(), "failure"),
            ("modified", head_manifest(), lgpl(hashes=("c" * 64,)), "failure"),
            (
                "other-profile",
                head_manifest(profile_version="9.9.9"),
                lgpl(),
                "failure",
            ),
            ("not-needed", head_manifest(), self.observed_result("MIT"), "success"),
            (
                "product-paths",
                head_manifest(paths=["services/api"]),
                other_lockfile(lgpl("services/api/uv.lock")),
                "success",
            ),
        ]
        for index, (scenario, manifest, scan, verdict) in enumerate(scenarios):
            with self.subTest(scenario=scenario):
                head = f"{index + 101:040x}"
                self.send_pull_request(
                    repository, head, action="opened" if index == 0 else "synchronize"
                )
                scan = {**copy.deepcopy(scan), "sourceRevision": head}
                manifest_reads = []

                def read_product(source, commit, path, manifest=manifest):
                    manifest_reads.append((source, commit, path))
                    files = {path: json.dumps(manifest).encode()}
                    return load_product(GitSnapshot(commit, files), path)

                self.assertTrue(
                    poll_pr_once(
                        engine,
                        self.org,
                        lambda lease, scan=scan: prepare_pr_license_scan(
                            engine,
                            lease,
                            execute=lambda _repository, _ref: {
                                "status": "ok",
                                "result": scan,
                            },
                            read_product=read_product,
                        ),
                    )
                )
                self.assertEqual(
                    manifest_reads,
                    [(repository, head, "products/audio-visualizer.json")],
                )
                with engine.connect() as db:
                    snapshot = db.execute(
                        select(assessment_jobs.c.result_snapshot_id).where(
                            assessment_jobs.c.organization_id == self.org,
                            assessment_jobs.c.head_sha == head,
                        )
                    ).scalar_one()
                result = self.client.get(f"/assessments/{snapshot}").json()
                github = Checks(repository, head)
                self.assertTrue(
                    publish_check_once(
                        engine,
                        self.org,
                        lambda _: github,
                        "https://portal.example",
                        clock=lambda: datetime.now(timezone.utc),
                    )
                )
                self.assertEqual(github.published[-1]["conclusion"], verdict, result)
                reasons = {
                    (item["control"]["id"], item["status"]): item["reason"]
                    for item in result["evaluations"]
                }
                if scenario in ("declared", "product-paths"):
                    basis = reasons[("PY-LIC-001", "PASS")]
                    self.assertIn("PY-LIC-001.1", basis)
                    self.assertIn(head[:12], basis)
                    self.assertIn("audio-visualizer", basis)
                    self.assertIn(("PY-LIC-001.1", "PASS"), reasons)
                elif verdict == "failure":
                    self.assertIn(("PY-LIC-001", "FAIL"), reasons)
                if scenario == "not-needed":
                    self.assertIn(("PY-LIC-001.1", "NOT_APPLICABLE"), reasons)
                if scenario == "product-paths":
                    self.assertEqual(
                        result["sourceScan"]["files"], ["services/api/uv.lock"]
                    )
                    self.assertEqual(
                        result["sourceScan"]["outsideProductPaths"], ["tools/uv.lock"]
                    )
                    self.assertEqual(len(result["evidence"]), 1)

    def test_contract_for_internal_use_does_not_grant_saas_or_replaced_artifacts(self):
        self.configure_native_product(license_only=True, license_use="internal")
        package_result = self.observed_result(None)
        package_result["packages"][0].update(
            source="unsupported:registry",
            status="UNKNOWN",
            metadata={"status": "UNKNOWN"},
        )
        first = self.finish_profile_scan(package_result)
        self.assertEqual(first["assessment"]["counts"]["FAIL"], 1)
        self.assertEqual(first["findings"][0]["outcome"], "FAIL")
        endpoint = f"/products/{self.product}/license-approvals"
        grant = self.client.post(
            endpoint,
            json={
                "assessmentId": first["assessment"]["id"],
                "evaluationId": first["evaluations"][0]["id"],
                "kind": "license-rights",
                "reason": "Vendor contract grants internal use.",
                "conditions": "Internal use by this entity only.",
                "proofUrl": "https://proof.example.test/protected/contract",
            },
        )
        self.assertEqual(grant.status_code, 201, grant.text)
        self.assertEqual(
            self.finish_profile_scan(package_result)["assessment"]["counts"]["PASS"], 1
        )
        changed = copy.deepcopy(package_result)
        changed["packages"][0]["artifactHashes"] = ["c" * 64]
        self.assertEqual(
            self.finish_profile_scan(changed)["assessment"]["counts"]["FAIL"], 1
        )

        # Adopt the same control and repository under a new use; only the
        # manifest's current scope changes, not the artifact or policy rule.
        governance = self.client.get(f"/products/{self.product}/governance").json()
        revision_id = governance["product"]["id"]
        path = "products/audio-visualizer.json"
        document = json.loads(self.source.files[path])
        document["spec"]["licenseUse"] = "saas"
        document["metadata"]["version"] = "1.1.0"
        self.source.files[path] = json.dumps(document).encode()
        self.source.commit = "c" * 40
        check_url = f"/organizations/{self.org}/resources/{revision_id}"
        check = self.client.post(check_url + "/check", json={})
        self.assertEqual(check.status_code, 200, check.text)
        candidate = check.json()["candidate"]
        adoption = self.client.post(
            check_url + "/adopt",
            json={
                "commit": candidate["source"]["commit"],
                "reviewDigest": check.json()["reviewDigest"],
            },
        )
        self.assertEqual(adoption.status_code, 201, adoption.text)
        current = self.finish_profile_scan(package_result)
        self.assertEqual(current["licenseUse"], "saas")
        self.assertEqual(current["assessment"]["counts"]["FAIL"], 1)

    def test_unresolved_source_blocks_a_package_with_an_allowed_wheel(self):
        self.configure_native_product(
            allowed=["MPL-2.0"], license_only=True, license_use="customer-distribution"
        )
        scan = self.observed_result("MPL-2.0")
        package = scan["packages"][0]
        package.update(
            name="certifi",
            version="2026.11.20",
            licenseExpression=None,
            artifactHashes=["a" * 64, "c" * 64],
        )
        wheel = {
            **package["metadata"]["artifacts"][0],
            "filename": "certifi.whl",
            "status": "OBSERVED",
        }
        package["metadata"] = {
            "status": "UNKNOWN",
            "reason": "dynamic license declaration",
            "artifacts": [
                wheel,
                {
                    "artifactSha256": "c" * 64,
                    "filename": "certifi.tar.gz",
                    "status": "UNKNOWN",
                    "reason": "dynamic license declaration",
                },
            ],
        }
        report = self.finish_profile_scan(scan)
        snapshot = report["assessment"]
        evaluation = report["evaluations"][0]
        self.assertEqual(snapshot["counts"]["FAIL"], 1)
        self.assertEqual(snapshot["counts"]["UNKNOWN"], 0)
        self.assertIn("Paketdatei", evaluation["reason"])
        self.assertEqual(report["findings"][0]["outcome"], "FAIL")
        evidence = report["evidence"][0]["value"]
        self.assertEqual(evidence["licenseCoverage"], "incomplete")
        self.assertEqual(evidence["artifacts"][0]["licenseExpression"], "MPL-2.0")
        self.assertEqual(evidence["artifacts"][1]["status"], "UNKNOWN")
        refused = self.client.post(
            f"/products/{self.product}/license-approvals",
            json={
                "assessmentId": snapshot["id"],
                "evaluationId": evaluation["id"],
                "kind": "conditions-met",
                "reason": "Wheel checked.",
                "conditions": "Publish notice.",
                "proofUrl": "https://proof.example.test/wheel",
            },
        )
        self.assertEqual(refused.status_code, 422, refused.text)

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
            evidence = db.execute(
                select(evidence_records.c.value).where(
                    evidence_records.c.producer_scan_id == unknown_job["id"]
                )
            ).scalar_one()
            self.assertEqual(evidence["licenseCoverage"], "incomplete")
            self.assertIsNone(evidence["licenseExpression"])
        self.assertEqual(
            self.client.get(f"/assessments/{unknown['assessmentId']}").json()[
                "assessment"
            ]["counts"]["FAIL"],
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

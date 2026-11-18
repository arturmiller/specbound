"""Test-only server: an in-process identity override, never enabled by the application."""

import json
import os
import tempfile
from pathlib import Path

import uvicorn
import yaml
from app.database import get_engine
from app.git_source import GitSnapshot
from app.github_repositories import github_metadata_source_factory
from app.identity import get_current_principal
from app.main import app
from app.pack_catalog import github_source_factory
from sqlalchemy import text

FIXTURE_ORGANIZATION = "123e4567-e89b-12d3-a456-426614174000"
FIXTURE_OWNER_TEAM = "123e4567-e89b-12d3-a456-426614174001"
WORKSPACE_DIRECTORY = tempfile.TemporaryDirectory(prefix="specbound-e2e-workspace-")
RESOURCE_REVISION_STAGE = "initial"


@app.post("/__e2e/resource-revision")
def resource_revision_fixture(stage: str):
    global RESOURCE_REVISION_STAGE
    if stage not in ("initial", "updated", "invalid"):
        raise ValueError("Unknown fixture revision")
    RESOURCE_REVISION_STAGE = stage
    return {"stage": stage}


@app.post("/__e2e/process-public-license-scan")
def process_public_license_scan_fixture(
    package_count: int = 1,
    partial: bool = False,
    no_observations: bool = False,
    license_expression: str = "GPL-3.0-only",
    scan_id: str | None = None,
):
    """Run the real queue processor with a deterministic source in test only."""
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "worker"))
    from public_license_worker import poll_once

    def fixture(repository, ref):
        response = {
            "status": "ok",
            "result": {
                "requestedRef": ref,
                "sourceRevision": "a" * 40,
                "coverage": "covered",
                "sourceCoverage": "covered",
                "reason": "Fixture lockfile; no installation is implied.",
                "files": ["uv.lock"],
                "unsupportedFiles": [],
                "packages": [
                    {
                        "path": "uv.lock",
                        "name": "sample-gpl",
                        "version": "1.0",
                        "source": "pypi",
                        "markers": [],
                        "licenseExpression": "GPL-3.0-only",
                        "status": "FAIL",
                        "metadata": {
                            "status": "OBSERVED",
                            "artifacts": [
                                {
                                    "sourceUrl": "https://files.pythonhosted.org/packages/ab/sample.whl.metadata",
                                    "sourceKind": "distribution-metadata",
                                    "artifactSha256": "a" * 64,
                                    "metadataSha256": "b" * 64,
                                    "licenseExpression": "GPL-3.0-only",
                                }
                            ],
                        },
                    },
                ],
            },
        }

        if not 1 <= package_count <= 200:
            raise ValueError("Invalid fixture package count")
        if package_count > 1:
            import copy

            package = response["result"]["packages"][0]
            response["result"]["packages"] = [
                {**copy.deepcopy(package), "name": f"package-{index + 1:02}"}
                for index in range(package_count)
            ]
        if license_expression not in ("GPL-3.0-only", "MIT"):
            raise ValueError("Invalid fixture expression")
        for package in response["result"]["packages"]:
            package["licenseExpression"] = license_expression
            package["status"] = "PASS" if license_expression == "MIT" else "FAIL"
            for artifact in package["metadata"]["artifacts"]:
                artifact["licenseExpression"] = license_expression
        if partial:
            response["result"].update(
                coverage="partial",
                sourceCoverage="partial",
                unsupportedFiles=["other/poetry.lock"],
            )
        if no_observations:
            response["result"].update(
                coverage="UNKNOWN",
                sourceCoverage="UNKNOWN",
                packages=[],
                files=[],
                unsupportedFiles=["poetry.lock"],
                reason="no supported lockfile",
            )
        return response

    return {"processed": poll_once(get_engine(), execute=fixture, job_id=scan_id)}


@app.post("/__e2e/assessment")
def create_assessment_fixture(
    failing: bool = False, missing_provider: bool = False, workspace: bool = False
):
    """Seed a complete report only in this test-only server."""
    import sys

    from app.findings import apply_snapshot
    from app.snapshots import create_snapshot
    from app.tables import organizations, teams
    from sqlalchemy import update

    sys.path.insert(0, str(Path(__file__).parent))
    import test_rule_evaluation as fixtures

    fixture = fixtures.RuleEvaluationTest(methodName="runTest")
    fixture.setUp()
    if workspace:
        with get_engine().begin() as db:
            db.execute(
                update(teams)
                .where(teams.c.id == fixture.team)
                .values(organization_id=FIXTURE_ORGANIZATION)
            )
        fixture.org = FIXTURE_ORGANIZATION
    if not missing_provider:
        fixture.save_evidence()
    control = fixture.control
    if failing:
        control = {
            **control,
            "assertions": [
                {"path": "publicly_reachable", "operator": "equals", "expected": True}
            ],
        }
    evaluation = fixture.evaluate(control=control)
    with get_engine().begin() as db:
        db.execute(
            update(organizations)
            .where(organizations.c.id == fixture.org)
            .values(owner_principal_id="user:e2e")
        )
        snapshot = create_snapshot(
            db,
            fixture.org,
            fixture.product,
            context="pull_request",
            binding_id=fixture.binding,
            pull_request_number=17,
            environment="test",
            git_sha=fixtures.COMMIT,
            pack_sha="a" * 40,
            evaluation_ids=[evaluation["id"]],
            now=fixtures.NOW,
        )
        if failing:
            apply_snapshot(db, fixture.org, snapshot["id"])
    return {
        "id": snapshot["id"],
        "sha": snapshot["gitSha"],
        "organizationId": fixture.org,
        "teamId": fixture.team,
        "productId": fixture.product,
    }


class FixtureSource:
    def __init__(self, repository):
        self.repository = repository

    def resolve_tag(self, tag):
        if tag != "v1.2.0" and not (
            self.repository == "arturmiller/specbound-example-provider"
            and tag == "v1.1.0"
        ):
            raise ValueError("Unknown fixture tag")
        return "a" * 40

    def fetch(self, ref):
        if self.repository in (
            "fixture/oscal",
            "fixture/oscal-removal",
            "fixture/oscal-invalid",
            "fixture/oscal-v2",
            "fixture/oscal-requirements",
            "fixture/oscal-profile-scan",
            "fixture/oscal-updates",
        ):
            from tests.test_resource_registry import ResourceFixtureSource

            snapshot = ResourceFixtureSource(self.repository).fetch(ref)
            if self.repository == "fixture/oscal-removal":
                files = dict(snapshot.files)
                for path, kind, resource_id, title, uuid in (
                    (
                        "catalogs/application.json",
                        "catalog",
                        "removal-controls",
                        "Removal Controls",
                        "a2beac83-e38d-45e4-a44d-6696aef75c36",
                    ),
                    (
                        "profiles/application-baseline.json",
                        "profile",
                        "removal-baseline",
                        "Removal Baseline",
                        "f263a64f-47ed-44f1-ad2f-d545d193c518",
                    ),
                ):
                    document = json.loads(files[path])
                    document[kind]["uuid"] = uuid
                    document[kind]["metadata"]["title"] = title
                    document[kind]["metadata"]["props"][0]["value"] = resource_id
                    files[path] = json.dumps(document).encode()
                bindings = json.loads(files["checks/application.json"])
                bindings["spec"]["catalog"]["id"] = "removal-controls"
                files["checks/application.json"] = json.dumps(bindings).encode()
                return GitSnapshot(snapshot.commit, files)
            if self.repository == "fixture/oscal-updates":
                files = dict(snapshot.files)
                product = json.loads(files["products/audio-visualizer.json"])
                product["metadata"]["id"] += "-updates"
                if RESOURCE_REVISION_STAGE != "initial":
                    product["metadata"].update(
                        version="2.0.0", name="Audio Visualizer Updated"
                    )
                    product["spec"]["profile"]["version"] = (
                        "99.0.0" if RESOURCE_REVISION_STAGE == "invalid" else "2.0.0"
                    )
                    product["spec"]["repositories"] = [
                        {"provider": "github", "repository": "example/updated-source"}
                    ]
                    profile = json.loads(files["profiles/application-baseline.json"])
                    profile["profile"]["metadata"]["version"] = "2.0.0"
                    profile["profile"]["imports"][0]["include-controls"][0][
                        "with-ids"
                    ] = ["PY-LIC-001"]
                    profile["profile"]["modify"]["set-parameters"][0]["values"] = [
                        "GPL-3.0-only"
                    ]
                    files["profiles/application-baseline.json"] = json.dumps(
                        profile
                    ).encode()
                files["products/audio-visualizer.json"] = json.dumps(product).encode()
                return GitSnapshot(
                    ("a" if RESOURCE_REVISION_STAGE == "initial" else "c") * 40, files
                )
            if self.repository in (
                "fixture/oscal-requirements",
                "fixture/oscal-profile-scan",
            ):
                files = dict(snapshot.files)
                document = json.loads(files["products/audio-visualizer.json"])
                document["metadata"]["id"] += "-" + self.repository.removeprefix(
                    "fixture/oscal-"
                )
                files["products/audio-visualizer.json"] = json.dumps(document).encode()
                return GitSnapshot(snapshot.commit, files)
            if self.repository.endswith("-invalid"):
                files = dict(snapshot.files)
                files["evidence/second/contracts/request.json"] = (
                    b'{"$schema":"https://json-schema.org/draft/2020-12/schema","type":42}'
                )
                return GitSnapshot(snapshot.commit, files)
            if self.repository.endswith("-v2"):
                files = dict(snapshot.files)
                manifest = json.loads(files["evidence/second/provider.json"])
                manifest["metadata"]["id"] += ".v2"
                manifest["capabilities"][0]["version"] = "v2"
                files["evidence/second/provider.json"] = json.dumps(manifest).encode()
                return GitSnapshot(snapshot.commit, files)
            return snapshot
        if self.repository == "fixture/multi-providers":
            if ref not in ("main", "heads/main", "a" * 40):
                raise ValueError("Unexpected fixture ref")
            root = next(
                parent / "contracts/phase4/examples"
                for parent in Path(__file__).resolve().parents
                if (parent / "contracts/phase4/examples").is_dir()
            )
            files = {
                str(path.relative_to(root)).replace("\\", "/"): path.read_bytes()
                for path in (root / "evidence").rglob("*.json")
            }
            return GitSnapshot("a" * 40, files)
        if ref != "a" * 40:
            raise ValueError("Unexpected fixture commit")
        if (
            self.repository.startswith("fixture/provider")
            or self.repository == "arturmiller/specbound-example-provider"
        ):
            fixtures = Path(__file__).parent / "fixtures" / "provider"
            schema = (fixtures / "schema.json").read_bytes()
            manifest = (fixtures / "provider.yaml").read_bytes()
            if self.repository == "arturmiller/specbound-example-provider":
                example = yaml.safe_load(manifest)
                example["metadata"]["id"] = "org.specbound.example-provider"
                example["capabilities"][0]["id"] = "demo.fixture"
                manifest = yaml.safe_dump(example).encode()
            if self.repository.endswith("-invalid"):
                manifest = b"kind: InvalidProvider\n"
            return GitSnapshot(
                ref,
                {
                    "provider.yaml": manifest,
                    "contracts/collect-request.json": schema,
                    "contracts/observation.json": schema,
                    "schemas/reachability.json": schema,
                    "tests/reachability.yaml": b"name: fixture\n",
                },
            )
        fixtures = Path(__file__).parent / "fixtures" / "governance"
        return GitSnapshot(
            ref,
            {
                "pack.yaml": (fixtures / "pack.yaml").read_bytes(),
                "controls/SEC-NET-001.yaml": (fixtures / "control.yaml").read_bytes(),
            },
        )

    def close(self):
        pass

    def metadata(self):
        return {
            "id": 42,
            "full_name": self.repository,
            "default_branch": "main",
            "private": False,
        }


def main():
    test_url = os.environ.get("SPECBOUND_E2E_DATABASE_URL")
    if not test_url:
        raise RuntimeError(
            "SPECBOUND_E2E_DATABASE_URL must point to a disposable test database"
        )
    os.environ["DATABASE_URL"] = test_url
    os.environ["GITHUB_ORGANIZATION_ID"] = FIXTURE_ORGANIZATION
    workspace_path = Path(WORKSPACE_DIRECTORY.name) / "workspace.json"
    workspace_path.write_text(
        json.dumps(
            {
                "organizationId": FIXTURE_ORGANIZATION,
                "defaultOwnerTeamId": FIXTURE_OWNER_TEAM,
            }
        ),
        encoding="utf-8",
    )
    os.environ["SPECBOUND_WORKSPACE_CONFIG"] = str(workspace_path)
    with get_engine().begin() as db:
        db.execute(
            text(
                "INSERT INTO principals (id, kind, issuer, subject) VALUES ('user:e2e', 'user', 'test:e2e', 'test-user') ON CONFLICT DO NOTHING"
            )
        )
        db.execute(
            text(
                "INSERT INTO organizations (id, name, owner_principal_id) VALUES (:id, :name, :owner) ON CONFLICT DO NOTHING"
            ),
            {
                "id": FIXTURE_ORGANIZATION,
                "name": "Fixture Organization",
                "owner": "user:e2e",
            },
        )
        db.execute(
            text(
                "INSERT INTO teams (id, organization_id, name) VALUES (:id, :org, 'Workspace owner') ON CONFLICT DO NOTHING"
            ),
            {"id": FIXTURE_OWNER_TEAM, "org": FIXTURE_ORGANIZATION},
        )
    app.dependency_overrides[get_current_principal] = lambda: "user:e2e"
    app.dependency_overrides[github_source_factory] = lambda: FixtureSource
    app.dependency_overrides[github_metadata_source_factory] = lambda: FixtureSource
    uvicorn.run(app, host="127.0.0.1", port=18762, log_level="warning")


if __name__ == "__main__":
    main()

"""Test-only server: an in-process identity override, never enabled by the application."""

import os
from pathlib import Path

import uvicorn
from app.database import get_engine
from app.git_source import GitSnapshot
from app.github_repositories import github_metadata_source_factory
from app.identity import get_current_principal
from app.main import app
from app.pack_catalog import github_source_factory
from sqlalchemy import text

FIXTURE_ORGANIZATION = "123e4567-e89b-12d3-a456-426614174000"


@app.post("/__e2e/assessment")
def create_assessment_fixture(failing: bool = False, missing_provider: bool = False):
    """Seed a complete report only in this test-only server."""
    import sys

    from app.findings import apply_snapshot
    from app.snapshots import create_snapshot
    from app.tables import organizations
    from sqlalchemy import update

    sys.path.insert(0, str(Path(__file__).parent))
    import test_rule_evaluation as fixtures

    fixture = fixtures.RuleEvaluationTest(methodName="runTest")
    fixture.setUp()
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
        if tag != "v1.2.0":
            raise ValueError("Unknown fixture tag")
        return "a" * 40

    def fetch(self, ref):
        if ref != "a" * 40:
            raise ValueError("Unexpected fixture commit")
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
    with get_engine().begin() as db:
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
    app.dependency_overrides[get_current_principal] = lambda: "user:e2e"
    app.dependency_overrides[github_source_factory] = lambda: FixtureSource
    app.dependency_overrides[github_metadata_source_factory] = lambda: FixtureSource
    uvicorn.run(app, host="127.0.0.1", port=18762, log_level="warning")


if __name__ == "__main__":
    main()

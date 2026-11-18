"""Test-only API process with real token validation and a disposable database."""

import hashlib
import json
import os
import tempfile
from pathlib import Path

import uvicorn
from app.database import get_engine
from app.main import app
from app.resource_registry import register_resource
from fastapi import Response
from sqlalchemy import text

from tests.test_resource_registry import ResourceFixtureSource

WORKSPACE_DIRECTORY = tempfile.TemporaryDirectory(prefix="specbound-oidc-workspace-")
ORGANIZATION = "123e4567-e89b-12d3-a456-426614174010"
TEAM = "123e4567-e89b-12d3-a456-426614174011"


def seed_workspace():
    """Prepare data only; HTTP requests still verify real provider access tokens."""
    issuer = os.environ["OIDC_ISSUER"]
    principal = "user:" + hashlib.sha256(f"{issuer}\0alice".encode()).hexdigest()
    path = Path(WORKSPACE_DIRECTORY.name) / "workspace.json"
    path.write_text(
        json.dumps({"organizationId": ORGANIZATION, "defaultOwnerTeamId": TEAM})
    )
    os.environ["SPECBOUND_WORKSPACE_CONFIG"] = str(path)
    os.environ["GITHUB_ORGANIZATION_ID"] = ORGANIZATION
    with get_engine().begin() as db:
        db.execute(
            text(
                "INSERT INTO principals (id,kind,issuer,subject) VALUES (:id,'user',:issuer,'alice') ON CONFLICT DO NOTHING"
            ),
            {"id": principal, "issuer": issuer},
        )
        db.execute(
            text(
                "INSERT INTO organizations (id,name,owner_principal_id) VALUES (:id,'OIDC Workspace',:owner) ON CONFLICT DO NOTHING"
            ),
            {"id": ORGANIZATION, "owner": principal},
        )
        db.execute(
            text(
                "INSERT INTO teams (id,organization_id,name) VALUES (:id,:org,'Owner') ON CONFLICT DO NOTHING"
            ),
            {"id": TEAM, "org": ORGANIZATION},
        )
        for kind, manifest, resource_id in (
            ("Catalog", "catalogs/application.json", "application-controls"),
            ("Profile", "profiles/application-baseline.json", "application-baseline"),
            (
                "EvidenceProviderPack",
                "evidence/second/provider.json",
                "org.example.secondary-evidence",
            ),
            ("Product", "products/audio-visualizer.json", "audio-visualizer"),
        ):
            source = ResourceFixtureSource("fixture/oidc-resources")
            if kind == "EvidenceProviderPack":
                document = json.loads(source.files[manifest])
                resource_id = document["metadata"]["id"]
            register_resource(
                ORGANIZATION,
                {
                    "apiVersion": "specbound.example/v1alpha1",
                    "kind": "ResourceSource",
                    "metadata": {
                        "id": resource_id,
                        "version": "1.0.0",
                        "name": resource_id,
                    },
                    "spec": {
                        "resourceType": kind,
                        "provider": "github",
                        "repository": source.repository,
                        "ref": "main",
                        "refType": "branch",
                        "manifestPath": manifest,
                        "expected": {"id": resource_id, "version": "1.0.0"},
                    },
                },
                Response(),
                principal,
                db,
                lambda _: source,
                expected_commit=None,
                preview=False,
            )
        db.execute(
            text(
                "INSERT INTO products (id,name,owner_team_id) VALUES (:id,'Platform API',:team) ON CONFLICT DO NOTHING"
            ),
            {"id": "123e4567-e89b-12d3-a456-426614174012", "team": TEAM},
        )


def main():
    test_url = os.environ.get("SPECBOUND_E2E_DATABASE_URL")
    if not test_url:
        raise RuntimeError(
            "SPECBOUND_E2E_DATABASE_URL must point to a disposable test database"
        )
    os.environ["DATABASE_URL"] = test_url
    seed_workspace()
    uvicorn.run(app, host="127.0.0.1", port=18765, log_level="warning")


if __name__ == "__main__":
    main()

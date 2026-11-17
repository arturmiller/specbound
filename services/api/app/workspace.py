"""Trusted installation context; never inferred from browser state or database order."""

import os
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from jsonschema import ValidationError
from sqlalchemy import select

from app.authorization import organization_access
from app.database import get_connection
from app.identity import get_current_principal
from app.resource_contracts import HERE, read, validate
from app.tables import organizations, teams

router = APIRouter()


def configured_workspace(db):
    try:
        path = Path(os.environ.get("SPECBOUND_WORKSPACE_CONFIG", ""))
        if not path.is_file() or path.stat().st_size > 65536:
            raise ValueError("Missing or excessive workspace configuration")
        config = read(path)
        validate(config, HERE / "workspace.schema.json")
    except (OSError, ValueError, ValidationError, TypeError) as exc:
        raise HTTPException(
            status_code=503, detail="Workspace is not configured correctly"
        ) from exc
    team = (
        db.execute(
            select(teams).where(
                teams.c.id == config["defaultOwnerTeamId"],
                teams.c.organization_id == config["organizationId"],
            )
        )
        .mappings()
        .one_or_none()
    )
    organization = (
        db.execute(
            select(organizations).where(organizations.c.id == config["organizationId"])
        )
        .mappings()
        .one_or_none()
    )
    if team is None or organization is None:
        raise HTTPException(
            status_code=503,
            detail="Workspace organization or owner team is unavailable",
        )
    return {
        **config,
        "organization": {
            "id": organization["id"],
            "name": organization["name"],
            "ownerPrincipalId": organization["owner_principal_id"],
        },
    }


@router.get("/workspace")
def get_workspace(
    principal=Depends(get_current_principal),
    db=Depends(get_connection, scope="function"),
):
    config = configured_workspace(db)
    organization_access(db, config["organizationId"], principal, write=False)
    return config

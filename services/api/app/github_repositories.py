"""Read metadata for an authorized product's GitHub repository binding."""

import os
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.engine import Connection

from app.database import get_connection
from app.git_source import SourceNotFound, SourceUnavailable
from app.github_source import configured_github_source
from app.identity import get_current_principal
from app.products import _product
from app.tables import repo_bindings

router = APIRouter(dependencies=[Depends(get_current_principal)])


@router.get("/products/{product_id}/repositories/{binding_id}/github")
def github_repository_metadata(
    product_id: str,
    binding_id: str,
    principal: Annotated[str, Depends(get_current_principal)],
    db: Annotated[Connection, Depends(get_connection)],
):
    _, team = _product(db, product_id, principal, "read")
    configured_org = os.environ.get("GITHUB_ORGANIZATION_ID", "")
    if not configured_org:
        raise HTTPException(
            status_code=503, detail="GitHub organization is not configured"
        )
    if team["organization_id"] != configured_org:
        raise HTTPException(
            status_code=403, detail="GitHub App is not available for this organization"
        )
    binding = (
        db.execute(
            select(repo_bindings).where(
                repo_bindings.c.id == binding_id,
                repo_bindings.c.product_id == product_id,
            )
        )
        .mappings()
        .one_or_none()
    )
    if binding is None:
        raise HTTPException(status_code=404, detail="Not found")
    if binding["provider"].lower() != "github":
        raise HTTPException(status_code=400, detail="Repository provider is not GitHub")
    try:
        source = configured_github_source(binding["repository"])
        try:
            return source.metadata()
        finally:
            source.close()
    except SourceNotFound as exc:
        raise HTTPException(
            status_code=404, detail="GitHub repository not found"
        ) from exc
    except SourceUnavailable as exc:
        raise HTTPException(
            status_code=503, detail="GitHub source unavailable"
        ) from exc

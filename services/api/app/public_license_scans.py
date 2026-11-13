"""Public, tokenless license scan requests scoped to a product's team."""

from datetime import datetime, timezone
from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, StringConstraints
from sqlalchemy import insert, select
from sqlalchemy.engine import Connection

from app.database import get_connection
from app.github_source import REPOSITORY
from app.identity import get_current_principal
from app.products import _product
from app.tables import public_license_scans, repo_bindings

router = APIRouter(dependencies=[Depends(get_current_principal)])
Db = Annotated[Connection, Depends(get_connection, scope="function")]
Principal = Annotated[str, Depends(get_current_principal)]
Ref = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)
]


class ScanRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ref: Ref


def _binding(db, product_id, binding_id):
    row = (
        db.execute(
            select(repo_bindings).where(
                repo_bindings.c.id == binding_id,
                repo_bindings.c.product_id == product_id,
            )
        )
        .mappings()
        .one_or_none()
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Repository not found")
    if row["provider"].lower() != "github" or not REPOSITORY.fullmatch(
        row["repository"]
    ):
        raise HTTPException(
            status_code=422, detail="A GitHub owner/repository is required"
        )
    return row


def _serialize(row):
    return {
        "id": row["id"],
        "productId": row["product_id"],
        "bindingId": row["binding_id"],
        "repository": row["repository"],
        "ref": row["ref"],
        "status": row["status"],
        "createdAt": row["created_at"],
        "finishedAt": row["finished_at"],
        "errorCode": row["error_code"],
        "result": row["result"],
    }


@router.get("/products/{product_id}/repositories/{binding_id}/public-license-scans")
def list_scans(product_id: str, binding_id: str, principal: Principal, db: Db):
    _, team = _product(db, product_id, principal, "read")
    binding = _binding(db, product_id, binding_id)
    rows = db.execute(
        select(public_license_scans)
        .where(
            public_license_scans.c.organization_id == team["organization_id"],
            public_license_scans.c.product_id == product_id,
            public_license_scans.c.binding_id == binding_id,
            public_license_scans.c.repository == binding["repository"],
        )
        .order_by(
            public_license_scans.c.created_at.desc(), public_license_scans.c.id.desc()
        )
        .limit(20)
    ).mappings()
    return [_serialize(row) for row in rows]


@router.post(
    "/products/{product_id}/repositories/{binding_id}/public-license-scans",
    status_code=201,
)
def start_scan(
    product_id: str, binding_id: str, data: ScanRequest, principal: Principal, db: Db
):
    _, team = _product(db, product_id, principal, "edit", lock=True)
    binding = _binding(db, product_id, binding_id)
    if any(part in (".", "..") for part in binding["repository"].split("/")):
        raise HTTPException(status_code=422, detail="Invalid GitHub repository")
    if "\x00" in data.ref:
        raise HTTPException(status_code=422, detail="Invalid Git reference")
    active = db.execute(
        select(public_license_scans.c.id).where(
            public_license_scans.c.binding_id == binding_id,
            public_license_scans.c.status.in_(("pending", "running")),
        )
    ).first()
    if active:
        raise HTTPException(status_code=409, detail="A scan is already pending")
    row = (
        db.execute(
            insert(public_license_scans)
            .values(
                id=str(uuid4()),
                organization_id=team["organization_id"],
                product_id=product_id,
                binding_id=binding_id,
                repository=binding["repository"],
                ref=data.ref,
                status="pending",
                created_at=datetime.now(timezone.utc),
                attempts=0,
            )
            .returning(public_license_scans)
        )
        .mappings()
        .one()
    )
    return _serialize(row)

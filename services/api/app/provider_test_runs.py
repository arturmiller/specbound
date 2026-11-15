"""Owner-only synthetic provider test requests, never assessment evidence."""

from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy import insert, select
from sqlalchemy.engine import Connection

from app.agents import human_owner
from app.database import get_connection
from app.identity import get_current_principal
from app.tables import pack_catalog, pack_revisions, provider_test_runs

router = APIRouter(dependencies=[Depends(get_current_principal)])
Db = Annotated[Connection, Depends(get_connection, scope="function")]
Principal = Annotated[str, Depends(get_current_principal)]
EXAMPLE_REPOSITORY = "arturmiller/specbound-example-provider"
EXAMPLE_CAPABILITY = {"id": "demo.fixture", "version": "v1"}


class TestRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")


def example_pack(db, organization_id, revision_id):
    row = db.execute(
        select(pack_revisions, pack_catalog.c.kind, pack_catalog.c.capabilities)
        .select_from(pack_revisions.join(pack_catalog, pack_catalog.c.revision_id == pack_revisions.c.id))
        .where(pack_revisions.c.organization_id == organization_id, pack_revisions.c.id == revision_id)
    ).mappings().one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Provider pack not found")
    if row["kind"] != "provider" or row["repository"] != EXAMPLE_REPOSITORY or not any(
        all(cap.get(key) == value for key, value in EXAMPLE_CAPABILITY.items())
        for cap in row["capabilities"]
    ):
        raise HTTPException(status_code=422, detail="Only the synthetic example provider is supported")
    return row


def serialize(row):
    return {
        "id": row["id"], "packRevisionId": row["pack_revision_id"],
        "packCommit": row["pack_commit"], "status": row["status"],
        "createdAt": row["created_at"], "synthetic": True,
    }


@router.get("/organizations/{organization_id}/packs/{revision_id}/test-runs")
def list_test_runs(organization_id: str, revision_id: str, principal: Principal, db: Db):
    human_owner(db, organization_id, principal)
    example_pack(db, organization_id, revision_id)
    rows = db.execute(
        select(provider_test_runs)
        .where(provider_test_runs.c.organization_id == organization_id, provider_test_runs.c.pack_revision_id == revision_id)
        .order_by(provider_test_runs.c.created_at.desc(), provider_test_runs.c.id.desc())
    ).mappings()
    return [serialize(row) for row in rows]


@router.post("/organizations/{organization_id}/packs/{revision_id}/test-runs", status_code=201)
def create_test_run(organization_id: str, revision_id: str, body: TestRequest, principal: Principal, db: Db):
    human_owner(db, organization_id, principal)
    pack = example_pack(db, organization_id, revision_id)
    row = db.execute(
        insert(provider_test_runs).values(
            id=str(uuid4()), organization_id=organization_id, pack_revision_id=revision_id,
            pack_commit=pack["commit_sha"], status="pending",
        ).returning(provider_test_runs)
    ).mappings().one()
    return serialize(row)

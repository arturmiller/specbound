"""Read persisted evidence only within the caller's visible product teams."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.engine import Connection

from app.authorization import visible_teams
from app.database import get_connection
from app.evidence_records import _serialize
from app.identity import get_current_principal
from app.tables import evidence_records, products

router = APIRouter(dependencies=[Depends(get_current_principal)])
Principal = Annotated[str, Depends(get_current_principal)]
Db = Annotated[Connection, Depends(get_connection, scope="function")]


def _visible_evidence(db: Connection, organization_id: str, principal: str):
    team_ids = [team["id"] for team in visible_teams(db, organization_id, principal)]
    return (
        select(evidence_records)
        .select_from(
            evidence_records.join(products, evidence_records.c.product_id == products.c.id)
        )
        .where(
            evidence_records.c.organization_id == organization_id,
            products.c.owner_team_id.in_(team_ids),
        )
    )


@router.get("/organizations/{organization_id}/evidence")
def list_evidence(
    organization_id: str,
    principal: Principal,
    db: Db,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0, le=9223372036854775807)] = 0,
):
    rows = db.execute(
        _visible_evidence(db, organization_id, principal)
        .order_by(evidence_records.c.observed_at.desc(), evidence_records.c.id.desc())
        .offset(offset)
        .limit(limit + 1)
    ).mappings().all()
    return {
        "items": [_serialize(row) for row in rows[:limit]],
        "nextOffset": offset + limit if len(rows) > limit else None,
    }


@router.get("/organizations/{organization_id}/evidence/{evidence_id}")
def get_evidence(organization_id: str, evidence_id: str, principal: Principal, db: Db):
    row = db.execute(
        _visible_evidence(db, organization_id, principal).where(
            evidence_records.c.id == evidence_id
        )
    ).mappings().one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Evidence not found")
    return _serialize(row)

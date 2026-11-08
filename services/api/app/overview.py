"""Tenant- and team-scoped inventory for the portal overview."""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.engine import Connection

from app.authorization import visible_teams
from app.database import get_connection
from app.identity import get_current_principal
from app.pack_catalog import _query as pack_query
from app.tables import assessment_snapshots, findings, pack_revisions, products

router = APIRouter(dependencies=[Depends(get_current_principal)])


@router.get("/organizations/{organization_id}/overview")
def overview(
    organization_id: str,
    principal: Annotated[str, Depends(get_current_principal)],
    db: Annotated[Connection, Depends(get_connection, scope="function")],
):
    teams = visible_teams(db, organization_id, principal)
    team_ids = [team["id"] for team in teams]
    product_rows = (
        db.execute(
            select(products)
            .where(products.c.owner_team_id.in_(team_ids))
            .order_by(products.c.id)
        )
        .mappings()
        .all()
    )
    product_ids = [product["id"] for product in product_rows]
    finding_rows = (
        db.execute(
            select(findings)
            .where(
                findings.c.organization_id == organization_id,
                findings.c.product_id.in_(product_ids),
            )
            .order_by(findings.c.id)
        )
        .mappings()
        .all()
    )
    packs = (
        db.execute(pack_query(organization_id).order_by(pack_revisions.c.id))
        .mappings()
        .all()
    )
    assessments = (
        db.execute(
            select(assessment_snapshots)
            .where(
                assessment_snapshots.c.organization_id == organization_id,
                assessment_snapshots.c.product_id.in_(product_ids),
            )
            .order_by(
                assessment_snapshots.c.created_at.desc(), assessment_snapshots.c.id
            )
        )
        .mappings()
        .all()
    )
    return {
        "products": [
            {"id": row["id"], "name": row["name"], "teamId": row["owner_team_id"]}
            for row in product_rows
        ],
        "packs": [
            {
                "id": row["id"],
                "repository": row["repository"],
                "tag": row["tag"],
                "kind": row["kind"],
                "name": row["manifest"]["metadata"]["id"],
            }
            for row in packs
        ],
        "findings": [
            {
                "id": row["id"],
                "productId": row["product_id"],
                "subjectId": row["subject_id"],
                "controlId": row["control_id"],
                "environment": row["environment"],
                "status": row["status"],
                "snapshotId": row["last_snapshot_id"],
            }
            for row in finding_rows
        ],
        "assessments": [
            {
                "id": row["id"],
                "productId": row["product_id"],
                "environment": row["environment"],
                "context": row["context"],
                "pullRequestNumber": row["pull_request_number"],
                "createdAt": row["created_at"],
                "gitSha": row["git_sha"],
                "counts": row["counts"],
                "evaluations": [
                    {"status": item["status"], "reason": item["reason"]}
                    for item in row["evaluations"]
                ],
            }
            for row in assessments
        ],
    }

"""Apply current assessment snapshots to stable, scoped finding lifecycles."""

import hashlib
import json
from uuid import uuid4

from sqlalchemy import insert, select, update
from sqlalchemy.engine import Connection

from app.tables import assessment_snapshots, finding_history, findings, products, teams


def _fingerprint(snapshot, item):
    identity = [
        snapshot["organization_id"],
        snapshot["product_id"],
        snapshot["binding_id"],
        snapshot["context"],
        snapshot["pull_request_number"],
        snapshot["environment"],
        item["subjectId"],
        item["controlId"],
    ]
    return hashlib.sha256(
        json.dumps(identity, ensure_ascii=True, separators=(",", ":")).encode()
    ).hexdigest()


def _serialize(row):
    return {
        "id": row["id"],
        "fingerprint": row["fingerprint"],
        "organizationId": row["organization_id"],
        "productId": row["product_id"],
        "bindingId": row["binding_id"],
        "context": row["context"],
        "pullRequestNumber": row["pull_request_number"],
        "environment": row["environment"],
        "subjectId": row["subject_id"],
        "controlId": row["control_id"],
        "status": row["status"],
        "createdAt": row["created_at"],
        "updatedAt": row["updated_at"],
        "lastSnapshotId": row["last_snapshot_id"],
    }


def list_findings(db: Connection, organization_id, product_id):
    rows = (
        db.execute(
            select(findings)
            .where(
                findings.c.organization_id == organization_id,
                findings.c.product_id == product_id,
            )
            .order_by(findings.c.fingerprint)
        )
        .mappings()
        .all()
    )
    return [_serialize(row) for row in rows]


def get_history(db: Connection, organization_id, finding_id):
    rows = (
        db.execute(
            select(finding_history)
            .select_from(
                finding_history.join(
                    findings, finding_history.c.finding_id == findings.c.id
                )
            )
            .where(
                findings.c.id == finding_id,
                findings.c.organization_id == organization_id,
            )
            .order_by(finding_history.c.observed_at, finding_history.c.snapshot_id)
        )
        .mappings()
        .all()
    )
    return [
        {
            "id": row["id"],
            "findingId": row["finding_id"],
            "snapshotId": row["snapshot_id"],
            "evaluationId": row["evaluation_id"],
            "outcome": row["outcome"],
            "stateAfter": row["state_after"],
            "reason": row["reason"],
            "observedAt": row["observed_at"],
        }
        for row in rows
    ]


def apply_snapshot(db: Connection, organization_id, snapshot_id):
    """Apply a latest snapshot once; stale snapshots cannot change finding state."""
    snapshot = (
        db.execute(
            select(assessment_snapshots).where(
                assessment_snapshots.c.id == snapshot_id,
                assessment_snapshots.c.organization_id == organization_id,
            )
        )
        .mappings()
        .one_or_none()
    )
    if snapshot is None:
        raise LookupError("Assessment snapshot not found")
    owned = db.execute(
        select(products.c.id)
        .select_from(products.join(teams, products.c.owner_team_id == teams.c.id))
        .where(
            products.c.id == snapshot["product_id"],
            teams.c.organization_id == organization_id,
        )
        .with_for_update(of=products)
    ).first()
    if owned is None:
        raise LookupError("Product not found in organization")
    latest = db.execute(
        select(assessment_snapshots.c.id)
        .where(
            assessment_snapshots.c.organization_id == organization_id,
            assessment_snapshots.c.product_id == snapshot["product_id"],
            assessment_snapshots.c.binding_id == snapshot["binding_id"],
            assessment_snapshots.c.context == snapshot["context"],
            assessment_snapshots.c.pull_request_number
            == snapshot["pull_request_number"],
            assessment_snapshots.c.environment == snapshot["environment"],
        )
        .order_by(
            assessment_snapshots.c.created_at.desc(), assessment_snapshots.c.id.desc()
        )
        .limit(1)
    ).scalar_one()
    if latest != snapshot_id:
        return []
    affected = []
    for item in snapshot["evaluations"]:
        fingerprint = _fingerprint(snapshot, item)
        existing = (
            db.execute(select(findings).where(findings.c.fingerprint == fingerprint))
            .mappings()
            .one_or_none()
        )
        if existing is None:
            if item["status"] != "FAIL":
                continue
            finding_id = str(uuid4())
            state = "open"
            db.execute(
                insert(findings).values(
                    id=finding_id,
                    fingerprint=fingerprint,
                    organization_id=organization_id,
                    product_id=snapshot["product_id"],
                    binding_id=snapshot["binding_id"],
                    context=snapshot["context"],
                    pull_request_number=snapshot["pull_request_number"],
                    environment=snapshot["environment"],
                    subject_id=item["subjectId"],
                    control_id=item["controlId"],
                    status=state,
                    created_at=snapshot["created_at"],
                    updated_at=snapshot["created_at"],
                    last_snapshot_id=snapshot_id,
                )
            )
        else:
            finding_id = existing["id"]
            if db.execute(
                select(finding_history.c.id).where(
                    finding_history.c.finding_id == finding_id,
                    finding_history.c.snapshot_id == snapshot_id,
                )
            ).first():
                continue
            state = (
                "open"
                if item["status"] == "FAIL"
                else "resolved"
                if item["status"] == "PASS"
                else existing["status"]
            )
            db.execute(
                update(findings)
                .where(findings.c.id == finding_id)
                .values(
                    status=state,
                    updated_at=snapshot["created_at"],
                    last_snapshot_id=snapshot_id,
                )
            )
        db.execute(
            insert(finding_history).values(
                id=str(uuid4()),
                finding_id=finding_id,
                snapshot_id=snapshot_id,
                evaluation_id=item["id"],
                outcome=item["status"],
                state_after=state,
                reason=item["reason"],
                observed_at=snapshot["created_at"],
            )
        )
        affected.append(finding_id)
    return affected

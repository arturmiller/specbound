"""Owner-authorized license decisions for an observed package and use."""

import os
from datetime import datetime, timezone
from typing import Annotated, Literal
from urllib.parse import urlsplit
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from pydantic import AwareDatetime, BaseModel, ConfigDict, StringConstraints
from sqlalchemy import insert, select, update

from app.audit import record_event
from app.authorization import organization_access
from app.license_scope import (
    approval_scope,
    current_license_configuration,
    license_decision,
    license_use,
    live_approvals,
)
from app.products import Db, Principal, _product
from app.tables import (
    assessment_jobs,
    assessment_snapshots,
    license_approvals,
    repo_bindings,
    rule_evaluations,
)

router = APIRouter()
RecordId = Annotated[str, StringConstraints(min_length=1, max_length=36)]
Note = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1500)
]
ProofUrl = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2048)
]


class ApprovalRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    assessmentId: RecordId
    evaluationId: RecordId
    kind: Literal["conditions-met", "license-rights"]
    reason: Note
    conditions: Note
    proofUrl: ProofUrl
    expiresAt: AwareDatetime | None = None


def _owner(db, product_id, principal, *, lock=False):
    _, team = _product(db, product_id, principal, "read", lock=lock)
    org = team["organization_id"]
    organization_access(db, org, principal, write=True)
    return org


@router.post("/products/{product_id}/license-approvals", status_code=201)
def approve_use(product_id: str, data: ApprovalRequest, principal: Principal, db: Db):
    org = _owner(db, product_id, principal, lock=True)
    now = datetime.now(timezone.utc)
    try:
        url = urlsplit(data.proofUrl)
        if url.scheme != "https" or not url.hostname or url.username or url.password:
            raise ValueError("A protected HTTPS evidence link is required")
    except ValueError as exc:
        raise HTTPException(
            422, "Ein geschützter HTTPS-Nachweislink ist erforderlich"
        ) from exc
    if data.expiresAt is not None and data.expiresAt <= now:
        raise HTTPException(422, "Die Freigabe muss in der Zukunft ablaufen")
    snapshot = (
        db.execute(
            select(assessment_snapshots).filter_by(
                id=data.assessmentId, product_id=product_id, organization_id=org
            )
        )
        .mappings()
        .one_or_none()
    )
    if snapshot is None or data.evaluationId not in snapshot["evaluation_ids"]:
        raise HTTPException(404, "Bewertung nicht gefunden")
    evaluation = (
        db.execute(
            select(rule_evaluations).filter_by(
                id=data.evaluationId, product_id=product_id, organization_id=org
            )
        )
        .mappings()
        .one()
    )
    context = snapshot["governance_context"]
    scope = approval_scope(
        context, snapshot["binding_id"], evaluation["subject"], evaluation["control"]
    )
    if scope is None or not current_license_configuration(db, context):
        raise HTTPException(
            409, "Ein aktuelles Profil und eine gehashte Paketversion sind erforderlich"
        )
    if evaluation["status"] == "PASS":
        raise HTTPException(
            409, "Für diese Bewertung ist keine neue Freigabe erforderlich"
        )
    if data.kind == "conditions-met" and evaluation["status"] != "FAIL":
        raise HTTPException(
            422, "Erfüllte Auflagen erfordern eine festgestellte Lizenz"
        )
    if db.execute(live_approvals(scope, now)).first():
        raise HTTPException(409, "Für diesen Einsatz gilt bereits eine Freigabe")
    row = (
        db.execute(
            insert(license_approvals)
            .values(
                id=str(uuid4()),
                **scope,
                kind=data.kind,
                reason=data.reason,
                conditions=data.conditions,
                proof_url=data.proofUrl,
                approved_by=principal,
                created_at=now,
                expires_at=data.expiresAt,
            )
            .returning(license_approvals)
        )
        .mappings()
        .one()
    )
    record_event(
        db,
        organization_id=org,
        actor_id=principal,
        action="license-approval.created",
        target_id=row["id"],
    )
    return license_decision(row)


def _approval(db, org, product, approval_id):
    row = (
        db.execute(
            select(license_approvals).filter_by(
                id=approval_id, organization_id=org, product_id=product
            )
        )
        .mappings()
        .one_or_none()
    )
    if row is None:
        raise HTTPException(404, "Freigabe nicht gefunden")
    return row


@router.get("/products/{product_id}/license-approvals/{approval_id}")
def get_approval(product_id: str, approval_id: str, principal: Principal, db: Db):
    org = _owner(db, product_id, principal)
    row = _approval(db, org, product_id, approval_id)
    return {
        **license_decision(row),
        "proofUrl": row["proof_url"],
        "approvedBy": row["approved_by"],
        "revokedAt": row["revoked_at"],
    }


@router.post("/products/{product_id}/license-approvals/{approval_id}/revoke")
def revoke_approval(product_id: str, approval_id: str, principal: Principal, db: Db):
    org = _owner(db, product_id, principal, lock=True)
    row = _approval(db, org, product_id, approval_id)
    if row["revoked_at"] is None:
        now = datetime.now(timezone.utc)
        db.execute(
            update(license_approvals).filter_by(id=approval_id).values(revoked_at=now)
        )
        record_event(
            db,
            organization_id=org,
            actor_id=principal,
            action="license-approval.revoked",
            target_id=approval_id,
        )
    return {"revoked": True}


@router.post("/assessments/{snapshot_id}/license-recheck", status_code=202)
def recheck_license_assessment(snapshot_id: str, principal: Principal, db: Db):
    snapshot = (
        db.execute(
            select(assessment_snapshots).filter_by(
                id=snapshot_id, context="pull_request"
            )
        )
        .mappings()
        .one_or_none()
    )
    if snapshot is None:
        raise HTTPException(404, "PR-Prüfung nicht gefunden")
    _, team = _product(db, snapshot["product_id"], principal, "edit")
    context = snapshot["governance_context"]
    if (
        os.environ.get("PR_LICENSE_SCAN_ENABLED", "").lower() != "true"
        or team["organization_id"] != snapshot["organization_id"]
        or not license_use(context)
        or not current_license_configuration(db, context)
    ):
        raise HTTPException(
            409, "Eine erneute Prüfung ist für diesen Stand nicht verfügbar"
        )
    result = db.execute(
        update(assessment_jobs)
        .where(
            assessment_jobs.c.result_snapshot_id == snapshot_id,
            assessment_jobs.c.product_id == snapshot["product_id"],
            assessment_jobs.c.organization_id == snapshot["organization_id"],
            assessment_jobs.c.status == "completed",
            assessment_jobs.c.check_valid_until.is_(None),
            assessment_jobs.c.binding_id.in_(
                select(repo_bindings.c.id).where(repo_bindings.c.active.is_(True))
            ),
        )
        .values(
            status="pending",
            attempts=0,
            result_snapshot_id=None,
            lease_token=None,
            lease_until=None,
            check_processed_at=None,
            check_retry_at=None,
            comment_processed_at=None,
            comment_retry_at=None,
        )
        .returning(assessment_jobs.c.id)
    ).scalar_one_or_none()
    if result is None:
        raise HTTPException(409, "Der Lauf ist bereits eingeplant oder wurde ersetzt")
    record_event(
        db,
        organization_id=snapshot["organization_id"],
        actor_id=principal,
        action="license-approval.recheck",
        target_id=snapshot_id,
    )
    return {"queued": True}

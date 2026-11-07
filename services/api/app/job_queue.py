"""PostgreSQL job claims with time-limited, fenced completion."""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

from sqlalchemy import and_, or_, select, update
from sqlalchemy.engine import Connection

from app.findings import apply_snapshot
from app.tables import assessment_jobs, assessment_snapshots

MAX_ATTEMPTS = 3


class LeaseLost(RuntimeError):
    """The job is no longer owned by the supplied worker lease."""


def _utc(value):
    if (
        not isinstance(value, datetime)
        or value.tzinfo is None
        or value.utcoffset() is None
    ):
        raise ValueError("A timezone-aware clock is required")
    return value.astimezone(timezone.utc)


def claim_next(db: Connection, organization_id, *, now, lease_seconds=30):
    """Lock one pending or expired job without blocking other queue consumers."""
    now = _utc(now)
    if type(lease_seconds) is not int or not 1 <= lease_seconds <= 3600:
        raise ValueError("Lease duration must be between 1 and 3600 seconds")
    for _ in range(100):
        row = (
            db.execute(
                select(assessment_jobs)
                .where(
                    assessment_jobs.c.organization_id == organization_id,
                    or_(
                        assessment_jobs.c.status == "pending",
                        and_(
                            assessment_jobs.c.status == "running",
                            assessment_jobs.c.lease_until <= now,
                        ),
                    ),
                )
                .order_by(assessment_jobs.c.created_at, assessment_jobs.c.id)
                .with_for_update(skip_locked=True)
                .limit(1)
            )
            .mappings()
            .one_or_none()
        )
        if row is None:
            return None
        if row["attempts"] >= MAX_ATTEMPTS:
            db.execute(
                update(assessment_jobs)
                .where(assessment_jobs.c.id == row["id"])
                .values(
                    status="dead",
                    lease_token=None,
                    lease_until=None,
                    last_error="attempts-exhausted",
                )
            )
            continue
        token = str(uuid4())
        attempts = row["attempts"] + 1
        db.execute(
            update(assessment_jobs)
            .where(assessment_jobs.c.id == row["id"])
            .values(
                status="running",
                attempts=attempts,
                lease_token=token,
                lease_until=now + timedelta(seconds=lease_seconds),
                last_error=None,
            )
        )
        return {
            "id": row["id"],
            "organizationId": row["organization_id"],
            "productId": row["product_id"],
            "bindingId": row["binding_id"],
            "pullRequestId": row["pull_request_id"],
            "pullRequestNumber": row["pull_request_number"],
            "headSha": row["head_sha"],
            "attempts": attempts,
            "leaseToken": token,
        }
    return None


def fail_job(db: Connection, job_id, lease_token, *, now):
    now = _utc(now)
    row = (
        db.execute(
            select(assessment_jobs)
            .where(
                assessment_jobs.c.id == job_id,
                assessment_jobs.c.status == "running",
                assessment_jobs.c.lease_token == lease_token,
                assessment_jobs.c.lease_until > now,
            )
            .with_for_update()
        )
        .mappings()
        .one_or_none()
    )
    if row is None:
        raise LeaseLost("Job lease is no longer valid")
    state = "dead" if row["attempts"] >= MAX_ATTEMPTS else "pending"
    db.execute(
        update(assessment_jobs)
        .where(assessment_jobs.c.id == job_id)
        .values(
            status=state,
            lease_token=None,
            lease_until=None,
            last_error="processor-failed",
        )
    )
    return state


def finish_job(db: Connection, job_id, lease_token, *, clock, build_snapshot):
    """Commit the snapshot and job result together while fencing expired leases."""
    with db.begin_nested():
        row = (
            db.execute(
                select(assessment_jobs)
                .where(assessment_jobs.c.id == job_id)
                .with_for_update()
            )
            .mappings()
            .one_or_none()
        )
        if row is None or row["lease_token"] != lease_token:
            raise LeaseLost("Job lease is no longer valid")
        if row["status"] == "completed":
            return row["result_snapshot_id"]
        if (
            row["status"] != "running"
            or not db.execute(
                select(assessment_jobs.c.id).where(
                    assessment_jobs.c.id == job_id,
                    assessment_jobs.c.lease_until > _utc(clock()),
                )
            ).first()
        ):
            raise LeaseLost("Job lease expired")
        snapshot_id = build_snapshot(db)
        snapshot = db.execute(
            select(assessment_snapshots.c.id).where(
                assessment_snapshots.c.id == snapshot_id,
                assessment_snapshots.c.organization_id == row["organization_id"],
                assessment_snapshots.c.product_id == row["product_id"],
                assessment_snapshots.c.binding_id == row["binding_id"],
                assessment_snapshots.c.context == "pull_request",
                assessment_snapshots.c.pull_request_number
                == row["pull_request_number"],
                assessment_snapshots.c.git_sha == row["head_sha"],
            )
        ).first()
        if snapshot is None:
            raise ValueError("Snapshot does not match the queued PR head")
        apply_snapshot(db, row["organization_id"], snapshot_id)
        if not db.execute(
            select(assessment_jobs.c.id).where(
                assessment_jobs.c.id == job_id,
                assessment_jobs.c.lease_until > _utc(clock()),
            )
        ).first():
            raise LeaseLost("Job lease expired before completion")
        db.execute(
            update(assessment_jobs)
            .where(assessment_jobs.c.id == job_id)
            .values(
                status="completed",
                lease_until=None,
                result_snapshot_id=snapshot_id,
                last_error=None,
            )
        )
        return snapshot_id

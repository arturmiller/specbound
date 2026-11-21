"""Worker polling with an explicitly supplied trusted assessment handler."""

import logging
from datetime import datetime, timezone

from app.job_queue import LeaseLost, claim_next, fail_job, finish_job
from app.tables import products
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

logger = logging.getLogger(__name__)


def poll_once(
    engine,
    organization_id,
    prepare,
    *,
    clock=lambda: datetime.now(timezone.utc),
    lease_seconds=30,
):
    with engine.begin() as db:
        lease = claim_next(
            db, organization_id, now=clock(), lease_seconds=lease_seconds
        )
    if lease is None:
        return False
    try:
        build_snapshot = prepare(lease)
        if not callable(build_snapshot):
            raise ValueError("The handler must return a snapshot builder")
        with engine.begin() as db:
            # Repository edits and deletion lock the product before dependent rows.
            if not db.execute(
                select(products.c.id)
                .where(products.c.id == lease["productId"])
                .with_for_update()
            ).first():
                raise LeaseLost("Product no longer exists")
            finish_job(
                db,
                lease["id"],
                lease["leaseToken"],
                clock=clock,
                build_snapshot=build_snapshot,
            )
    except LeaseLost:
        logger.warning("Job lease expired: %s", lease["id"])
    except Exception:
        logger.warning("Job handler failed: %s", lease["id"])
        try:
            with engine.begin() as db:
                fail_job(db, lease["id"], lease["leaseToken"], now=clock())
        except LeaseLost:
            logger.warning("Failed job lease expired: %s", lease["id"])
    return True


def run_queue(engine, organization_id, prepare, stop, *, interval=1.0, lease_seconds=30):
    """Poll until stopped; no queue runs without a supplied handler."""
    if interval <= 0:
        raise ValueError("Polling interval must be positive")
    while not stop.is_set():
        try:
            worked = poll_once(
                engine, organization_id, prepare, lease_seconds=lease_seconds
            )
        except SQLAlchemyError:
            logger.warning("Queue database unavailable")
            worked = False
        if not worked:
            stop.wait(interval)

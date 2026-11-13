"""Lease and execute public scan previews without access tokens or shell commands."""

import json
import logging
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.tables import products, public_license_scans, repo_bindings, teams
from sqlalchemy import and_, func, or_, select, update

logger = logging.getLogger(__name__)
LEASE_SECONDS = 180
PROCESS_TIMEOUT = 120
MAX_OUTPUT_BYTES = 8 * 1024 * 1024
MAX_ATTEMPTS = 3


def _clock():
    return datetime.now(timezone.utc)


def claim(db, *, now):
    row = (
        db.execute(
            select(public_license_scans)
            .where(
                or_(
                    public_license_scans.c.status == "pending",
                    and_(
                        public_license_scans.c.status == "running",
                        public_license_scans.c.lease_until <= now,
                    ),
                )
            )
            .order_by(public_license_scans.c.created_at, public_license_scans.c.id)
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
            update(public_license_scans)
            .where(public_license_scans.c.id == row["id"])
            .values(
                status="failed",
                error_code="attempts-exhausted",
                finished_at=now,
                lease_token=None,
                lease_until=None,
            )
        )
        return None
    token = str(uuid4())
    db.execute(
        update(public_license_scans)
        .where(public_license_scans.c.id == row["id"])
        .values(
            status="running",
            attempts=row["attempts"] + 1,
            lease_token=token,
            lease_until=now + timedelta(seconds=LEASE_SECONDS),
            error_code=None,
        )
    )
    return {**dict(row), "lease_token": token, "attempts": row["attempts"] + 1}


def _run(repository, ref):
    try:
        with tempfile.TemporaryFile() as output:
            process = subprocess.run(
                [sys.executable, "-m", "app.public_license_runner", repository, ref],
                stdout=output,
                stderr=subprocess.DEVNULL,
                timeout=PROCESS_TIMEOUT,
                check=False,
                env={
                    "PATH": "/usr/local/bin:/usr/bin:/bin",
                    "PYTHONIOENCODING": "utf-8",
                },
            )
            if process.returncode or output.tell() > MAX_OUTPUT_BYTES:
                return {"status": "error", "errorCode": "scanner-failed"}
            output.seek(0)
            response = json.loads(output.read(MAX_OUTPUT_BYTES + 1))
        if not isinstance(response, dict) or response.get("status") not in (
            "ok",
            "error",
        ):
            return {"status": "error", "errorCode": "scanner-failed"}
        return response
    except subprocess.TimeoutExpired:
        return {"status": "error", "errorCode": "timeout"}
    except (OSError, ValueError, TypeError):
        return {"status": "error", "errorCode": "scanner-failed"}


def finish(db, lease, response, *, now):
    # Repository edits and deletion take the product lock first. Hold the same
    # lock until completion so the source cannot change after our scope check.
    if not db.execute(
        select(products.c.id).where(products.c.id == lease["product_id"]).with_for_update()
    ).first():
        return False
    row = (
        db.execute(
            select(public_license_scans)
            .where(
                public_license_scans.c.id == lease["id"],
                public_license_scans.c.status == "running",
                public_license_scans.c.lease_token == lease["lease_token"],
                public_license_scans.c.lease_until > now,
            )
            .with_for_update()
        )
        .mappings()
        .one_or_none()
    )
    if row is None:
        return False
    binding = db.execute(
        select(repo_bindings.c.id)
        .select_from(
            repo_bindings.join(
                products, repo_bindings.c.product_id == products.c.id
            ).join(teams, products.c.owner_team_id == teams.c.id)
        )
        .where(
            repo_bindings.c.id == row["binding_id"],
            repo_bindings.c.product_id == row["product_id"],
            repo_bindings.c.repository == row["repository"],
            func.lower(repo_bindings.c.provider) == "github",
            teams.c.organization_id == row["organization_id"],
        )
    ).first()
    if binding is None:
        response = {"status": "error", "errorCode": "source-changed"}
    result = response.get("result")
    if response.get("status") == "ok" and isinstance(result, dict):
        values = {
            "status": "completed",
            "result": result,
            "error_code": None,
            "finished_at": now,
        }
    else:
        code = response.get("errorCode")
        allowed = {
            "rate-limited",
            "source-not-found",
            "source-unavailable",
            "source-changed",
            "scanner-failed",
            "timeout",
        }
        code = code if code in allowed else "scanner-failed"
        retry = (
            code in {"timeout", "source-unavailable", "scanner-failed"}
            and row["attempts"] < MAX_ATTEMPTS
        )
        values = {
            "status": "pending" if retry else "failed",
            "error_code": code,
            "finished_at": None if retry else now,
        }
    db.execute(
        update(public_license_scans)
        .where(public_license_scans.c.id == row["id"])
        .values(
            **values,
            lease_token=None,
            lease_until=None,
        )
    )
    return True


def poll_once(engine, *, execute=_run, clock=_clock, processing=None):
    with engine.begin() as db:
        lease = claim(db, now=clock())
    if lease is None:
        return False
    if processing is not None:
        processing.set()
    try:
        response = execute(lease["repository"], lease["ref"])
        with engine.begin() as db:
            return finish(db, lease, response, now=clock())
    finally:
        if processing is not None:
            processing.clear()


def run_queue(engine, stop, processing):
    while not stop.is_set():
        try:
            worked = poll_once(engine, processing=processing)
        except Exception:
            logger.warning("Public license scan worker unavailable")
            worked = False
        if not worked:
            stop.wait(3)

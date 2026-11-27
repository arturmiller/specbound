"""Run the public license scanner for an authenticated, queued PR head."""

from datetime import datetime, timezone
from functools import partial
from uuid import uuid4

from app.frozen_governance import freeze_product_governance
from app.public_license_assessment import create_public_license_assessment
from app.pull_request_events import parse_pr_event
from app.tables import (
    assessment_jobs,
    github_events,
    public_license_scans,
    repo_bindings,
)
from public_license_worker import LEASE_SECONDS, run_scan
from queue_worker import run_queue
from sqlalchemy import func, insert, select


def _queued_repository(db, lease):
    repository, payload = db.execute(
        select(repo_bindings.c.repository, github_events.c.payload)
        .select_from(
            assessment_jobs.join(
                github_events,
                assessment_jobs.c.delivery_id == github_events.c.delivery_id,
            ).join(repo_bindings, assessment_jobs.c.binding_id == repo_bindings.c.id)
        )
        .where(
            assessment_jobs.c.id == lease["id"],
            repo_bindings.c.product_id == lease["productId"],
            repo_bindings.c.active.is_(True),
            func.lower(repo_bindings.c.provider) == "github",
            github_events.c.organization_id == lease["organizationId"],
            github_events.c.event_type == "pull_request",
        )
    ).one()
    event = parse_pr_event(payload)
    if (
        event is None
        or event["repository"].lower() != repository.lower()
        or event["pr_id"] != lease["pullRequestId"]
        or event["number"] != lease["pullRequestNumber"]
        or event["head"] != lease["headSha"]
    ):
        raise ValueError("PR job no longer matches its signed delivery")
    return repository


def prepare_pr_license_scan(
    engine, lease, *, execute=run_scan, clock=lambda: datetime.now(timezone.utc)
):
    with engine.begin() as db:
        repository = _queued_repository(db, lease)
        governance = freeze_product_governance(
            db, lease["organizationId"], lease["productId"]
        )
    job = {
        "id": str(uuid4()),
        "organization_id": lease["organizationId"],
        "product_id": lease["productId"],
        "binding_id": lease["bindingId"],
        "repository": repository,
        "ref": lease["headSha"],
        "governance_context": governance,
    }
    started = clock()
    response = execute(repository, job["ref"])
    result = response.get("result")
    valid = (
        response["status"] == "ok"
        and isinstance(result, dict)
        and result.get("sourceRevision") == job["ref"]
    )
    error = None
    if not valid:
        error = (
            "revision-mismatch"
            if response["status"] == "ok"
            else response.get("errorCode", "scanner-failed")
        )
        result = {
            "sourceCoverage": "UNKNOWN",
            "coverage": "UNKNOWN",
            "reason": error,
            "files": [],
            "unsupportedFiles": [],
            "packages": [],
        }

    def persist(db):
        if _queued_repository(db, lease) != repository:
            raise ValueError("Repository changed during scan")
        now = clock()
        snapshot_id = create_public_license_assessment(
            db, job, result, now=now, pull_request_number=lease["pullRequestNumber"]
        )
        db.execute(
            insert(public_license_scans).values(
                **job,
                assessment_id=snapshot_id,
                created_at=started,
                finished_at=now,
                attempts=lease["attempts"],
                status="failed" if error else "completed",
                error_code=error,
                result=result,
            )
        )
        return snapshot_id

    return persist


def run_pr_license_queue(engine, organization_id, stop):
    run_queue(
        engine,
        organization_id,
        partial(prepare_pr_license_scan, engine),
        stop,
        lease_seconds=LEASE_SECONDS,
    )

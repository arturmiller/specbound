"""Deliver completed job summaries with transactional retry and PR serialization."""

import logging
from datetime import timedelta

from sqlalchemy import func, or_, select, text, update

from app.pr_comment import upsert_comment
from app.pull_request_events import parse_pr_event
from app.tables import (
    assessment_jobs,
    assessment_snapshots,
    github_events,
    repo_bindings,
)

logger = logging.getLogger(__name__)


def publish_once(engine, organization_id, source_factory, portal_url, *, clock):
    with engine.begin() as db:
        job = (
            db.execute(
                select(assessment_jobs)
                .where(
                    assessment_jobs.c.organization_id == organization_id,
                    assessment_jobs.c.status == "completed",
                    assessment_jobs.c.comment_processed_at.is_(None),
                    or_(
                        assessment_jobs.c.comment_retry_at.is_(None),
                        assessment_jobs.c.comment_retry_at <= clock(),
                    ),
                )
                .order_by(assessment_jobs.c.created_at, assessment_jobs.c.id)
                .with_for_update(skip_locked=True)
                .limit(1)
            )
            .mappings()
            .one_or_none()
        )
        if job is None:
            return False
        binding = (
            db.execute(
                select(repo_bindings)
                .where(
                    repo_bindings.c.id == job["binding_id"],
                    repo_bindings.c.product_id == job["product_id"],
                    func.lower(repo_bindings.c.provider) == "github",
                )
                .with_for_update()
            )
            .mappings()
            .one_or_none()
        )
        if binding is None:
            db.execute(
                update(assessment_jobs)
                .where(assessment_jobs.c.id == job["id"])
                .values(comment_processed_at=clock())
            )
            return True
        event_payload = db.execute(
            select(github_events.c.payload).where(
                github_events.c.delivery_id == job["delivery_id"],
                github_events.c.organization_id == organization_id,
            )
        ).scalar_one()
        try:
            event = parse_pr_event(event_payload)
        except ValueError:
            event = None
        if (
            event is None
            or event["repository"].lower() != binding["repository"].lower()
            or event["pr_id"] != job["pull_request_id"]
            or event["number"] != job["pull_request_number"]
            or event["head"] != job["head_sha"]
        ):
            db.execute(
                update(assessment_jobs)
                .where(assessment_jobs.c.id == job["id"])
                .values(comment_processed_at=clock())
            )
            return True
        snapshot = (
            db.execute(
                select(assessment_snapshots).where(
                    assessment_snapshots.c.id == job["result_snapshot_id"],
                    assessment_snapshots.c.organization_id == organization_id,
                    assessment_snapshots.c.product_id == job["product_id"],
                    assessment_snapshots.c.binding_id == job["binding_id"],
                    assessment_snapshots.c.context == "pull_request",
                    assessment_snapshots.c.pull_request_number
                    == job["pull_request_number"],
                    assessment_snapshots.c.git_sha == job["head_sha"],
                )
            )
            .mappings()
            .one()
        )
        # Serialize multiple workers and bindings for the same repository and PR.
        db.execute(
            text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"),
            {
                "key": binding["repository"].lower()
                + "#"
                + str(job["pull_request_number"])
            },
        )
        try:
            bindings = db.execute(
                select(func.count())
                .select_from(repo_bindings)
                .where(
                    func.lower(repo_bindings.c.provider) == "github",
                    func.lower(repo_bindings.c.repository)
                    == binding["repository"].lower(),
                )
            ).scalar_one()
            if bindings != 1:
                raise ValueError("Repository binding is ambiguous")
            source = source_factory(binding["repository"])
            try:
                upsert_comment(
                    source,
                    job["pull_request_number"],
                    job["head_sha"],
                    snapshot["counts"],
                    portal_url,
                    snapshot["id"],
                )
            finally:
                source.close()
        except Exception:
            logger.warning("PR comment delivery failed; retry scheduled")
            db.execute(
                update(assessment_jobs)
                .where(assessment_jobs.c.id == job["id"])
                .values(comment_retry_at=clock() + timedelta(seconds=30))
            )
            return True
        # Obsolete heads are deliberately processed without publishing.
        db.execute(
            update(assessment_jobs)
            .where(assessment_jobs.c.id == job["id"])
            .values(comment_processed_at=clock(), comment_retry_at=None)
        )
        return True

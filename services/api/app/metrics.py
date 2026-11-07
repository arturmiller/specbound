"""Local aggregate queue metrics without tenant identifiers or payload data."""

from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.engine import Connection

from app.tables import assessment_jobs

STATES = ("pending", "running", "completed", "dead")


def render_metrics(db: Connection, *, now: datetime):
    if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("A timezone-aware clock is required")
    counts = dict.fromkeys(STATES, 0)
    for state, count in db.execute(
        select(assessment_jobs.c.status, func.count()).group_by(
            assessment_jobs.c.status
        )
    ):
        if state in counts:
            counts[state] = count
    oldest = db.execute(
        select(func.min(assessment_jobs.c.created_at)).where(
            assessment_jobs.c.status == "pending"
        )
    ).scalar_one()
    if oldest is None:
        lag = 0.0
    else:
        if oldest.tzinfo is None:
            oldest = oldest.replace(tzinfo=timezone.utc)
        lag = max(0.0, (now.astimezone(timezone.utc) - oldest).total_seconds())
    lines = [
        "# HELP specbound_jobs Number of assessment jobs by state.",
        "# TYPE specbound_jobs gauge",
    ]
    lines.extend(
        f'specbound_jobs{{status="{state}"}} {counts[state]}' for state in STATES
    )
    lines.extend(
        [
            "# HELP specbound_oldest_pending_job_seconds Age of the oldest pending job.",
            "# TYPE specbound_oldest_pending_job_seconds gauge",
            f"specbound_oldest_pending_job_seconds {lag:.3f}",
        ]
    )
    return "\n".join(lines) + "\n"

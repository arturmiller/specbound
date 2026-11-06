from uuid import uuid4

from sqlalchemy import insert
from sqlalchemy.engine import Connection

from app.tables import audit_events


def record_agent_event(
    db: Connection,
    *,
    organization_id: str,
    actor_id: str,
    action: str,
    target_id: str,
    team_id: str | None = None,
    details: dict | None = None,
) -> None:
    db.execute(
        insert(audit_events).values(
            id=str(uuid4()),
            organization_id=organization_id,
            actor_id=actor_id,
            action=action,
            target_id=target_id,
            team_id=team_id,
            details=details or {},
        )
    )

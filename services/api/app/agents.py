"""Organization-scoped agent records and audited lifecycle."""

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, StringConstraints
from sqlalchemy import delete, insert, select, update
from sqlalchemy.engine import Connection

from app.audit import record_agent_event
from app.authorization import organization_access
from app.database import get_connection
from app.identity import get_current_principal
from app.tables import (
    agent_credentials,
    agents,
    audit_events,
    members,
    organizations,
    principals,
    teams,
)

router = APIRouter(dependencies=[Depends(get_current_principal)])
Db = Annotated[Connection, Depends(get_connection, scope="function")]
Principal = Annotated[str, Depends(get_current_principal)]
Name = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)
]


class AgentInput(BaseModel):
    name: Name


def lock_agent(db: Connection, organization_id: str, agent_id: str):
    agent = (
        db.execute(
            select(agents)
            .where(
                agents.c.organization_id == organization_id,
                agents.c.principal_id == agent_id,
            )
            .with_for_update()
        )
        .mappings()
        .one_or_none()
    )
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent


def _response(row):
    return {
        "id": row["principal_id"],
        "kind": "agent",
        "organizationId": row["organization_id"],
        "name": row["name"],
    }


def human_owner(db: Connection, organization_id: str, principal: str):
    organization_access(db, organization_id, principal, write=True)
    kind = db.execute(
        select(principals.c.kind).where(principals.c.id == principal)
    ).scalar_one_or_none()
    if kind != "user":
        raise HTTPException(
            status_code=403, detail="A human organization owner is required"
        )


@router.post(
    "/organizations/{organization_id}/agents/{agent_id}/credentials", status_code=201
)
def create_credential(
    organization_id: str,
    agent_id: str,
    principal: Principal,
    db: Db,
    response: Response,
):
    human_owner(db, organization_id, principal)
    lock_agent(db, organization_id, agent_id)
    credential_id = str(uuid4())
    token = "sba_" + secrets.token_urlsafe(32)
    expires = datetime.now(timezone.utc) + timedelta(hours=1)
    db.execute(
        insert(agent_credentials).values(
            id=credential_id,
            agent_id=agent_id,
            token_hash=hashlib.sha256(token.encode("ascii")).hexdigest(),
            expires_at=expires,
        )
    )
    record_agent_event(
        db,
        organization_id=organization_id,
        actor_id=principal,
        action="agent.credential.created",
        target_id=agent_id,
        details={"credentialId": credential_id},
    )
    response.headers["Cache-Control"] = "no-store"
    return {"id": credential_id, "token": token, "expiresAt": expires}


@router.get("/organizations/{organization_id}/agents/{agent_id}/credentials")
def list_credentials(
    organization_id: str,
    agent_id: str,
    principal: Principal,
    db: Db,
    response: Response,
):
    human_owner(db, organization_id, principal)
    lock_agent(db, organization_id, agent_id)
    rows = db.execute(
        select(
            agent_credentials.c.id,
            agent_credentials.c.expires_at,
            agent_credentials.c.revoked_at,
        )
        .where(agent_credentials.c.agent_id == agent_id)
        .order_by(agent_credentials.c.expires_at.desc(), agent_credentials.c.id)
    ).mappings()
    response.headers["Cache-Control"] = "no-store"
    return [
        {
            "id": row["id"],
            "expiresAt": row["expires_at"],
            "revokedAt": row["revoked_at"],
        }
        for row in rows
    ]


@router.delete(
    "/organizations/{organization_id}/agents/{agent_id}/credentials/{credential_id}",
    status_code=204,
)
def revoke_credential(
    organization_id: str,
    agent_id: str,
    credential_id: str,
    principal: Principal,
    db: Db,
):
    human_owner(db, organization_id, principal)
    lock_agent(db, organization_id, agent_id)
    updated = db.execute(
        update(agent_credentials)
        .where(
            agent_credentials.c.id == credential_id,
            agent_credentials.c.agent_id == agent_id,
            agent_credentials.c.revoked_at.is_(None),
        )
        .values(revoked_at=datetime.now(timezone.utc))
        .returning(agent_credentials.c.id)
    ).scalar_one_or_none()
    if updated is None:
        raise HTTPException(status_code=404, detail="Credential not found")
    record_agent_event(
        db,
        organization_id=organization_id,
        actor_id=principal,
        action="agent.credential.revoked",
        target_id=agent_id,
        details={"credentialId": credential_id},
    )


@router.post(
    "/organizations/{organization_id}/agents", status_code=status.HTTP_201_CREATED
)
def create_agent(organization_id: str, data: AgentInput, principal: Principal, db: Db):
    organization_access(db, organization_id, principal, write=True)
    locked = db.execute(
        select(organizations.c.id)
        .where(organizations.c.id == organization_id)
        .with_for_update()
    ).first()
    if locked is None:
        raise HTTPException(status_code=404, detail="Organization not found")
    agent_id = f"agent:{uuid4()}"
    db.execute(
        insert(principals).values(id=agent_id, kind="agent", issuer=None, subject=None)
    )
    row = (
        db.execute(
            insert(agents)
            .values(
                principal_id=agent_id, organization_id=organization_id, name=data.name
            )
            .returning(agents)
        )
        .mappings()
        .one()
    )
    record_agent_event(
        db,
        organization_id=organization_id,
        actor_id=principal,
        action="agent.created",
        target_id=agent_id,
        details={"name": data.name},
    )
    return _response(row)


@router.get("/organizations/{organization_id}/agents")
def list_agents(organization_id: str, principal: Principal, db: Db):
    organization_access(db, organization_id, principal, write=True)
    rows = db.execute(
        select(agents)
        .where(agents.c.organization_id == organization_id)
        .order_by(agents.c.principal_id)
    ).mappings()
    return [_response(row) for row in rows]


@router.get("/organizations/{organization_id}/agents/{agent_id}")
def get_agent(organization_id: str, agent_id: str, principal: Principal, db: Db):
    organization_access(db, organization_id, principal, write=True)
    return _response(lock_agent(db, organization_id, agent_id))


@router.patch("/organizations/{organization_id}/agents/{agent_id}")
def update_agent(
    organization_id: str, agent_id: str, data: AgentInput, principal: Principal, db: Db
):
    organization_access(db, organization_id, principal, write=True)
    old = lock_agent(db, organization_id, agent_id)
    row = (
        db.execute(
            update(agents)
            .where(agents.c.principal_id == agent_id)
            .values(name=data.name)
            .returning(agents)
        )
        .mappings()
        .one()
    )
    record_agent_event(
        db,
        organization_id=organization_id,
        actor_id=principal,
        action="agent.updated",
        target_id=agent_id,
        details={"oldName": old["name"], "newName": data.name},
    )
    return _response(row)


@router.delete(
    "/organizations/{organization_id}/agents/{agent_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_agent(organization_id: str, agent_id: str, principal: Principal, db: Db):
    organization_access(db, organization_id, principal, write=True)
    agent = lock_agent(db, organization_id, agent_id)
    memberships = (
        db.execute(
            select(
                members.c.id, members.c.team_id, members.c.role, teams.c.organization_id
            )
            .select_from(members.join(teams, members.c.team_id == teams.c.id))
            .where(members.c.principal_id == agent_id)
        )
        .mappings()
        .all()
    )
    if any(member["organization_id"] != organization_id for member in memberships):
        raise HTTPException(
            status_code=409, detail="Agent has memberships outside its organization"
        )
    for member in memberships:
        db.execute(delete(members).where(members.c.id == member["id"]))
        record_agent_event(
            db,
            organization_id=organization_id,
            actor_id=principal,
            action="agent.membership.deleted",
            target_id=agent_id,
            team_id=member["team_id"],
            details={"role": member["role"]},
        )
    db.execute(delete(agents).where(agents.c.principal_id == agent_id))
    db.execute(
        delete(principals).where(
            principals.c.id == agent_id, principals.c.kind == "agent"
        )
    )
    record_agent_event(
        db,
        organization_id=organization_id,
        actor_id=principal,
        action="agent.deleted",
        target_id=agent_id,
        details={"name": agent["name"]},
    )


@router.get("/organizations/{organization_id}/audit-events")
def list_audit_events(organization_id: str, principal: Principal, db: Db):
    organization_access(db, organization_id, principal, write=True)
    rows = db.execute(
        select(audit_events)
        .where(audit_events.c.organization_id == organization_id)
        .order_by(audit_events.c.occurred_at, audit_events.c.id)
    ).mappings()
    return [
        {
            "id": row["id"],
            "actorId": row["actor_id"],
            "action": row["action"],
            "targetId": row["target_id"],
            "teamId": row["team_id"],
            "details": row["details"],
            "occurredAt": row["occurred_at"],
        }
        for row in rows
    ]

"""Central role policy and scoped resource authorization."""

from fastapi import HTTPException
from sqlalchemy import and_, exists, select
from sqlalchemy.engine import Connection

from app.tables import members, organizations, teams

ROLE_ACTIONS = {
    "viewer": frozenset({"read"}),
    "maintainer": frozenset({"read", "edit"}),
    "admin": frozenset({"read", "edit", "manage"}),
}


def role_allows(role: str | None, action: str) -> bool:
    return action in ROLE_ACTIONS.get(role, frozenset())


def _forbidden():
    raise HTTPException(status_code=403, detail="Insufficient permission")


def organization_access(
    db: Connection, organization_id: str, principal: str, *, write: bool
):
    org = (
        db.execute(select(organizations).where(organizations.c.id == organization_id))
        .mappings()
        .one_or_none()
    )
    if org is None:
        raise HTTPException(status_code=404, detail="Not found")
    if org["owner_principal_id"] == principal:
        return org
    if not write:
        member = db.execute(
            select(members.c.id)
            .select_from(members.join(teams, members.c.team_id == teams.c.id))
            .where(
                teams.c.organization_id == organization_id,
                members.c.principal_id == principal,
            )
            .limit(1)
        ).first()
        if member:
            return org
    _forbidden()


def team_access(db: Connection, team_id: str, principal: str, action: str):
    team = (
        db.execute(select(teams).where(teams.c.id == team_id)).mappings().one_or_none()
    )
    if team is None:
        raise HTTPException(status_code=404, detail="Not found")
    org = (
        db.execute(
            select(organizations).where(organizations.c.id == team["organization_id"])
        )
        .mappings()
        .one()
    )
    if org["owner_principal_id"] == principal:
        return team
    role = db.execute(
        select(members.c.role).where(
            members.c.team_id == team_id, members.c.principal_id == principal
        )
    ).scalar_one_or_none()
    if not role_allows(role, action):
        _forbidden()
    return team


def visible_organizations(db: Connection, principal: str):
    is_member = exists(
        select(members.c.id)
        .select_from(members.join(teams, members.c.team_id == teams.c.id))
        .where(
            teams.c.organization_id == organizations.c.id,
            members.c.principal_id == principal,
        )
    )
    return db.execute(
        select(organizations)
        .where((organizations.c.owner_principal_id == principal) | is_member)
        .order_by(organizations.c.id)
    ).mappings()


def visible_teams(db: Connection, organization_id: str, principal: str):
    org = organization_access(db, organization_id, principal, write=False)
    query = select(teams).where(teams.c.organization_id == organization_id)
    if org["owner_principal_id"] != principal:
        is_member = exists(
            select(members.c.id).where(
                and_(
                    members.c.team_id == teams.c.id, members.c.principal_id == principal
                )
            )
        )
        query = query.where(is_member)
    return db.execute(query.order_by(teams.c.id)).mappings()

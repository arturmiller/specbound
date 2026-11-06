"""Organization and team CRUD; identity is fail-closed until OIDC is available."""

from typing import Annotated, Literal
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, StringConstraints
from sqlalchemy import Column, MetaData, String, Table, delete, insert, select, update
from sqlalchemy.engine import Connection
from sqlalchemy.exc import IntegrityError

from app.database import get_connection
from app.identity import get_current_principal

metadata = MetaData()
organizations = Table(
    "organizations",
    metadata,
    Column("id", String),
    Column("name", String),
    Column("owner_principal_id", String),
)
teams = Table(
    "teams",
    metadata,
    Column("id", String),
    Column("organization_id", String),
    Column("name", String),
)
members = Table(
    "team_members",
    metadata,
    Column("id", String),
    Column("team_id", String),
    Column("principal_id", String),
    Column("role", String),
)

NonBlank = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)
]
Role = Literal["admin", "maintainer", "viewer"]


class NameInput(BaseModel):
    name: NonBlank


class MemberInput(BaseModel):
    principalId: NonBlank
    role: Role


class MemberRoleInput(BaseModel):
    role: Role


router = APIRouter(dependencies=[Depends(get_current_principal)])
Db = Annotated[Connection, Depends(get_connection)]
Principal = Annotated[str, Depends(get_current_principal)]


def _required(db: Connection, table: Table, item_id: str):
    item = (
        db.execute(select(table).where(table.c.id == item_id)).mappings().one_or_none()
    )
    if item is None:
        raise HTTPException(status_code=404, detail="Not found")
    return item


def _organization(item):
    return {
        "id": item["id"],
        "name": item["name"],
        "ownerPrincipalId": item["owner_principal_id"],
    }


def _team(item):
    return {
        "id": item["id"],
        "organizationId": item["organization_id"],
        "name": item["name"],
    }


def _member(item):
    return {
        "id": item["id"],
        "teamId": item["team_id"],
        "principalId": item["principal_id"],
        "role": item["role"],
    }


@router.post("/organizations", status_code=status.HTTP_201_CREATED)
def create_organization(data: NameInput, principal: Principal, db: Db):
    item = (
        db.execute(
            insert(organizations)
            .values(id=str(uuid4()), name=data.name, owner_principal_id=principal)
            .returning(organizations)
        )
        .mappings()
        .one()
    )
    return _organization(item)


@router.get("/organizations")
def list_organizations(db: Db):
    return [
        _organization(row)
        for row in db.execute(
            select(organizations).order_by(organizations.c.id)
        ).mappings()
    ]


@router.get("/organizations/{organization_id}")
def get_organization(organization_id: str, db: Db):
    return _organization(_required(db, organizations, organization_id))


@router.patch("/organizations/{organization_id}")
def update_organization(organization_id: str, data: NameInput, db: Db):
    _required(db, organizations, organization_id)
    row = (
        db.execute(
            update(organizations)
            .where(organizations.c.id == organization_id)
            .values(name=data.name)
            .returning(organizations)
        )
        .mappings()
        .one()
    )
    return _organization(row)


@router.delete(
    "/organizations/{organization_id}", status_code=status.HTTP_204_NO_CONTENT
)
def delete_organization(organization_id: str, db: Db):
    _required(db, organizations, organization_id)
    db.execute(delete(organizations).where(organizations.c.id == organization_id))


@router.post(
    "/organizations/{organization_id}/teams", status_code=status.HTTP_201_CREATED
)
def create_team(organization_id: str, data: NameInput, db: Db):
    _required(db, organizations, organization_id)
    row = (
        db.execute(
            insert(teams)
            .values(id=str(uuid4()), organization_id=organization_id, name=data.name)
            .returning(teams)
        )
        .mappings()
        .one()
    )
    return _team(row)


@router.get("/organizations/{organization_id}/teams")
def list_teams(organization_id: str, db: Db):
    _required(db, organizations, organization_id)
    rows = db.execute(
        select(teams)
        .where(teams.c.organization_id == organization_id)
        .order_by(teams.c.id)
    ).mappings()
    return [_team(row) for row in rows]


@router.get("/teams/{team_id}")
def get_team(team_id: str, db: Db):
    return _team(_required(db, teams, team_id))


@router.patch("/teams/{team_id}")
def update_team(team_id: str, data: NameInput, db: Db):
    _required(db, teams, team_id)
    row = (
        db.execute(
            update(teams)
            .where(teams.c.id == team_id)
            .values(name=data.name)
            .returning(teams)
        )
        .mappings()
        .one()
    )
    return _team(row)


@router.delete("/teams/{team_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_team(team_id: str, db: Db):
    _required(db, teams, team_id)
    db.execute(delete(teams).where(teams.c.id == team_id))


@router.post("/teams/{team_id}/members", status_code=status.HTTP_201_CREATED)
def create_member(team_id: str, data: MemberInput, db: Db):
    _required(db, teams, team_id)
    try:
        row = (
            db.execute(
                insert(members)
                .values(
                    id=str(uuid4()),
                    team_id=team_id,
                    principal_id=data.principalId,
                    role=data.role,
                )
                .returning(members)
            )
            .mappings()
            .one()
        )
    except IntegrityError as exc:
        raise HTTPException(
            status_code=409, detail="Membership already exists"
        ) from exc
    return _member(row)


@router.get("/teams/{team_id}/members")
def list_members(team_id: str, db: Db):
    _required(db, teams, team_id)
    rows = db.execute(
        select(members).where(members.c.team_id == team_id).order_by(members.c.id)
    ).mappings()
    return [_member(row) for row in rows]


@router.get("/teams/{team_id}/members/{member_id}")
def get_member(team_id: str, member_id: str, db: Db):
    member = _required(db, members, member_id)
    if member["team_id"] != team_id:
        raise HTTPException(status_code=404, detail="Not found")
    return _member(member)


@router.patch("/teams/{team_id}/members/{member_id}")
def update_member(team_id: str, member_id: str, data: MemberRoleInput, db: Db):
    get_member(team_id, member_id, db)
    row = (
        db.execute(
            update(members)
            .where(members.c.id == member_id)
            .values(role=data.role)
            .returning(members)
        )
        .mappings()
        .one()
    )
    return _member(row)


@router.delete(
    "/teams/{team_id}/members/{member_id}", status_code=status.HTTP_204_NO_CONTENT
)
def delete_member(team_id: str, member_id: str, db: Db):
    get_member(team_id, member_id, db)
    db.execute(delete(members).where(members.c.id == member_id))

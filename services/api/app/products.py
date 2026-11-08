"""Team-owned products and unverified repository bindings."""

from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, StringConstraints, model_validator
from sqlalchemy import delete, insert, select, update
from sqlalchemy.engine import Connection
from sqlalchemy.exc import IntegrityError

from app.authorization import organization_access, team_access, visible_teams
from app.database import get_connection
from app.identity import get_current_principal
from app.tables import organizations, products, repo_bindings, teams

NonBlank = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)
]
Db = Annotated[Connection, Depends(get_connection, scope="function")]
Principal = Annotated[str, Depends(get_current_principal)]
router = APIRouter(dependencies=[Depends(get_current_principal)])


class ProductCreate(BaseModel):
    name: NonBlank
    ownerTeamId: NonBlank


class ProductUpdate(BaseModel):
    name: NonBlank | None = None
    ownerTeamId: NonBlank | None = None

    @model_validator(mode="after")
    def require_changes(self):
        if not self.model_fields_set or any(
            getattr(self, field) is None for field in self.model_fields_set
        ):
            raise ValueError("Supply non-null product changes")
        return self


class RepoInput(BaseModel):
    provider: NonBlank
    repository: NonBlank


def _lock_org(db: Connection, org_id: str):
    if not db.execute(
        select(organizations.c.id).where(organizations.c.id == org_id).with_for_update()
    ).first():
        raise HTTPException(status_code=404, detail="Not found")


def _lock_team(db: Connection, team_id: str):
    if not db.execute(
        select(teams.c.id).where(teams.c.id == team_id).with_for_update()
    ).first():
        raise HTTPException(status_code=404, detail="Not found")


def _product(
    db: Connection, product_id: str, principal: str, action: str, *, lock=False
):
    query = select(products).where(products.c.id == product_id)
    if lock:
        query = query.with_for_update()
    item = db.execute(query).mappings().one_or_none()
    if item is None:
        raise HTTPException(status_code=404, detail="Not found")
    team = team_access(db, item["owner_team_id"], principal, action)
    return item, team


def _serialize(item, org_id):
    return {
        "id": item["id"],
        "name": item["name"],
        "ownerTeamId": item["owner_team_id"],
        "organizationId": org_id,
    }


def _binding(item):
    return {
        "id": item["id"],
        "productId": item["product_id"],
        "provider": item["provider"],
        "repository": item["repository"],
    }


@router.post(
    "/organizations/{organization_id}/products", status_code=status.HTTP_201_CREATED
)
def create_product(
    organization_id: str, data: ProductCreate, principal: Principal, db: Db
):
    organization_access(db, organization_id, principal, write=False)
    _lock_org(db, organization_id)
    _lock_team(db, data.ownerTeamId)
    team = team_access(db, data.ownerTeamId, principal, "edit")
    if team["organization_id"] != organization_id:
        raise HTTPException(
            status_code=422, detail="Owner team must belong to the organization"
        )
    item = (
        db.execute(
            insert(products)
            .values(id=str(uuid4()), name=data.name, owner_team_id=data.ownerTeamId)
            .returning(products)
        )
        .mappings()
        .one()
    )
    return _serialize(item, organization_id)


@router.get("/organizations/{organization_id}/products")
def list_products(organization_id: str, principal: Principal, db: Db):
    team_ids = [team["id"] for team in visible_teams(db, organization_id, principal)]
    rows = db.execute(
        select(products)
        .where(products.c.owner_team_id.in_(team_ids))
        .order_by(products.c.id)
    ).mappings()
    return [_serialize(item, organization_id) for item in rows]


@router.get("/products/{product_id}")
def get_product(product_id: str, principal: Principal, db: Db):
    item, team = _product(db, product_id, principal, "read")
    return _serialize(item, team["organization_id"])


@router.patch("/products/{product_id}")
def update_product(product_id: str, data: ProductUpdate, principal: Principal, db: Db):
    item, team = _product(db, product_id, principal, "edit")
    _lock_org(db, team["organization_id"])
    item, team = _product(db, product_id, principal, "edit", lock=True)
    changes = {}
    if data.name is not None:
        changes["name"] = data.name
    if data.ownerTeamId is not None:
        _lock_team(db, data.ownerTeamId)
        new_team = team_access(db, data.ownerTeamId, principal, "edit")
        if new_team["organization_id"] != team["organization_id"]:
            raise HTTPException(
                status_code=422, detail="Owner team must belong to the organization"
            )
        changes["owner_team_id"] = data.ownerTeamId
    updated = (
        db.execute(
            update(products)
            .where(products.c.id == product_id)
            .values(**changes)
            .returning(products)
        )
        .mappings()
        .one()
    )
    return _serialize(updated, team["organization_id"])


@router.delete("/products/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_product(product_id: str, principal: Principal, db: Db):
    _product(db, product_id, principal, "edit", lock=True)
    db.execute(delete(repo_bindings).where(repo_bindings.c.product_id == product_id))
    db.execute(delete(products).where(products.c.id == product_id))


@router.get("/products/{product_id}/repositories")
def list_repositories(product_id: str, principal: Principal, db: Db):
    _product(db, product_id, principal, "read")
    return [
        _binding(row)
        for row in db.execute(
            select(repo_bindings)
            .where(repo_bindings.c.product_id == product_id)
            .order_by(repo_bindings.c.id)
        ).mappings()
    ]


@router.post("/products/{product_id}/repositories", status_code=status.HTTP_201_CREATED)
def create_repository(product_id: str, data: RepoInput, principal: Principal, db: Db):
    _product(db, product_id, principal, "edit", lock=True)
    try:
        row = (
            db.execute(
                insert(repo_bindings)
                .values(
                    id=str(uuid4()),
                    product_id=product_id,
                    provider=data.provider,
                    repository=data.repository,
                )
                .returning(repo_bindings)
            )
            .mappings()
            .one()
        )
    except IntegrityError as exc:
        raise HTTPException(
            status_code=409, detail="Repository binding already exists"
        ) from exc
    return _binding(row)


@router.get("/products/{product_id}/repositories/{binding_id}")
def get_repository(product_id: str, binding_id: str, principal: Principal, db: Db):
    _product(db, product_id, principal, "read")
    row = (
        db.execute(
            select(repo_bindings).where(
                repo_bindings.c.product_id == product_id,
                repo_bindings.c.id == binding_id,
            )
        )
        .mappings()
        .one_or_none()
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Not found")
    return _binding(row)


@router.patch("/products/{product_id}/repositories/{binding_id}")
def update_repository(
    product_id: str, binding_id: str, data: RepoInput, principal: Principal, db: Db
):
    _product(db, product_id, principal, "edit", lock=True)
    try:
        row = (
            db.execute(
                update(repo_bindings)
                .where(
                    repo_bindings.c.product_id == product_id,
                    repo_bindings.c.id == binding_id,
                )
                .values(provider=data.provider, repository=data.repository)
                .returning(repo_bindings)
            )
            .mappings()
            .one_or_none()
        )
    except IntegrityError as exc:
        raise HTTPException(
            status_code=409, detail="Repository binding already exists"
        ) from exc
    if row is None:
        raise HTTPException(status_code=404, detail="Not found")
    return _binding(row)


@router.delete(
    "/products/{product_id}/repositories/{binding_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_repository(product_id: str, binding_id: str, principal: Principal, db: Db):
    _product(db, product_id, principal, "edit", lock=True)
    result = db.execute(
        delete(repo_bindings).where(
            repo_bindings.c.product_id == product_id, repo_bindings.c.id == binding_id
        )
    )
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Not found")

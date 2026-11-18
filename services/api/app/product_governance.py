"""Bind actual product sources to an explicit, registered profile version."""

import copy
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import insert, select, update

from app.authorization import team_access
from app.manifest_io import read_yaml
from app.manifest_source import checked_manifest_path, content_digest
from app.resource_contracts import HERE, validate
from app.tables import product_governance, products, repo_bindings, resource_documents
from app.workspace import configured_workspace


def load_product(snapshot, manifest_path):
    checked_manifest_path(manifest_path)
    document = read_yaml(snapshot.files, manifest_path)
    validate(document, HERE / "product.schema.json")
    repositories = document["spec"]["repositories"]
    names = [item["repository"].lower() for item in repositories]
    if len(set(names)) != len(names) or any(len(name) > 200 for name in names):
        raise ValueError("Duplicate or oversized product repository")
    return {
        **document["metadata"],
        "document": document,
        "resolved": {
            "repositories": repositories,
            "profile": document["spec"]["profile"],
        },
        "dependencies": [manifest_path],
        "contentDigest": content_digest({"product": snapshot.files[manifest_path]}),
    }


def resolve_product(db, organization_id, loaded, principal):
    workspace = configured_workspace(db)
    if workspace["organizationId"] != organization_id:
        raise HTTPException(
            status_code=403, detail="Product source is outside the configured workspace"
        )
    team_access(db, workspace["defaultOwnerTeamId"], principal, "edit")
    reference = loaded["resolved"]["profile"]
    profiles = (
        db.execute(
            select(resource_documents).where(
                resource_documents.c.organization_id == organization_id,
                resource_documents.c.kind == "Profile",
                resource_documents.c.resource_id == reference["id"],
                resource_documents.c.resource_version == reference["version"],
            )
        )
        .mappings()
        .all()
    )
    if not profiles:
        raise ValueError("Referenced profile version must be registered first")
    if len({profile["content_digest"] for profile in profiles}) != 1:
        raise ValueError("Referenced profile version is ambiguous")
    profile = sorted(profiles, key=lambda item: item["revision_id"])[0]
    current = (
        db.execute(
            select(product_governance).where(
                product_governance.c.organization_id == organization_id,
                product_governance.c.resource_id == loaded["id"],
            )
        )
        .mappings()
        .one_or_none()
    )
    if current:
        team = db.execute(
            select(products.c.owner_team_id).where(
                products.c.id == current["product_id"]
            )
        ).scalar_one()
        team_access(db, team, principal, "edit")
    loaded["resolved"].update(
        productId=current["product_id"] if current else str(uuid4()),
        ownerTeamId=team if current else workspace["defaultOwnerTeamId"],
        profile={
            "resourceId": profile["resource_id"],
            "version": profile["resource_version"],
            "name": profile["name"],
            "revisionId": profile["revision_id"],
            "contentDigest": profile["content_digest"],
        },
        groups=copy.deepcopy(profile["resolved"]["groups"]),
        controls=copy.deepcopy(profile["resolved"]["controls"]),
        selectedControlIds=copy.deepcopy(profile["resolved"]["selectedControlIds"]),
        catalog=copy.deepcopy(profile["resolved"]["catalog"]),
    )
    loaded["contentDigest"] = content_digest(
        {
            "product": loaded["contentDigest"].encode(),
            "profile": profile["content_digest"].encode(),
        }
    )
    return current


def attach_product(
    db, organization_id, revision_id, loaded, current, *, adopt_from=None
):
    if current:
        if current["revision_id"] == revision_id:
            return
        if adopt_from is None or current["revision_id"] != adopt_from["revision_id"]:
            raise HTTPException(
                status_code=409,
                detail="Product already has a manifest; adopting a new revision requires explicit review",
            )
        product_id = current["product_id"]
        # Shares the enqueue lock: every scan sees one complete configuration.
        db.execute(
            select(products.c.id).where(products.c.id == product_id).with_for_update()
        ).one()
        db.execute(
            update(product_governance)
            .where(product_governance.c.product_id == product_id)
            .values(
                revision_id=revision_id,
                profile_revision_id=loaded["resolved"]["profile"]["revisionId"],
            )
        )
        db.execute(
            update(products)
            .where(products.c.id == product_id)
            .values(name=loaded["name"])
        )
        synchronize_repositories(db, product_id, loaded["resolved"]["repositories"])
        return
    product_id = loaded["resolved"]["productId"]
    db.execute(
        insert(products).values(
            id=product_id,
            name=loaded["name"],
            owner_team_id=loaded["resolved"]["ownerTeamId"],
        )
    )
    db.execute(
        insert(product_governance).values(
            product_id=product_id,
            organization_id=organization_id,
            resource_id=loaded["id"],
            revision_id=revision_id,
            profile_revision_id=loaded["resolved"]["profile"]["revisionId"],
        )
    )
    for repository in loaded["resolved"]["repositories"]:
        db.execute(
            insert(repo_bindings).values(
                id=str(uuid4()), product_id=product_id, **repository
            )
        )


def synchronize_repositories(db, product_id, repositories):
    """Retire removed sources without deleting IDs used by historical scans."""
    existing = (
        db.execute(
            select(repo_bindings).where(repo_bindings.c.product_id == product_id)
        )
        .mappings()
        .all()
    )
    db.execute(
        update(repo_bindings)
        .where(repo_bindings.c.product_id == product_id)
        .values(active=False)
    )
    for repository in repositories:
        previous = next(
            (
                row
                for row in existing
                if row["provider"] == repository["provider"]
                and row["repository"] == repository["repository"]
            ),
            None,
        )
        if previous:
            db.execute(
                update(repo_bindings)
                .where(repo_bindings.c.id == previous["id"])
                .values(active=True)
            )
        else:
            db.execute(
                insert(repo_bindings).values(
                    id=str(uuid4()), product_id=product_id, active=True, **repository
                )
            )


def require_unmanaged_product(db, product_id):
    if db.execute(
        select(product_governance.c.product_id).where(
            product_governance.c.product_id == product_id
        )
    ).first():
        raise HTTPException(
            status_code=409,
            detail="Product configuration is managed in its Git manifest; publish and adopt a new revision",
        )

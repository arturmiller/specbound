"""Review and explicitly adopt immutable resource revisions, preserving history."""

import copy
from typing import Annotated, Callable, Literal

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, ConfigDict, StringConstraints
from sqlalchemy import select
from sqlalchemy.engine import Connection

from app.audit import record_event
from app.authorization import organization_access
from app.database import get_connection
from app.git_source import GitSource
from app.identity import get_current_principal
from app.pack_catalog import github_source_factory
from app.pack_revisions import _lock_org
from app.resource_registry import get_resource, import_resource
from app.resource_store import resources_query, review_digest
from app.tables import product_governance, resource_documents

router = APIRouter()
Db = Annotated[Connection, Depends(get_connection, scope="function")]
Principal = Annotated[str, Depends(get_current_principal)]
SourceFactory = Annotated[Callable[[str], GitSource], Depends(github_source_factory)]
Ref = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)
]


class RevisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ref: Ref | None = None
    refType: Literal["branch", "tag", "commit"] | None = None


class AdoptionRequest(RevisionRequest):
    commit: Annotated[
        str, StringConstraints(pattern=r"^(?:[0-9a-f]{40}|[0-9a-f]{64})$")
    ]
    reviewDigest: Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]


def revision_config(db, organization_id, revision_id, principal, request):
    organization_access(db, organization_id, principal, write=True)
    before = get_resource(organization_id, revision_id, principal, db)
    if before["state"] == "archived":
        raise HTTPException(
            status_code=409,
            detail="Catalog is archived; restore it before checking revisions",
        )
    row = (
        db.execute(
            resources_query(organization_id).where(
                resource_documents.c.revision_id == revision_id
            )
        )
        .mappings()
        .one()
    )
    if row["kind"] == "Product":
        current = db.execute(
            select(product_governance.c.revision_id).where(
                product_governance.c.product_id == row["resolved"]["productId"],
                product_governance.c.organization_id == organization_id,
            )
        ).scalar_one_or_none()
        if current != revision_id:
            raise HTTPException(
                status_code=409,
                detail="This product revision is historical; review the current revision",
            )
    config = copy.deepcopy(row["source_config"])
    for key in ("ref", "refType"):
        value = getattr(request, key)
        if value is not None:
            config["spec"][key] = value
    return row, before, config


def differences(before, after, path=""):
    """Deterministic structural differences; never a simulated assessment."""
    if before == after:
        return []
    if isinstance(before, dict) and isinstance(after, dict):
        changes = []
        for key in sorted(set(before) | set(after)):
            pointer = path + "/" + str(key).replace("~", "~0").replace("/", "~1")
            if key not in before or key not in after:
                changes.append(
                    {
                        "path": pointer,
                        "before": before.get(key),
                        "after": after.get(key),
                        "change": "added" if key in after else "removed",
                    }
                )
            else:
                changes.extend(differences(before[key], after[key], pointer))
        return changes
    return [
        {"path": path or "/", "before": before, "after": after, "change": "changed"}
    ]


def pinned_references(db, organization_id, revision_id):
    references = []
    for row in db.execute(resources_query(organization_id)).mappings():
        if any(
            row["resolved"].get(field, {}).get("revisionId") == revision_id
            for field in ("catalog", "profile")
        ):
            references.append(
                {
                    "revisionId": row["revision_id"],
                    "resourceType": row["kind"],
                    "name": row["name"],
                    "version": row["resource_version"],
                    "productId": row["resolved"].get("productId"),
                }
            )
    current = (
        db.execute(
            select(
                product_governance.c.product_id, product_governance.c.revision_id
            ).where(
                product_governance.c.organization_id == organization_id,
                (product_governance.c.profile_revision_id == revision_id)
                | (product_governance.c.revision_id == revision_id),
            )
        )
        .mappings()
        .all()
    )
    return {
        "resources": references,
        "currentProducts": [
            {"productId": row["product_id"], "revisionId": row["revision_id"]}
            for row in current
        ],
    }


@router.post("/organizations/{organization_id}/resources/{revision_id}/check")
def check_revision(
    organization_id: str,
    revision_id: str,
    data: RevisionRequest,
    principal: Principal,
    db: Db,
    factory: SourceFactory,
):
    _, before, config = revision_config(
        db, organization_id, revision_id, principal, data
    )
    candidate = import_resource(
        organization_id,
        config,
        Response(),
        principal,
        db,
        factory,
        preview=True,
        discover_version=True,
    )
    return {
        "before": before,
        "candidate": candidate,
        "reviewDigest": review_digest(candidate),
        "validation": {"structure": "valid", "references": "valid"},
        "changes": differences(
            {"manifest": before["manifest"], "resolved": before["resolved"]},
            {"manifest": candidate["manifest"], "resolved": candidate["resolved"]},
        ),
        "references": pinned_references(db, organization_id, revision_id),
        "assessmentImpact": "not_computed",
    }


@router.post(
    "/organizations/{organization_id}/resources/{revision_id}/adopt", status_code=201
)
def adopt_revision(
    organization_id: str,
    revision_id: str,
    data: AdoptionRequest,
    principal: Principal,
    db: Db,
    factory: SourceFactory,
):
    organization_access(db, organization_id, principal, write=True)
    _lock_org(db, organization_id)
    row, before, config = revision_config(
        db, organization_id, revision_id, principal, data
    )
    saved = import_resource(
        organization_id,
        config,
        Response(),
        principal,
        db,
        factory,
        expected_commit=data.commit,
        preview=False,
        discover_version=True,
        adopt_from=row,
        expected_review_digest=data.reviewDigest,
    )
    record_event(
        db,
        organization_id=organization_id,
        actor_id=principal,
        action="resource.revision.adopted",
        target_id=saved["id"],
        details={
            "previousRevisionId": revision_id,
            "revisionId": saved["id"],
            "resourceType": saved["resourceType"],
            "resourceId": saved["resourceId"],
            "previousCommit": before["source"]["commit"],
            "commit": saved["source"]["commit"],
            "reviewDigest": data.reviewDigest,
        },
    )
    return saved


@router.get("/organizations/{organization_id}/resources/{revision_id}/adoptions")
def adoption_history(
    organization_id: str, revision_id: str, principal: Principal, db: Db
):
    from app.tables import audit_events

    get_resource(organization_id, revision_id, principal, db)
    rows = db.execute(
        select(audit_events)
        .where(
            audit_events.c.organization_id == organization_id,
            audit_events.c.action == "resource.revision.adopted",
            (audit_events.c.target_id == revision_id)
            | (audit_events.c.details["previousRevisionId"].as_string() == revision_id),
        )
        .order_by(audit_events.c.occurred_at, audit_events.c.id)
    ).mappings()
    return [
        {
            "id": row["id"],
            "actorId": row["actor_id"],
            "occurredAt": row["occurred_at"],
            "details": row["details"],
        }
        for row in rows
    ]

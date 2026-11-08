"""Authorized catalog of structurally validated, pinned Git packs."""

import os
from typing import Annotated, Callable, Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, StringConstraints
from sqlalchemy import JSON, bindparam, delete, select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.engine import Connection

from app.agents import human_owner
from app.audit import record_agent_event
from app.authorization import organization_access
from app.database import get_connection
from app.git_source import GitSource, GitSourceError
from app.github_source import configured_github_source
from app.governance_pack import load_governance_pack
from app.identity import get_current_principal
from app.manifest_io import ManifestError
from app.pack_revisions import TagMoved, pin_release
from app.provider_pack import load_provider_pack
from app.tables import pack_approvals, pack_catalog, pack_revisions

router = APIRouter(dependencies=[Depends(get_current_principal)])
NonBlank = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)
]


class ConnectPack(BaseModel):
    repository: NonBlank
    tag: NonBlank
    kind: Literal["governance", "provider"]


def github_source_factory() -> Callable[[str], GitSource]:
    return configured_github_source


def _serialize(row):
    return {
        "id": row["id"],
        "organizationId": row["organization_id"],
        "repository": row["repository"],
        "tag": row["tag"],
        "commit": row["commit_sha"],
        "kind": row["kind"],
        "manifest": row["manifest"],
        "controls": row["controls"],
        "capabilities": row["capabilities"],
    }


def _query(organization_id):
    return (
        select(
            pack_revisions,
            pack_catalog.c.kind,
            pack_catalog.c.manifest,
            pack_catalog.c.controls,
            pack_catalog.c.capabilities,
        )
        .select_from(
            pack_revisions.join(
                pack_catalog, pack_catalog.c.revision_id == pack_revisions.c.id
            )
        )
        .where(pack_revisions.c.organization_id == organization_id)
    )


@router.get("/organizations/{organization_id}/packs/{revision_id}/approval")
def get_approval(
    organization_id: str,
    revision_id: str,
    principal: Annotated[str, Depends(get_current_principal)],
    db: Annotated[Connection, Depends(get_connection, scope="function")],
):
    organization_access(db, organization_id, principal, write=False)
    pack = (
        db.execute(_query(organization_id).where(pack_revisions.c.id == revision_id))
        .mappings()
        .one_or_none()
    )
    if pack is None:
        raise HTTPException(status_code=404, detail="Pack not found")
    approval = (
        db.execute(
            select(pack_approvals).where(
                pack_approvals.c.revision_id == revision_id,
                pack_approvals.c.organization_id == organization_id,
            )
        )
        .mappings()
        .one_or_none()
    )
    return {
        "revisionId": revision_id,
        "approved": approval is not None,
        "approvedBy": approval["approved_by"] if approval else None,
        "approvedAt": approval["approved_at"] if approval else None,
    }


@router.put("/organizations/{organization_id}/packs/{revision_id}/approval")
def approve_pack(
    organization_id: str,
    revision_id: str,
    principal: Annotated[str, Depends(get_current_principal)],
    db: Annotated[Connection, Depends(get_connection, scope="function")],
):
    human_owner(db, organization_id, principal)
    pack = (
        db.execute(_query(organization_id).where(pack_revisions.c.id == revision_id))
        .mappings()
        .one_or_none()
    )
    if pack is None:
        raise HTTPException(status_code=404, detail="Pack not found")
    if pack["kind"] != "governance":
        raise HTTPException(
            status_code=422, detail="Only governance packs can be approved here"
        )
    inserted = db.execute(
        pg_insert(pack_approvals)
        .values(
            revision_id=revision_id,
            organization_id=organization_id,
            repository=pack["repository"],
            approved_by=principal,
        )
        .on_conflict_do_nothing(index_elements=[pack_approvals.c.revision_id])
        .returning(pack_approvals.c.revision_id)
    ).scalar_one_or_none()
    if inserted:
        record_agent_event(
            db,
            organization_id=organization_id,
            actor_id=principal,
            action="governance.approved",
            target_id=revision_id,
            details={"commit": pack["commit_sha"]},
        )
    return get_approval(organization_id, revision_id, principal, db)


@router.delete(
    "/organizations/{organization_id}/packs/{revision_id}/approval", status_code=204
)
def revoke_approval(
    organization_id: str,
    revision_id: str,
    principal: Annotated[str, Depends(get_current_principal)],
    db: Annotated[Connection, Depends(get_connection, scope="function")],
):
    human_owner(db, organization_id, principal)
    removed = db.execute(
        delete(pack_approvals)
        .where(
            pack_approvals.c.revision_id == revision_id,
            pack_approvals.c.organization_id == organization_id,
        )
        .returning(pack_approvals.c.revision_id)
    ).scalar_one_or_none()
    if removed is None:
        raise HTTPException(status_code=404, detail="Approval not found")
    record_agent_event(
        db,
        organization_id=organization_id,
        actor_id=principal,
        action="governance.approval.revoked",
        target_id=revision_id,
    )


@router.get("/organizations/{organization_id}/packs")
def list_packs(
    organization_id: str,
    principal: Annotated[str, Depends(get_current_principal)],
    db: Annotated[Connection, Depends(get_connection, scope="function")],
):
    organization_access(db, organization_id, principal, write=False)
    return [
        _serialize(row)
        for row in db.execute(
            _query(organization_id).order_by(pack_revisions.c.id)
        ).mappings()
    ]


@router.get("/organizations/{organization_id}/packs/{revision_id}")
def get_pack(
    organization_id: str,
    revision_id: str,
    principal: Annotated[str, Depends(get_current_principal)],
    db: Annotated[Connection, Depends(get_connection, scope="function")],
):
    organization_access(db, organization_id, principal, write=False)
    row = (
        db.execute(_query(organization_id).where(pack_revisions.c.id == revision_id))
        .mappings()
        .one_or_none()
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Pack not found")
    return _serialize(row)


@router.post(
    "/organizations/{organization_id}/packs", status_code=status.HTTP_201_CREATED
)
def connect_pack(
    organization_id: str,
    data: ConnectPack,
    principal: Annotated[str, Depends(get_current_principal)],
    db: Annotated[Connection, Depends(get_connection, scope="function")],
    factory: Annotated[Callable[[str], GitSource], Depends(github_source_factory)],
):
    organization_access(db, organization_id, principal, write=True)
    configured_org = os.environ.get("GITHUB_ORGANIZATION_ID", "")
    if not configured_org:
        raise HTTPException(
            status_code=503, detail="GitHub organization is not configured"
        )
    if configured_org != organization_id:
        raise HTTPException(
            status_code=403, detail="GitHub App is not available for this organization"
        )
    try:
        source = factory(data.repository)
        try:
            commit = source.resolve_tag(data.tag)
            previous = db.execute(
                select(pack_revisions.c.commit_sha).where(
                    pack_revisions.c.organization_id == organization_id,
                    pack_revisions.c.repository == data.repository,
                    pack_revisions.c.tag == data.tag,
                )
            ).scalar_one_or_none()
            if previous is not None and previous != commit:
                raise TagMoved(previous, commit)
            snapshot = source.fetch(commit)
            if snapshot.commit != commit:
                raise ValueError("Snapshot did not match resolved commit")
            loaded = (
                load_governance_pack(snapshot)
                if data.kind == "governance"
                else load_provider_pack(snapshot)
            )
            revision = pin_release(
                db, organization_id, data.repository, data.tag, source
            )
            if revision["commit"] != snapshot.commit:
                raise TagMoved(snapshot.commit, revision["commit"])
        finally:
            source.close()
        controls = loaded.get("controls", [])
        capabilities = (
            loaded["manifest"].get("requiresCapabilities", [])
            if data.kind == "governance"
            else loaded["manifest"]["capabilities"]
        )
        insert = text(
            "INSERT INTO pack_catalog (revision_id, kind, manifest, controls, capabilities) VALUES (:id, :kind, :manifest, :controls, :capabilities) ON CONFLICT (revision_id) DO NOTHING"
        ).bindparams(
            bindparam("manifest", type_=JSON),
            bindparam("controls", type_=JSON),
            bindparam("capabilities", type_=JSON),
        )
        db.execute(
            insert,
            {
                "id": revision["id"],
                "kind": data.kind,
                "manifest": loaded["manifest"],
                "controls": controls,
                "capabilities": capabilities,
            },
        )
        row = (
            db.execute(
                _query(organization_id).where(pack_revisions.c.id == revision["id"])
            )
            .mappings()
            .one()
        )
        if row["kind"] != data.kind:
            raise HTTPException(
                status_code=409,
                detail="Pinned release already belongs to another pack kind",
            )
        return _serialize(row)
    except TagMoved as exc:
        raise HTTPException(
            status_code=409, detail="Tag moved from its pinned commit"
        ) from exc
    except (ManifestError, ValueError) as exc:
        raise HTTPException(
            status_code=422, detail="Invalid pack manifest or repository"
        ) from exc
    except GitSourceError as exc:
        raise HTTPException(status_code=503, detail="Git source unavailable") from exc

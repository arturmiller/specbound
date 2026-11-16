"""Authorized catalog of structurally validated, pinned Git packs."""

import os
from typing import Annotated, Callable, Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, StringConstraints, model_validator
from sqlalchemy import JSON, bindparam, delete, select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.engine import Connection

from app.agents import human_owner
from app.audit import record_agent_event
from app.authorization import organization_access
from app.database import get_connection
from app.git_source import GitSource, GitSourceError
from app.github_source import configured_github_source
from app.identity import get_current_principal
from app.manifest_io import ManifestError, validator
from app.manifest_source import checked_manifest_path, load_pack_at, snapshot_for_ref
from app.pack_revisions import TagMoved, pin_release
from app.resource_contracts import HERE, ROOT, read
from app.tables import pack_approvals, pack_catalog, pack_revisions

router = APIRouter(dependencies=[Depends(get_current_principal)])
schemas_router = APIRouter()
NonBlank = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)
]


class ConnectPack(BaseModel):
    model_config = ConfigDict(extra="forbid")
    repository: NonBlank
    tag: NonBlank | None = None
    ref: NonBlank | None = None
    refType: Literal["tag", "branch", "commit"] = "tag"
    manifestPath: str | None = None
    kind: Literal["governance", "provider"]

    @model_validator(mode="after")
    def source_fields(self):
        if bool(self.tag) == bool(self.ref) or (self.tag and self.refType != "tag"):
            raise ValueError("Supply one tag or one explicit ref")
        self.manifestPath = checked_manifest_path(
            self.manifestPath
            or ("pack.yaml" if self.kind == "governance" else "provider.yaml")
        )
        return self


def github_source_factory() -> Callable[[str], GitSource]:
    return configured_github_source


def require_github_organization(organization_id):
    configured_org = os.environ.get("GITHUB_ORGANIZATION_ID", "")
    if not configured_org:
        raise HTTPException(
            status_code=503, detail="GitHub organization is not configured"
        )
    if configured_org != organization_id:
        raise HTTPException(
            status_code=403, detail="GitHub App is not available for this organization"
        )


def _serialize(row):
    return {
        "id": row["id"],
        "organizationId": row["organization_id"],
        "repository": row["repository"],
        "tag": row["tag"],
        "commit": row["commit_sha"],
        "ref": row["tag"],
        "refType": row["ref_kind"],
        "manifestPath": row["manifest_path"],
        "schemaUrl": f"/api/contracts/{row['kind']}-pack",
        "manifestUrl": f"https://github.com/{row['repository']}/blob/{row['commit_sha']}/{row['manifest_path']}",
        "commitUrl": f"https://github.com/{row['repository']}/commit/{row['commit_sha']}",
        "validationStatus": "structure_validated",
        "contentDigest": row["content_digest"],
        "schemas": row["schemas"] or {},
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
            pack_catalog.c.content_digest,
            pack_catalog.c.schemas,
        )
        .select_from(
            pack_revisions.join(
                pack_catalog, pack_catalog.c.revision_id == pack_revisions.c.id
            )
        )
        .where(pack_revisions.c.organization_id == organization_id)
    )


@schemas_router.get("/contracts/{contract}")
def get_contract(
    contract: Literal[
        "governance-pack", "provider-pack", "oscal-catalog", "resource-source"
    ],
):
    if contract == "oscal-catalog":
        return read(ROOT / "oscal/1.2.3/oscal_catalog_schema.json")
    if contract == "resource-source":
        return read(HERE / "resource-source.schema.json")
    filename = (
        "governance-pack.schema.json"
        if contract == "governance-pack"
        else "evidence-provider-pack.schema.json"
    )
    return validator(filename).schema


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
    require_github_organization(organization_id)
    try:
        source = factory(data.repository)
        try:
            ref = data.ref or data.tag
            snapshot = snapshot_for_ref(source, data.repository, ref, data.refType)
            loaded = load_pack_at(snapshot, data.manifestPath, data.kind)
            revision = pin_release(
                db,
                organization_id,
                data.repository,
                ref,
                source,
                manifest_path=data.manifestPath,
                ref_kind=data.refType,
                resolved_commit=snapshot.commit,
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
        for existing in db.execute(
            _query(organization_id).where(pack_catalog.c.kind == data.kind)
        ).mappings():
            metadata = existing["manifest"]["metadata"]
            if (
                metadata["id"] == loaded["manifest"]["metadata"]["id"]
                and metadata["version"] == loaded["manifest"]["metadata"]["version"]
                and (
                    (
                        existing["content_digest"] is None
                        and existing["id"] != revision["id"]
                    )
                    or (
                        existing["content_digest"] is not None
                        and existing["content_digest"] != loaded["contentDigest"]
                    )
                    or (
                        existing["id"] == revision["id"]
                        and (
                            existing["manifest"] != loaded["manifest"]
                            or existing["controls"] != controls
                        )
                    )
                )
            ):
                raise HTTPException(
                    status_code=409,
                    detail="Resource ID/version already identifies different content; publish a new version",
                )
        insert = text(
            "INSERT INTO pack_catalog (revision_id, kind, manifest, controls, capabilities, content_digest, schemas) VALUES (:id, :kind, :manifest, :controls, :capabilities, :digest, :schemas) ON CONFLICT (revision_id) DO NOTHING"
        ).bindparams(
            bindparam("manifest", type_=JSON),
            bindparam("controls", type_=JSON),
            bindparam("capabilities", type_=JSON),
            bindparam("schemas", type_=JSON),
        )
        db.execute(
            insert,
            {
                "id": revision["id"],
                "kind": data.kind,
                "manifest": loaded["manifest"],
                "controls": controls,
                "capabilities": capabilities,
                "digest": loaded["contentDigest"],
                "schemas": loaded.get("schemas", {}),
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

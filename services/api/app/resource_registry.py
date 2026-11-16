"""Authorized, revision-pinned resource registration and read-only previews."""

import re
from typing import Annotated, Callable
from urllib.parse import quote

from fastapi import APIRouter, Depends, Header, HTTPException, Response
from jsonschema import ValidationError
from sqlalchemy import insert, select
from sqlalchemy.engine import Connection

from app.authorization import organization_access
from app.database import get_connection
from app.git_source import GitSource, GitSourceError
from app.identity import get_current_principal
from app.manifest_io import ManifestError
from app.manifest_source import snapshot_for_ref
from app.oscal_resources import load_catalog, load_profile
from app.pack_catalog import github_source_factory, require_github_organization
from app.pack_revisions import TagMoved, pin_release
from app.resource_contracts import HERE, validate
from app.tables import pack_revisions, resource_documents

router = APIRouter(dependencies=[Depends(get_current_principal)])


def _query(organization_id):
    return (
        select(pack_revisions, resource_documents)
        .select_from(
            pack_revisions.join(
                resource_documents,
                resource_documents.c.revision_id == pack_revisions.c.id,
            )
        )
        .where(
            pack_revisions.c.organization_id == organization_id,
            resource_documents.c.organization_id == organization_id,
        )
    )


def _source(repository, ref, ref_kind, commit, path, dependencies, kind):
    base = f"https://github.com/{repository}"
    return {
        "repository": repository,
        "ref": ref,
        "refType": ref_kind,
        "commit": commit,
        "manifestPath": path,
        "manifestUrl": f"{base}/blob/{commit}/{quote(path, safe='/')}",
        "commitUrl": f"{base}/commit/{commit}",
        "schemaUrl": "/api/contracts/oscal-catalog"
        if kind == "Catalog"
        else "/api/contracts/oscal-profile",
        "files": [
            {"path": name, "url": f"{base}/blob/{commit}/{quote(name, safe='/')}"}
            for name in dependencies
        ],
    }


def _serialize(row):
    return {
        "id": row["revision_id"],
        "organizationId": row["organization_id"],
        "resourceType": row["kind"],
        "resourceId": row["resource_id"],
        "version": row["resource_version"],
        "name": row["name"],
        "state": "registered",
        "validationStatus": "structure_validated",
        "source": _source(
            row["repository"],
            row["tag"],
            row["ref_kind"],
            row["commit_sha"],
            row["manifest_path"],
            row["dependencies"],
            row["kind"],
        ),
        "manifest": row["document"],
        "resolved": row["resolved"],
        "contentDigest": row["content_digest"],
    }


@router.get("/organizations/{organization_id}/resources")
def list_resources(
    organization_id: str,
    principal: Annotated[str, Depends(get_current_principal)],
    db: Annotated[Connection, Depends(get_connection, scope="function")],
):
    organization_access(db, organization_id, principal, write=False)
    return [
        _serialize(row)
        for row in db.execute(
            _query(organization_id).order_by(
                resource_documents.c.name,
                resource_documents.c.resource_version,
                resource_documents.c.revision_id,
            )
        ).mappings()
    ]


@router.get("/organizations/{organization_id}/resources/{revision_id}")
def get_resource(
    organization_id: str,
    revision_id: str,
    principal: Annotated[str, Depends(get_current_principal)],
    db: Annotated[Connection, Depends(get_connection, scope="function")],
):
    organization_access(db, organization_id, principal, write=False)
    row = (
        db.execute(
            _query(organization_id).where(
                resource_documents.c.revision_id == revision_id
            )
        )
        .mappings()
        .one_or_none()
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Resource revision not found")
    return _serialize(row)


@router.post("/organizations/{organization_id}/resources", status_code=201)
def register_resource(
    organization_id: str,
    data: dict,
    response: Response,
    principal: Annotated[str, Depends(get_current_principal)],
    db: Annotated[Connection, Depends(get_connection, scope="function")],
    factory: Annotated[Callable[[str], GitSource], Depends(github_source_factory)],
    expected_commit: Annotated[str | None, Header(alias="X-Expected-Commit")] = None,
    preview: bool = False,
):
    organization_access(db, organization_id, principal, write=True)
    require_github_organization(organization_id)
    if expected_commit is not None and not re.fullmatch(
        r"(?:[0-9a-f]{40}|[0-9a-f]{64})", expected_commit
    ):
        raise HTTPException(
            status_code=422, detail="Expected commit must be a full Git object ID"
        )
    try:
        validate(data, HERE / "resource-source.schema.json")
        config = data["spec"]
        kind = config["resourceType"]
        loaders = {"Catalog": load_catalog, "Profile": load_profile}
        if kind not in loaders:
            raise ValueError(
                "Only native Catalog and Profile registration are supported here"
            )
        source = factory(config["repository"])
        try:
            ref_kind = config.get("refType", "branch")
            snapshot = snapshot_for_ref(
                source, config["repository"], config["ref"], ref_kind
            )
            if expected_commit is not None and snapshot.commit != expected_commit:
                raise HTTPException(
                    status_code=409,
                    detail="Source changed after preview; check the new revision first",
                )
            loaded = loaders[kind](snapshot, config["manifestPath"])
        finally:
            source.close()
        if config["expected"] != {"id": loaded["id"], "version": loaded["version"]}:
            raise ValueError(
                "Manifest identity/version differs from the registered reference"
            )
        if kind == "Profile":
            catalog = loaded["resolved"]["catalog"]
            matches = (
                db.execute(
                    _query(organization_id).where(
                        resource_documents.c.kind == "Catalog",
                        resource_documents.c.resource_id == catalog["resourceId"],
                        resource_documents.c.resource_version == catalog["version"],
                    )
                )
                .mappings()
                .all()
            )
            if not matches:
                raise ValueError("Referenced catalog version must be registered first")
            if {row["content_digest"] for row in matches} != {catalog["contentDigest"]}:
                raise ValueError(
                    "Referenced catalog version is ambiguous or has different content"
                )
            matches.sort(
                key=lambda row: (
                    not (
                        row["repository"] == config["repository"]
                        and row["manifest_path"] == catalog["manifestPath"]
                        and row["commit_sha"] == snapshot.commit
                    ),
                    row["revision_id"],
                )
            )
            catalog["revisionId"] = matches[0]["revision_id"]
        if preview:
            response.status_code = 200
            return {
                "id": None,
                "organizationId": organization_id,
                "resourceType": kind,
                "resourceId": loaded["id"],
                "version": loaded["version"],
                "name": loaded["name"],
                "state": "preview",
                "validationStatus": "structure_validated",
                "source": _source(
                    config["repository"],
                    config["ref"],
                    ref_kind,
                    snapshot.commit,
                    config["manifestPath"],
                    loaded["dependencies"],
                    kind,
                ),
                "manifest": loaded["document"],
                "resolved": loaded["resolved"],
                "contentDigest": loaded["contentDigest"],
            }
        revision = pin_release(
            db,
            organization_id,
            config["repository"],
            config["ref"],
            source,
            manifest_path=config["manifestPath"],
            ref_kind=ref_kind,
            resolved_commit=snapshot.commit,
        )
        previous = (
            db.execute(
                select(resource_documents).where(
                    resource_documents.c.organization_id == organization_id,
                    resource_documents.c.kind == kind,
                    resource_documents.c.resource_id == loaded["id"],
                    resource_documents.c.resource_version == loaded["version"],
                )
            )
            .mappings()
            .all()
        )
        if any(row["content_digest"] != loaded["contentDigest"] for row in previous):
            raise HTTPException(
                status_code=409,
                detail="Resource ID/version already identifies different content; publish a new version",
            )
        existing = (
            db.execute(
                select(resource_documents).where(
                    resource_documents.c.revision_id == revision["id"]
                )
            )
            .mappings()
            .one_or_none()
        )
        if existing is None:
            db.execute(
                insert(resource_documents).values(
                    revision_id=revision["id"],
                    organization_id=organization_id,
                    kind=kind,
                    resource_id=loaded["id"],
                    resource_version=loaded["version"],
                    name=loaded["name"],
                    source_config=data,
                    document=loaded["document"],
                    resolved=loaded["resolved"],
                    dependencies=loaded["dependencies"],
                    content_digest=loaded["contentDigest"],
                )
            )
        elif (
            existing["kind"] != kind
            or existing["content_digest"] != loaded["contentDigest"]
        ):
            raise HTTPException(
                status_code=409,
                detail="Source revision already identifies another resource",
            )
        return get_resource(organization_id, revision["id"], principal, db)
    except TagMoved as exc:
        raise HTTPException(
            status_code=409, detail="Tag moved from its pinned commit"
        ) from exc
    except ValidationError as exc:
        pointer = "/".join(str(part) for part in exc.absolute_path)[:200] or "document"
        raise HTTPException(
            status_code=422, detail=f"Schema mismatch at {pointer}"
        ) from exc
    except (ManifestError, ValueError, RecursionError) as exc:
        raise HTTPException(
            status_code=422,
            detail="Invalid or unsupported resource manifest, binding or reference: "
            + str(exc)[:200],
        ) from exc
    except GitSourceError as exc:
        raise HTTPException(status_code=503, detail="Git source unavailable") from exc

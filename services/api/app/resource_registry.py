"""Authorized, revision-pinned resource registration and read-only previews."""

import copy
import re
from typing import Annotated, Callable

from fastapi import APIRouter, Depends, Header, HTTPException, Response
from jsonschema import ValidationError
from sqlalchemy import insert, select
from sqlalchemy.engine import Connection

from app.authorization import organization_access, team_access, visible_teams
from app.database import get_connection
from app.evidence_packs import load_evidence_pack
from app.git_source import GitSource, GitSourceError
from app.identity import get_current_principal
from app.manifest_io import ManifestError
from app.manifest_source import snapshot_for_ref
from app.oscal_resources import load_catalog, load_profile
from app.pack_catalog import (
    github_source_factory,
    persist_loaded_pack,
    require_github_organization,
)
from app.pack_revisions import TagMoved, _lock_org, pin_release
from app.product_governance import attach_product, load_product, resolve_product
from app.resource_contracts import HERE, validate
from app.resource_store import (
    resource_source,
    resources_query,
    review_digest,
    serialize_resource,
)
from app.tables import pack_revisions, products, resource_documents

router = APIRouter(dependencies=[Depends(get_current_principal)])


@router.get("/organizations/{organization_id}/resources")
def list_resources(
    organization_id: str,
    principal: Annotated[str, Depends(get_current_principal)],
    db: Annotated[Connection, Depends(get_connection, scope="function")],
):
    organization_access(db, organization_id, principal, write=False)
    team_ids = [team["id"] for team in visible_teams(db, organization_id, principal)]
    visible_products = select(products.c.id).where(
        products.c.owner_team_id.in_(team_ids)
    )
    return [
        serialize_resource(row)
        for row in db.execute(
            resources_query(organization_id)
            .where(
                (resource_documents.c.kind != "Product")
                | resource_documents.c.resolved["productId"]
                .as_string()
                .in_(visible_products)
            )
            .order_by(
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
            resources_query(organization_id).where(
                resource_documents.c.revision_id == revision_id
            )
        )
        .mappings()
        .one_or_none()
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Resource revision not found")
    if row["kind"] == "Product":
        product = (
            db.execute(
                select(products).where(
                    products.c.id == row["resolved"].get("productId")
                )
            )
            .mappings()
            .one_or_none()
        )
        if product is None:
            raise HTTPException(
                status_code=404, detail="Product resource is unavailable"
            )
        team_access(db, product["owner_team_id"], principal, "read")
    return serialize_resource(row)


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
    return import_resource(
        organization_id,
        data,
        response,
        principal,
        db,
        factory,
        expected_commit=expected_commit,
        preview=preview,
    )


def import_resource(
    organization_id,
    data,
    response,
    principal,
    db,
    factory,
    *,
    expected_commit=None,
    preview=False,
    adopt_from=None,
    discover_version=False,
    expected_review_digest=None,
):
    data = copy.deepcopy(data)
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
        loaders = {
            "Catalog": load_catalog,
            "Profile": load_profile,
            "Product": load_product,
            "EvidenceProviderPack": load_evidence_pack,
        }
        if kind not in loaders:
            raise ValueError("Unsupported resource type")
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
        if discover_version:
            config["expected"]["version"] = loaded["version"]
        if config["expected"] != {"id": loaded["id"], "version": loaded["version"]}:
            raise ValueError(
                "Manifest identity/version differs from the registered reference"
            )
        if not preview:
            _lock_org(db, organization_id)
        current_product = (
            resolve_product(db, organization_id, loaded, principal)
            if kind == "Product"
            else None
        )
        if kind == "Profile":
            catalog = loaded["resolved"]["catalog"]
            matches = (
                db.execute(
                    resources_query(organization_id).where(
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
        if ref_kind == "tag":
            pinned = db.execute(
                select(pack_revisions.c.commit_sha).where(
                    pack_revisions.c.organization_id == organization_id,
                    pack_revisions.c.repository == config["repository"],
                    pack_revisions.c.tag == config["ref"],
                    pack_revisions.c.ref_kind == ref_kind,
                    pack_revisions.c.manifest_path == config["manifestPath"],
                )
            ).scalar_one_or_none()
            if pinned is not None and pinned != snapshot.commit:
                raise TagMoved(pinned, snapshot.commit)
        candidate = {
            "id": None,
            "organizationId": organization_id,
            "resourceType": kind,
            "resourceId": loaded["id"],
            "version": loaded["version"],
            "name": loaded["name"],
            "state": "preview",
            "validationStatus": "structure_validated",
            "source": resource_source(
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
        if (
            expected_review_digest is not None
            and review_digest(candidate) != expected_review_digest
        ):
            raise HTTPException(
                status_code=409,
                detail="Reviewed configuration or references changed; check again",
            )
        if preview:
            response.status_code = 200
            return candidate
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
        if kind == "EvidenceProviderPack":
            persist_loaded_pack(
                db, organization_id, revision, "provider", loaded["providerPack"]
            )
        if kind == "Product":
            attach_product(
                db,
                organization_id,
                revision["id"],
                loaded,
                current_product,
                adopt_from=adopt_from,
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

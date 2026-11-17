"""Provider source adapter and exact, versioned requirement-to-provider matching."""

from pathlib import PurePosixPath
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.engine import Connection

from app.authorization import organization_access
from app.database import get_connection
from app.identity import get_current_principal
from app.manifest_source import load_pack_at
from app.tables import pack_catalog, pack_revisions, resource_documents

router = APIRouter()


def load_evidence_pack(snapshot, manifest_path):
    loaded = load_pack_at(snapshot, manifest_path, "provider")
    manifest = loaded["manifest"]
    metadata = manifest["metadata"]
    directory = PurePosixPath(manifest_path).parent
    dependencies = [
        manifest_path,
        *[str(directory / path) for path in sorted(loaded["schemas"])],
        *[str(directory / path) for path in manifest.get("tests", [])],
    ]
    return {
        "id": metadata["id"],
        "version": metadata["version"],
        "name": metadata.get("title", metadata["id"]),
        "document": manifest,
        "resolved": {
            "groups": [],
            "controls": [],
            "capabilities": manifest["capabilities"],
            "schemas": loaded["schemas"],
            "runtime": manifest["runtime"],
            "permissions": manifest.get("permissions", {}),
            "executionApproval": "not_available",
        },
        "dependencies": dependencies,
        "contentDigest": loaded["contentDigest"],
        "providerPack": loaded,
    }


def match_capabilities(resources, providers):
    result = []
    for resource in resources:
        for control in resource["controls"]:
            binding = control.get("binding")
            if not binding:
                continue
            required = binding["requiredEvidence"]["capability"]
            identity = required.rsplit("/", 1)[0]
            matching, incompatible = [], []
            for provider in providers:
                offered = {
                    f"{cap['id']}/{cap['version']}" for cap in provider["capabilities"]
                }
                if required in offered:
                    matching.append(provider["revisionId"])
                elif any(cap["id"] == identity for cap in provider["capabilities"]):
                    incompatible.append(provider["revisionId"])
            result.append(
                {
                    **{
                        key: value
                        for key, value in resource.items()
                        if key != "controls"
                    },
                    "controlId": control["id"],
                    "capability": required,
                    "providerRevisionIds": matching,
                    "incompatibleProviderRevisionIds": incompatible,
                    "status": "available"
                    if matching
                    else "incompatible_version"
                    if incompatible
                    else "missing",
                }
            )
    return result


@router.get("/organizations/{organization_id}/evidence-pack-usage")
def get_evidence_pack_usage(
    organization_id: str,
    principal: Annotated[str, Depends(get_current_principal)],
    db: Annotated[Connection, Depends(get_connection, scope="function")],
):
    organization_access(db, organization_id, principal, write=False)
    providers = [
        {
            "revisionId": row["id"],
            "resourceId": row["manifest"]["metadata"]["id"],
            "version": row["manifest"]["metadata"]["version"],
            "name": row["manifest"]["metadata"].get(
                "title", row["manifest"]["metadata"]["id"]
            ),
            "capabilities": row["capabilities"],
            "executionApproval": "not_available",
        }
        for row in db.execute(
            select(
                pack_revisions.c.id,
                pack_catalog.c.manifest,
                pack_catalog.c.capabilities,
            )
            .join(pack_catalog, pack_catalog.c.revision_id == pack_revisions.c.id)
            .where(
                pack_revisions.c.organization_id == organization_id,
                pack_catalog.c.kind == "provider",
            )
            .order_by(pack_revisions.c.id)
        ).mappings()
    ]
    resources = [
        {
            "revisionId": row["revision_id"],
            "resourceType": row["kind"],
            "resourceId": row["resource_id"],
            "version": row["resource_version"],
            "name": row["name"],
            "controls": row["resolved"]["controls"],
        }
        for row in db.execute(
            select(resource_documents)
            .where(
                resource_documents.c.organization_id == organization_id,
                resource_documents.c.kind.in_(("Catalog", "Profile")),
            )
            .order_by(resource_documents.c.revision_id)
        ).mappings()
    ]
    return {
        "providers": providers,
        "controls": match_capabilities(resources, providers),
    }

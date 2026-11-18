"""Read immutable resource documents with their exact source links."""

import hashlib
import json
from urllib.parse import quote

from sqlalchemy import select

from app.tables import pack_revisions, resource_documents


def review_digest(candidate):
    """Fence exactly the configuration, closure and source shown for adoption."""
    payload = {
        key: candidate[key]
        for key in ("source", "manifest", "resolved", "contentDigest")
    }
    return hashlib.sha256(
        json.dumps(
            payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True
        ).encode()
    ).hexdigest()


def resources_query(organization_id):
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


def resource_source(repository, ref, ref_kind, commit, path, dependencies, kind):
    base = f"https://github.com/{repository}"
    return {
        "repository": repository,
        "ref": ref,
        "refType": ref_kind,
        "commit": commit,
        "manifestPath": path,
        "manifestUrl": f"{base}/blob/{commit}/{quote(path, safe='/')}",
        "commitUrl": f"{base}/commit/{commit}",
        "schemaUrl": {
            "Catalog": "/api/contracts/oscal-catalog",
            "Profile": "/api/contracts/oscal-profile",
            "Product": "/api/contracts/product",
            "EvidenceProviderPack": "/api/contracts/provider-pack",
        }[kind],
        "files": [
            {"path": name, "url": f"{base}/blob/{commit}/{quote(name, safe='/')}"}
            for name in dependencies
        ],
    }


def serialize_resource(row):
    return {
        "id": row["revision_id"],
        "organizationId": row["organization_id"],
        "resourceType": row["kind"],
        "resourceId": row["resource_id"],
        "version": row["resource_version"],
        "name": row["name"],
        "state": "archived" if row["archived"] else "registered",
        "validationStatus": "structure_validated",
        "source": resource_source(
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

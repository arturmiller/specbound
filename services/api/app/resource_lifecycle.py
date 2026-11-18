"""Owner-authorized catalog archival without deleting fixed resource references."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import update
from sqlalchemy.engine import Connection

from app.audit import record_event
from app.authorization import organization_access
from app.database import get_connection
from app.identity import get_current_principal
from app.pack_revisions import _lock_org
from app.resource_registry import get_resource
from app.tables import resource_documents

router = APIRouter()
Db = Annotated[Connection, Depends(get_connection, scope="function")]
Principal = Annotated[str, Depends(get_current_principal)]


def set_catalog_archive(db, organization_id, revision_id, principal, *, archived):
    organization_access(db, organization_id, principal, write=True)
    _lock_org(db, organization_id)
    resource = get_resource(organization_id, revision_id, principal, db)
    if resource["resourceType"] != "Catalog":
        raise HTTPException(
            status_code=422, detail="Only catalog archival is supported"
        )
    if (resource["state"] == "archived") != archived:
        db.execute(
            update(resource_documents)
            .where(
                resource_documents.c.organization_id == organization_id,
                resource_documents.c.revision_id == revision_id,
            )
            .values(archived=archived)
        )
        record_event(
            db,
            organization_id=organization_id,
            actor_id=principal,
            action="resource.archived" if archived else "resource.restored",
            target_id=revision_id,
            details={
                "resourceType": "Catalog",
                "resourceId": resource["resourceId"],
                "version": resource["version"],
                "commit": resource["source"]["commit"],
            },
        )
    return get_resource(organization_id, revision_id, principal, db)


@router.delete(
    "/organizations/{organization_id}/resources/{revision_id}", status_code=204
)
def remove_catalog(
    organization_id: str, revision_id: str, principal: Principal, db: Db
):
    set_catalog_archive(db, organization_id, revision_id, principal, archived=True)
    return Response(status_code=204)


@router.post("/organizations/{organization_id}/resources/{revision_id}/restore")
def restore_catalog(
    organization_id: str, revision_id: str, principal: Principal, db: Db
):
    return set_catalog_archive(
        db, organization_id, revision_id, principal, archived=False
    )

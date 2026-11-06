"""Immutable Git tag pins and an internal active-revision pointer."""

import re
from uuid import uuid4

from sqlalchemy import and_, select, text
from sqlalchemy.engine import Connection

from app.git_source import GitSource
from app.tables import organizations, pack_activations, pack_revisions


class TagMoved(Exception):
    def __init__(self, pinned: str, observed: str):
        super().__init__("Tag no longer points to its pinned commit")
        self.pinned = pinned
        self.observed = observed


def _serialize(row):
    return {
        "id": row["id"],
        "organizationId": row["organization_id"],
        "repository": row["repository"],
        "tag": row["tag"],
        "commit": row["commit_sha"],
    }


def _lock_org(db: Connection, organization_id: str):
    if not db.execute(
        select(organizations.c.id)
        .where(organizations.c.id == organization_id)
        .with_for_update()
    ).first():
        raise LookupError("Organization not found")


def _resolve(source: GitSource, repository: str, tag: str):
    if any(
        not isinstance(value, str) or not value.strip() or len(value) > 200
        for value in (repository, tag)
    ):
        raise ValueError("Repository and tag must be nonempty")
    if getattr(source, "repository", repository) != repository:
        raise ValueError("Source repository does not match")
    commit = source.resolve_tag(tag)
    if not isinstance(commit, str) or not re.fullmatch(
        r"(?:[0-9a-f]{40}|[0-9a-f]{64})", commit
    ):
        raise ValueError("Source must resolve a full commit ID")
    return commit


def pin_release(
    db: Connection, organization_id: str, repository: str, tag: str, source: GitSource
):
    commit = _resolve(source, repository, tag)
    _lock_org(db, organization_id)
    db.execute(
        text(
            "INSERT INTO pack_revisions (id, organization_id, repository, tag, commit_sha) VALUES (:id, :org, :repo, :tag, :commit) ON CONFLICT (organization_id, repository, tag) DO NOTHING"
        ),
        {
            "id": str(uuid4()),
            "org": organization_id,
            "repo": repository,
            "tag": tag,
            "commit": commit,
        },
    )
    row = (
        db.execute(
            select(pack_revisions).where(
                pack_revisions.c.organization_id == organization_id,
                pack_revisions.c.repository == repository,
                pack_revisions.c.tag == tag,
            )
        )
        .mappings()
        .one()
    )
    if row["commit_sha"] != commit:
        raise TagMoved(row["commit_sha"], commit)
    return _serialize(row)


def activate_release(
    db: Connection, organization_id: str, revision_id: str, source: GitSource
):
    verify_release(db, organization_id, revision_id, source)
    _lock_org(db, organization_id)
    row = (
        db.execute(
            select(pack_revisions).where(
                pack_revisions.c.organization_id == organization_id,
                pack_revisions.c.id == revision_id,
            )
        )
        .mappings()
        .one_or_none()
    )
    if row is None:
        raise LookupError("Revision not found")
    db.execute(
        text(
            "INSERT INTO pack_activations (organization_id, repository, revision_id) VALUES (:org, :repo, :revision) ON CONFLICT (organization_id, repository) DO UPDATE SET revision_id = excluded.revision_id"
        ),
        {"org": organization_id, "repo": row["repository"], "revision": revision_id},
    )
    return _serialize(row)


def get_active_release(db: Connection, organization_id: str, repository: str):
    row = (
        db.execute(
            select(pack_revisions)
            .select_from(
                pack_revisions.join(
                    pack_activations,
                    and_(
                        pack_activations.c.revision_id == pack_revisions.c.id,
                        pack_activations.c.organization_id
                        == pack_revisions.c.organization_id,
                        pack_activations.c.repository == pack_revisions.c.repository,
                    ),
                )
            )
            .where(
                pack_activations.c.organization_id == organization_id,
                pack_activations.c.repository == repository,
            )
        )
        .mappings()
        .one_or_none()
    )
    return _serialize(row) if row is not None else None


def verify_release(
    db: Connection, organization_id: str, revision_id: str, source: GitSource
):
    row = (
        db.execute(
            select(pack_revisions).where(
                pack_revisions.c.organization_id == organization_id,
                pack_revisions.c.id == revision_id,
            )
        )
        .mappings()
        .one_or_none()
    )
    if row is None:
        raise LookupError("Revision not found")
    observed = _resolve(source, row["repository"], row["tag"])
    if observed != row["commit_sha"]:
        raise TagMoved(row["commit_sha"], observed)
    return _serialize(row)

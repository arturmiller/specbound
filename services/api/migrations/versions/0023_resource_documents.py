"""Retain native governance resources and their resolved, pinned dependencies."""

import sqlalchemy as sa
from alembic import op

revision = "0023_resource_documents"
down_revision = "0022_manifest_sources"
branch_labels = None
depends_on = None


def upgrade():
    op.create_unique_constraint(
        "uq_pack_revision_org_id", "pack_revisions", ["organization_id", "id"]
    )
    op.create_table(
        "resource_documents",
        sa.Column("revision_id", sa.String(36), primary_key=True),
        sa.Column(
            "organization_id",
            sa.String(36),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("kind", sa.String(40), nullable=False),
        sa.Column("resource_id", sa.String(128), nullable=False),
        sa.Column("resource_version", sa.String(128), nullable=False),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("source_config", sa.JSON, nullable=False),
        sa.Column("document", sa.JSON, nullable=False),
        sa.Column("resolved", sa.JSON, nullable=False),
        sa.Column("dependencies", sa.JSON, nullable=False),
        sa.Column("content_digest", sa.String(64), nullable=False),
        sa.ForeignKeyConstraint(
            ["organization_id", "revision_id"],
            ["pack_revisions.organization_id", "pack_revisions.id"],
            ondelete="CASCADE",
        ),
        sa.CheckConstraint(
            "kind IN ('Catalog', 'Profile', 'Product')",
            name="ck_resource_document_kind",
        ),
    )
    op.create_index(
        "ix_resource_identity",
        "resource_documents",
        ["organization_id", "kind", "resource_id", "resource_version"],
    )


def downgrade():
    if (
        op.get_bind()
        .execute(sa.text("SELECT 1 FROM resource_documents LIMIT 1"))
        .first()
    ):
        raise RuntimeError(
            "Cannot discard registered resource documents and provenance"
        )
    op.drop_table("resource_documents")
    op.drop_constraint("uq_pack_revision_org_id", "pack_revisions", type_="unique")

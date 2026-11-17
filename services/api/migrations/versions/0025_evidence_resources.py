"""Allow provider manifests in the shared source registry without replacing v1."""

import sqlalchemy as sa
from alembic import op

revision = "0025_evidence_resources"
down_revision = "0024_product_governance"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_index("ix_resource_identity", table_name="resource_documents")
    op.alter_column(
        "resource_documents",
        "resource_id",
        type_=sa.String(200),
        existing_type=sa.String(128),
    )
    op.alter_column(
        "resource_documents",
        "resource_version",
        type_=sa.Text(),
        existing_type=sa.String(128),
    )
    op.create_index(
        "ix_resource_identity",
        "resource_documents",
        ["organization_id", "kind", "resource_id"],
    )
    op.drop_constraint("ck_resource_document_kind", "resource_documents", type_="check")
    op.create_check_constraint(
        "ck_resource_document_kind",
        "resource_documents",
        "kind IN ('Catalog', 'Profile', 'Product', 'EvidenceProviderPack')",
    )


def downgrade():
    if (
        op.get_bind()
        .execute(
            sa.text(
                "SELECT 1 FROM resource_documents WHERE kind = 'EvidenceProviderPack' LIMIT 1"
            )
        )
        .first()
    ):
        raise RuntimeError("Cannot discard registered Evidence Pack sources")
    op.drop_index("ix_resource_identity", table_name="resource_documents")
    op.alter_column(
        "resource_documents",
        "resource_id",
        type_=sa.String(128),
        existing_type=sa.String(200),
    )
    op.alter_column(
        "resource_documents",
        "resource_version",
        type_=sa.String(128),
        existing_type=sa.Text(),
    )
    op.create_index(
        "ix_resource_identity",
        "resource_documents",
        ["organization_id", "kind", "resource_id", "resource_version"],
    )
    op.drop_constraint("ck_resource_document_kind", "resource_documents", type_="check")
    op.create_check_constraint(
        "ck_resource_document_kind",
        "resource_documents",
        "kind IN ('Catalog', 'Profile', 'Product')",
    )

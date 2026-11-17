"""Explicit current product manifests; existing products stay unassigned."""

import sqlalchemy as sa
from alembic import op

revision = "0024_product_governance"
down_revision = "0023_resource_documents"
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column("products", "name", type_=sa.Text(), existing_type=sa.String(200))
    op.create_unique_constraint(
        "uq_resource_org_revision",
        "resource_documents",
        ["organization_id", "revision_id"],
    )
    op.create_table(
        "product_governance",
        sa.Column(
            "product_id",
            sa.String(36),
            sa.ForeignKey("products.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "organization_id",
            sa.String(36),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("resource_id", sa.String(128), nullable=False),
        sa.Column("revision_id", sa.String(36), nullable=False),
        sa.Column("profile_revision_id", sa.String(36), nullable=False),
        sa.UniqueConstraint(
            "organization_id", "resource_id", name="uq_product_resource_identity"
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "revision_id"],
            ["resource_documents.organization_id", "resource_documents.revision_id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "profile_revision_id"],
            ["resource_documents.organization_id", "resource_documents.revision_id"],
            ondelete="RESTRICT",
        ),
    )


def downgrade():
    db = op.get_bind()
    if (
        db.execute(sa.text("SELECT 1 FROM product_governance LIMIT 1")).first()
        or db.execute(
            sa.text("SELECT 1 FROM products WHERE length(name) > 200 LIMIT 1")
        ).first()
    ):
        raise RuntimeError(
            "Cannot discard explicit product governance or truncate product names"
        )
    op.drop_table("product_governance")
    op.drop_constraint("uq_resource_org_revision", "resource_documents", type_="unique")
    op.alter_column("products", "name", type_=sa.String(200), existing_type=sa.Text())

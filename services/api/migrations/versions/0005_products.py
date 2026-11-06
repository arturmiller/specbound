"""Add team-owned products and repository bindings."""

import sqlalchemy as sa
from alembic import op

revision = "0005_products"
down_revision = "0004_agents_audit"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "products",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column(
            "owner_team_id",
            sa.String(36),
            sa.ForeignKey("teams.id", ondelete="RESTRICT"),
            nullable=False,
        ),
    )
    op.create_index("ix_products_owner_team_id", "products", ["owner_team_id"])
    op.create_table(
        "repo_bindings",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "product_id",
            sa.String(36),
            sa.ForeignKey("products.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("provider", sa.String(200), nullable=False),
        sa.Column("repository", sa.String(200), nullable=False),
        sa.UniqueConstraint(
            "product_id", "provider", "repository", name="uq_product_repository"
        ),
    )
    op.create_index("ix_repo_bindings_product_id", "repo_bindings", ["product_id"])


def downgrade() -> None:
    op.drop_index("ix_repo_bindings_product_id", table_name="repo_bindings")
    op.drop_table("repo_bindings")
    op.drop_index("ix_products_owner_team_id", table_name="products")
    op.drop_table("products")

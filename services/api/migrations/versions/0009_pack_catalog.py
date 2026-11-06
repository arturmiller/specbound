"""Store validated catalog metadata against an immutable revision."""

import sqlalchemy as sa
from alembic import op

revision = "0009_pack_catalog"
down_revision = "0008_pack_revisions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "pack_catalog",
        sa.Column(
            "revision_id",
            sa.String(36),
            sa.ForeignKey("pack_revisions.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("manifest", sa.JSON, nullable=False),
        sa.Column("controls", sa.JSON, nullable=False),
        sa.Column("capabilities", sa.JSON, nullable=False),
        sa.CheckConstraint(
            "kind IN ('governance', 'provider')", name="ck_pack_catalog_kind"
        ),
    )


def downgrade() -> None:
    op.drop_table("pack_catalog")

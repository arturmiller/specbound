"""Hide removed catalog registrations while retaining their immutable history."""

import sqlalchemy as sa
from alembic import op

revision = "0028_catalog_archival"
down_revision = "0027_repository_retirement"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "resource_documents",
        sa.Column("archived", sa.Boolean, nullable=False, server_default=sa.false()),
    )


def downgrade():
    if (
        op.get_bind()
        .execute(sa.text("SELECT 1 FROM resource_documents WHERE archived LIMIT 1"))
        .first()
    ):
        raise RuntimeError("Cannot revive archived catalogs by downgrade")
    op.drop_column("resource_documents", "archived")

"""Retain removed product sources for immutable assessment provenance."""

import sqlalchemy as sa
from alembic import op

revision = "0027_repository_retirement"
down_revision = "0026_frozen_governance"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "repo_bindings",
        sa.Column("active", sa.Boolean, nullable=False, server_default=sa.true()),
    )


def downgrade():
    if (
        op.get_bind()
        .execute(sa.text("SELECT 1 FROM repo_bindings WHERE NOT active LIMIT 1"))
        .first()
    ):
        raise RuntimeError("Cannot revive retired product sources by downgrade")
    op.drop_column("repo_bindings", "active")

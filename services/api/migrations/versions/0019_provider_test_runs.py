"""Store synthetic test requests separately from assessment evidence."""

import sqlalchemy as sa
from alembic import op

revision = "0019_provider_test_runs"
down_revision = "0018_agent_approval"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "provider_test_runs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("pack_revision_id", sa.String(36), sa.ForeignKey("pack_catalog.revision_id", ondelete="CASCADE"), nullable=False),
        sa.Column("pack_commit", sa.String(64), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("status IN ('pending', 'running', 'succeeded', 'failed')", name="ck_provider_test_runs_status"),
    )
    op.create_index("ix_provider_test_runs_org_pack", "provider_test_runs", ["organization_id", "pack_revision_id", "created_at"])


def downgrade() -> None:
    if op.get_bind().execute(sa.text("SELECT count(*) FROM provider_test_runs")).scalar_one():
        raise RuntimeError("Cannot downgrade while provider test runs exist")
    op.drop_index("ix_provider_test_runs_org_pack", table_name="provider_test_runs")
    op.drop_table("provider_test_runs")

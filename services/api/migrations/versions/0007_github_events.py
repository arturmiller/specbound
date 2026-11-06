"""Store verified GitHub webhook deliveries."""

import sqlalchemy as sa
from alembic import op

revision = "0007_github_events"
down_revision = "0006_scanner_coverage"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "github_events",
        sa.Column("delivery_id", sa.String(36), primary_key=True),
        sa.Column("installation_id", sa.String(30), nullable=False),
        sa.Column("organization_id", sa.String(36), nullable=False),
        sa.Column("event_type", sa.String(100), nullable=False),
        sa.Column("payload", sa.JSON, nullable=False),
        sa.Column(
            "received_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_table("github_events")

"""Add short-lived agent credentials and human governance approvals."""

import sqlalchemy as sa
from alembic import op

revision = "0018_agent_approval"
down_revision = "0017_check_delivery"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "agent_credentials",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "agent_id",
            sa.String(200),
            sa.ForeignKey("agents.principal_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
    )
    op.create_table(
        "pack_approvals",
        sa.Column(
            "revision_id",
            sa.String(36),
            sa.ForeignKey("pack_catalog.revision_id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("organization_id", sa.String(36), nullable=False),
        sa.Column("repository", sa.String(200), nullable=False),
        sa.Column("approved_by", sa.String(200), nullable=False),
        sa.Column(
            "approved_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "repository", "revision_id"],
            [
                "pack_revisions.organization_id",
                "pack_revisions.repository",
                "pack_revisions.id",
            ],
            ondelete="CASCADE",
        ),
    )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.execute(sa.text("SELECT count(*) FROM pack_approvals")).scalar_one():
        raise RuntimeError("Cannot downgrade while governance approvals exist")
    if bind.execute(sa.text("SELECT count(*) FROM agent_credentials")).scalar_one():
        raise RuntimeError("Cannot downgrade while agent credentials exist")
    op.drop_table("pack_approvals")
    op.drop_table("agent_credentials")

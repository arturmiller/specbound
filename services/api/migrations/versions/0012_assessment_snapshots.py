"""Store separate immutable PR and baseline assessment snapshots."""

import sqlalchemy as sa
from alembic import op

revision = "0012_assessment_snapshots"
down_revision = "0011_rule_evaluations"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "assessment_snapshots",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "organization_id",
            sa.String(36),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "product_id",
            sa.String(36),
            sa.ForeignKey("products.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "binding_id",
            sa.String(36),
            sa.ForeignKey("repo_bindings.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("context", sa.String(20), nullable=False),
        sa.Column("pull_request_number", sa.Integer, nullable=True),
        sa.Column("environment", sa.String(200), nullable=False),
        sa.Column("git_sha", sa.String(64), nullable=False),
        sa.Column("pack_sha", sa.String(64), nullable=False),
        sa.Column("evaluation_ids", sa.JSON, nullable=False),
        sa.Column("evidence_ids", sa.JSON, nullable=False),
        sa.Column("counts", sa.JSON, nullable=False),
        sa.Column("evaluations", sa.JSON, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "(context = 'pull_request' AND pull_request_number IS NOT NULL AND pull_request_number > 0) OR (context = 'baseline' AND pull_request_number IS NULL)",
            name="ck_assessment_context",
        ),
    )
    op.create_index(
        "ix_assessment_snapshots_product",
        "assessment_snapshots",
        ["organization_id", "product_id", "context", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_assessment_snapshots_product", table_name="assessment_snapshots")
    op.drop_table("assessment_snapshots")

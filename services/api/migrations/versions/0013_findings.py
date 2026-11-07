"""Add stable findings and one history entry per applied snapshot."""

import sqlalchemy as sa
from alembic import op

revision = "0013_findings"
down_revision = "0012_assessment_snapshots"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "findings",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("fingerprint", sa.String(64), nullable=False, unique=True),
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
        sa.Column("subject_id", sa.String(500), nullable=False),
        sa.Column("control_id", sa.String(128), nullable=False),
        sa.Column("status", sa.String(10), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "last_snapshot_id",
            sa.String(36),
            sa.ForeignKey("assessment_snapshots.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.CheckConstraint("status IN ('open', 'resolved')", name="ck_finding_status"),
    )
    op.create_index(
        "ix_findings_product", "findings", ["organization_id", "product_id", "status"]
    )
    op.create_table(
        "finding_history",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "finding_id",
            sa.String(36),
            sa.ForeignKey("findings.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "snapshot_id",
            sa.String(36),
            sa.ForeignKey("assessment_snapshots.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "evaluation_id",
            sa.String(36),
            sa.ForeignKey("rule_evaluations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("outcome", sa.String(20), nullable=False),
        sa.Column("state_after", sa.String(10), nullable=False),
        sa.Column("reason", sa.Text, nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "finding_id", "snapshot_id", name="uq_finding_history_snapshot"
        ),
        sa.CheckConstraint(
            "outcome IN ('PASS', 'FAIL', 'UNKNOWN', 'NOT_APPLICABLE')",
            name="ck_finding_history_outcome",
        ),
        sa.CheckConstraint(
            "state_after IN ('open', 'resolved')", name="ck_finding_history_state"
        ),
    )
    op.create_index(
        "ix_finding_history_finding", "finding_history", ["finding_id", "observed_at"]
    )


def downgrade() -> None:
    op.drop_index("ix_finding_history_finding", table_name="finding_history")
    op.drop_table("finding_history")
    op.drop_index("ix_findings_product", table_name="findings")
    op.drop_table("findings")

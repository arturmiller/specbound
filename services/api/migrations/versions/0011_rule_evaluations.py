"""Persist control outcomes and the inputs needed to understand them."""

import sqlalchemy as sa
from alembic import op

revision = "0011_rule_evaluations"
down_revision = "0010_evidence_records"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "rule_evaluations",
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
        sa.Column("subject_id", sa.String(500), nullable=False),
        sa.Column("environment", sa.String(200), nullable=False),
        sa.Column("target_revision", sa.String(71), nullable=False),
        sa.Column("control_id", sa.String(128), nullable=False),
        sa.Column("governance_revision", sa.String(64), nullable=False),
        sa.Column("scan_id", sa.Integer, nullable=True),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("reason", sa.Text, nullable=False),
        sa.Column("evidence_ids", sa.JSON, nullable=False),
        sa.Column("control", sa.JSON, nullable=False),
        sa.Column("subject", sa.JSON, nullable=False),
        sa.Column("evaluated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('PASS', 'FAIL', 'UNKNOWN', 'NOT_APPLICABLE')",
            name="ck_rule_evaluation_status",
        ),
    )
    op.create_index(
        "ix_rule_evaluations_scope",
        "rule_evaluations",
        ["organization_id", "product_id", "subject_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_rule_evaluations_scope", table_name="rule_evaluations")
    op.drop_table("rule_evaluations")

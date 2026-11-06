"""Persist measured scope and status for each scanner run."""

import sqlalchemy as sa
from alembic import op

revision = "0006_scanner_coverage"
down_revision = "0005_products"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "scanner_coverage",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "binding_id",
            sa.String(36),
            sa.ForeignKey("repo_bindings.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("scanner", sa.String(100), nullable=False),
        sa.Column("ref", sa.String(200), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("source_revision", sa.String(64), nullable=True),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("files", sa.JSON, nullable=False),
        sa.Column("errors", sa.JSON, nullable=False),
        sa.CheckConstraint(
            "status IN ('covered', 'partial', 'failed')",
            name="ck_scanner_coverage_status",
        ),
    )
    op.create_index(
        "ix_scanner_coverage_scope",
        "scanner_coverage",
        ["binding_id", "scanner", "ref", "observed_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_scanner_coverage_scope", table_name="scanner_coverage")
    op.drop_table("scanner_coverage")

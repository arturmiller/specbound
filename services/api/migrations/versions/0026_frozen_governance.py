"""Freeze scan governance before execution without inventing historical metadata."""

import sqlalchemy as sa
from alembic import op

revision = "0026_frozen_governance"
down_revision = "0025_evidence_resources"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "public_license_scans", sa.Column("governance_context", sa.JSON, nullable=True)
    )
    op.add_column(
        "assessment_snapshots", sa.Column("governance_context", sa.JSON, nullable=True)
    )
    op.add_column(
        "assessment_snapshots", sa.Column("control_results", sa.JSON, nullable=True)
    )


def downgrade():
    db = op.get_bind()
    for table in ("public_license_scans", "assessment_snapshots"):
        if db.execute(
            sa.text(
                f"SELECT 1 FROM {table} WHERE governance_context IS NOT NULL LIMIT 1"
            )
        ).first():
            raise RuntimeError("Cannot discard frozen governance provenance")
    op.drop_column("assessment_snapshots", "control_results")
    op.drop_column("assessment_snapshots", "governance_context")
    op.drop_column("public_license_scans", "governance_context")

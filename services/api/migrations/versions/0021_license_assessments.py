"""Preserve truthful scanner provenance and manual repository assessments."""

import sqlalchemy as sa
from alembic import op

revision = "0021_license_assessments"
down_revision = "0020_public_license_scans"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "evidence_records",
        "collector_revision",
        existing_type=sa.String(64),
        nullable=True,
    )
    op.alter_column(
        "evidence_records",
        "collector_image",
        existing_type=sa.String(500),
        nullable=True,
    )
    op.add_column(
        "evidence_records",
        sa.Column(
            "producer_kind", sa.String(32), nullable=False, server_default="collector"
        ),
    )
    op.add_column(
        "evidence_records", sa.Column("producer_scan_id", sa.String(36), nullable=True)
    )
    op.create_check_constraint(
        "ck_evidence_producer",
        "evidence_records",
        "(producer_kind = 'collector' AND collector_revision IS NOT NULL AND collector_image IS NOT NULL AND producer_scan_id IS NULL) OR "
        "(producer_kind = 'public-license-scan' AND collector_revision IS NULL AND collector_image IS NULL AND producer_scan_id IS NOT NULL)",
    )
    op.add_column(
        "public_license_scans",
        sa.Column(
            "assessment_id",
            sa.String(36),
            sa.ForeignKey("assessment_snapshots.id", ondelete="SET NULL"),
        ),
    )
    op.drop_constraint("ck_assessment_context", "assessment_snapshots", type_="check")
    op.create_check_constraint(
        "ck_assessment_context",
        "assessment_snapshots",
        "(context = 'pull_request' AND pull_request_number IS NOT NULL AND pull_request_number > 0) OR "
        "(context IN ('baseline', 'repository') AND pull_request_number IS NULL)",
    )


def downgrade() -> None:
    db = op.get_bind()
    if db.execute(
        sa.text(
            "SELECT count(*) FROM evidence_records WHERE producer_kind <> 'collector'"
        )
    ).scalar_one():
        raise RuntimeError("Cannot downgrade while non-collector evidence exists")
    if db.execute(
        sa.text(
            "SELECT count(*) FROM assessment_snapshots WHERE context = 'repository'"
        )
    ).scalar_one():
        raise RuntimeError("Cannot downgrade while repository assessments exist")
    op.drop_constraint("ck_assessment_context", "assessment_snapshots", type_="check")
    op.create_check_constraint(
        "ck_assessment_context",
        "assessment_snapshots",
        "(context = 'pull_request' AND pull_request_number IS NOT NULL AND pull_request_number > 0) OR "
        "(context = 'baseline' AND pull_request_number IS NULL)",
    )
    op.drop_column("public_license_scans", "assessment_id")
    op.drop_constraint("ck_evidence_producer", "evidence_records", type_="check")
    op.drop_column("evidence_records", "producer_scan_id")
    op.drop_column("evidence_records", "producer_kind")
    op.alter_column(
        "evidence_records",
        "collector_image",
        existing_type=sa.String(500),
        nullable=False,
    )
    op.alter_column(
        "evidence_records",
        "collector_revision",
        existing_type=sa.String(64),
        nullable=False,
    )

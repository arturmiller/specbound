"""Persist collector observations and their bounded freshness interval."""

import sqlalchemy as sa
from alembic import op

revision = "0010_evidence_records"
down_revision = "0009_pack_catalog"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "evidence_records",
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
        sa.Column("capability", sa.String(500), nullable=False),
        sa.Column("environment", sa.String(200), nullable=False),
        sa.Column("target_revision", sa.String(71), nullable=False),
        sa.Column("collector_revision", sa.String(64), nullable=False),
        sa.Column("collector_image", sa.String(500), nullable=False),
        sa.Column("provenance", sa.JSON, nullable=False),
        sa.Column("value", sa.JSON, nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ttl_seconds", sa.Integer, nullable=False),
        sa.CheckConstraint("ttl_seconds > 0", name="ck_evidence_positive_ttl"),
        sa.CheckConstraint("expires_at > observed_at", name="ck_evidence_expiry"),
    )
    op.create_index(
        "ix_evidence_scope",
        "evidence_records",
        [
            "organization_id",
            "product_id",
            "environment",
            "target_revision",
            "subject_id",
            "capability",
        ],
    )


def downgrade() -> None:
    op.drop_index("ix_evidence_scope", table_name="evidence_records")
    op.drop_table("evidence_records")

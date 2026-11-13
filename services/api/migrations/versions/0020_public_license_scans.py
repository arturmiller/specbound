"""Persist explicitly public license scan jobs and their actual results."""

import sqlalchemy as sa
from alembic import op

revision = "0020_public_license_scans"
down_revision = "0019_provider_test_runs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "public_license_scans",
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
        sa.Column("repository", sa.String(200), nullable=False),
        sa.Column("ref", sa.String(200), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column("attempts", sa.Integer, nullable=False, server_default="0"),
        sa.Column("lease_token", sa.String(36)),
        sa.Column("lease_until", sa.DateTime(timezone=True)),
        sa.Column("error_code", sa.String(40)),
        sa.Column("result", sa.JSON),
        sa.CheckConstraint(
            "status IN ('pending', 'running', 'completed', 'failed')",
            name="ck_public_license_scan_status",
        ),
    )
    op.create_index(
        "ix_public_license_scans_binding",
        "public_license_scans",
        ["organization_id", "binding_id", "created_at"],
    )


def downgrade() -> None:
    if (
        op.get_bind()
        .execute(sa.text("SELECT count(*) FROM public_license_scans"))
        .scalar_one()
    ):
        raise RuntimeError("Cannot downgrade while public license scans exist")
    op.drop_index("ix_public_license_scans_binding", table_name="public_license_scans")
    op.drop_table("public_license_scans")

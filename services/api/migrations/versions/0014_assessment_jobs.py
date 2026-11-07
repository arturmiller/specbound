"""Queue unique PR-head assessment requests from verified deliveries."""

import sqlalchemy as sa
from alembic import op

revision = "0014_assessment_jobs"
down_revision = "0013_findings"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "assessment_jobs",
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
        sa.Column(
            "delivery_id",
            sa.String(36),
            sa.ForeignKey("github_events.delivery_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("pull_request_id", sa.BigInteger, nullable=False),
        sa.Column("pull_request_number", sa.Integer, nullable=False),
        sa.Column("head_sha", sa.String(64), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint(
            "binding_id",
            "pull_request_number",
            "head_sha",
            name="uq_assessment_job_pr_head",
        ),
        sa.CheckConstraint(
            "pull_request_id > 0 AND pull_request_number > 0",
            name="ck_assessment_job_pr",
        ),
        sa.CheckConstraint("status IN ('pending')", name="ck_assessment_job_status"),
    )
    op.create_index(
        "ix_assessment_jobs_status_created", "assessment_jobs", ["status", "created_at"]
    )


def downgrade() -> None:
    op.drop_index("ix_assessment_jobs_status_created", table_name="assessment_jobs")
    op.drop_table("assessment_jobs")

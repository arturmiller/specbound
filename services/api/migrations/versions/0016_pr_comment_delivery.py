"""Track delivery of PR summaries separately from assessment completion."""

import sqlalchemy as sa
from alembic import op

revision = "0016_pr_comment_delivery"
down_revision = "0015_worker_leases"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "assessment_jobs", sa.Column("comment_processed_at", sa.DateTime(timezone=True))
    )
    op.add_column(
        "assessment_jobs", sa.Column("comment_retry_at", sa.DateTime(timezone=True))
    )
    op.create_index(
        "ix_assessment_jobs_comment_pending",
        "assessment_jobs",
        ["status", "comment_processed_at", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_assessment_jobs_comment_pending", table_name="assessment_jobs")
    op.drop_column("assessment_jobs", "comment_retry_at")
    op.drop_column("assessment_jobs", "comment_processed_at")

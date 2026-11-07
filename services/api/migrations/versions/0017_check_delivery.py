"""Track independent commit-check delivery and evidence revalidation."""

import sqlalchemy as sa
from alembic import op

revision = "0017_check_delivery"
down_revision = "0016_pr_comment_delivery"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for name in ("check_processed_at", "check_retry_at", "check_valid_until"):
        op.add_column("assessment_jobs", sa.Column(name, sa.DateTime(timezone=True)))


def downgrade() -> None:
    for name in ("check_valid_until", "check_retry_at", "check_processed_at"):
        op.drop_column("assessment_jobs", name)

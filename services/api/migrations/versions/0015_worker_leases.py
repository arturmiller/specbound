"""Add fenced worker leases, retry state, and one result per job."""

import sqlalchemy as sa
from alembic import op

revision = "0015_worker_leases"
down_revision = "0014_assessment_jobs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("assessment_jobs") as batch:
        batch.drop_constraint("ck_assessment_job_status", type_="check")
        batch.add_column(
            sa.Column("attempts", sa.Integer, nullable=False, server_default="0")
        )
        batch.add_column(sa.Column("lease_token", sa.String(36), nullable=True))
        batch.add_column(
            sa.Column("lease_until", sa.DateTime(timezone=True), nullable=True)
        )
        batch.add_column(sa.Column("last_error", sa.String(50), nullable=True))
        batch.add_column(sa.Column("result_snapshot_id", sa.String(36), nullable=True))
        batch.create_foreign_key(
            "fk_assessment_job_result",
            "assessment_snapshots",
            ["result_snapshot_id"],
            ["id"],
            ondelete="RESTRICT",
        )
        batch.create_unique_constraint(
            "uq_assessment_job_result", ["result_snapshot_id"]
        )
        batch.create_check_constraint(
            "ck_assessment_job_status",
            "status IN ('pending', 'running', 'completed', 'dead')",
        )
        batch.create_check_constraint("ck_assessment_job_attempts", "attempts >= 0")
        batch.create_check_constraint(
            "ck_assessment_job_lease",
            "(status = 'running' AND lease_token IS NOT NULL AND lease_until IS NOT NULL AND result_snapshot_id IS NULL) OR (status IN ('pending', 'dead') AND lease_token IS NULL AND lease_until IS NULL AND result_snapshot_id IS NULL) OR (status = 'completed' AND lease_token IS NOT NULL AND lease_until IS NULL AND result_snapshot_id IS NOT NULL)",
        )


def downgrade() -> None:
    incompatible = (
        op.get_bind()
        .execute(
            sa.text(
                "SELECT COUNT(*) FROM assessment_jobs WHERE status <> 'pending' OR attempts <> 0"
            )
        )
        .scalar_one()
    )
    if incompatible:
        raise RuntimeError("Cannot downgrade while jobs have execution history")
    with op.batch_alter_table("assessment_jobs") as batch:
        batch.drop_constraint("ck_assessment_job_lease", type_="check")
        batch.drop_constraint("ck_assessment_job_attempts", type_="check")
        batch.drop_constraint("ck_assessment_job_status", type_="check")
        batch.drop_constraint("uq_assessment_job_result", type_="unique")
        batch.drop_constraint("fk_assessment_job_result", type_="foreignkey")
        for column in (
            "result_snapshot_id",
            "last_error",
            "lease_until",
            "lease_token",
            "attempts",
        ):
            batch.drop_column(column)
        batch.create_check_constraint(
            "ck_assessment_job_status", "status IN ('pending')"
        )

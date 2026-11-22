"""Store scoped license approvals and keep their revocation history."""

import sqlalchemy as sa
from alembic import op

revision = "0029_license_approvals"
down_revision = "0028_catalog_archival"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "license_approvals",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), nullable=False),
        sa.Column("product_id", sa.String(36), nullable=False),
        sa.Column("binding_id", sa.String(36), nullable=False),
        sa.Column("subject_id", sa.String(500), nullable=False),
        sa.Column("artifact_digest", sa.String(64), nullable=False),
        sa.Column("control_id", sa.String(128), nullable=False),
        sa.Column("policy_digest", sa.String(64), nullable=False),
        sa.Column("license_use", sa.String(32), nullable=False),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("conditions", sa.Text(), nullable=False),
        sa.Column("proof_url", sa.Text(), nullable=False),
        sa.Column("approved_by", sa.String(200), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint("expires_at IS NULL OR expires_at > created_at"),
    )
    op.create_index(
        "ix_license_approvals_scope",
        "license_approvals",
        ["organization_id", "product_id", "binding_id", "subject_id", "license_use"],
    )


def downgrade():
    if (
        op.get_bind()
        .execute(sa.text("SELECT 1 FROM license_approvals LIMIT 1"))
        .first()
    ):
        raise RuntimeError("Cannot discard license approval history")
    op.drop_table("license_approvals")

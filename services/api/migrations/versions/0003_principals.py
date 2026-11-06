"""Persist issuer-qualified user and agent principals."""

import sqlalchemy as sa
from alembic import op

revision = "0003_principals"
down_revision = "0002_organizations_teams"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "principals",
        sa.Column("id", sa.String(200), primary_key=True),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("issuer", sa.Text(), nullable=True),
        sa.Column("subject", sa.Text(), nullable=True),
        sa.CheckConstraint("kind IN ('user', 'agent')", name="ck_principals_kind"),
        sa.CheckConstraint(
            "(issuer IS NULL AND subject IS NULL) OR (issuer IS NOT NULL AND subject IS NOT NULL)",
            name="ck_principals_identity_pair",
        ),
        sa.CheckConstraint(
            "kind != 'user' OR (issuer IS NOT NULL AND subject IS NOT NULL)",
            name="ck_principals_user_identity",
        ),
        sa.UniqueConstraint("issuer", "subject", name="uq_principals_issuer_subject"),
    )


def downgrade() -> None:
    op.drop_table("principals")

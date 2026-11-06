"""Persist immutable tag pins and the active revision pointer."""

import sqlalchemy as sa
from alembic import op

revision = "0008_pack_revisions"
down_revision = "0007_github_events"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "pack_revisions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "organization_id",
            sa.String(36),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("repository", sa.String(200), nullable=False),
        sa.Column("tag", sa.String(200), nullable=False),
        sa.Column("commit_sha", sa.String(64), nullable=False),
        sa.UniqueConstraint(
            "organization_id", "repository", "tag", name="uq_pack_revision_tag"
        ),
        sa.UniqueConstraint(
            "organization_id", "repository", "id", name="uq_pack_revision_scope"
        ),
    )
    op.create_table(
        "pack_activations",
        sa.Column("organization_id", sa.String(36), primary_key=True),
        sa.Column("repository", sa.String(200), primary_key=True),
        sa.Column("revision_id", sa.String(36), nullable=False),
        sa.ForeignKeyConstraint(
            ["organization_id", "repository", "revision_id"],
            [
                "pack_revisions.organization_id",
                "pack_revisions.repository",
                "pack_revisions.id",
            ],
            ondelete="CASCADE",
        ),
    )


def downgrade() -> None:
    op.drop_table("pack_activations")
    op.drop_table("pack_revisions")

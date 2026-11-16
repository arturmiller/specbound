"""Pin individual manifest sources while retaining legacy revision identities."""

import sqlalchemy as sa
from alembic import op

revision = "0022_manifest_sources"
down_revision = "0021_license_assessments"
branch_labels = None
depends_on = None


def _drop_activation_foreign_keys():
    for key in sa.inspect(op.get_bind()).get_foreign_keys("pack_activations"):
        op.drop_constraint(key["name"], "pack_activations", type_="foreignkey")


def upgrade():
    op.add_column(
        "pack_revisions",
        sa.Column(
            "manifest_path", sa.String(500), nullable=False, server_default="pack.yaml"
        ),
    )
    op.add_column(
        "pack_revisions",
        sa.Column("ref_kind", sa.String(20), nullable=False, server_default="tag"),
    )
    op.add_column(
        "pack_activations",
        sa.Column(
            "manifest_path", sa.String(500), nullable=False, server_default="pack.yaml"
        ),
    )
    op.execute(
        "UPDATE pack_revisions SET manifest_path = 'provider.yaml' WHERE id IN (SELECT revision_id FROM pack_catalog WHERE kind = 'provider')"
    )
    op.execute(
        "UPDATE pack_activations a SET manifest_path = r.manifest_path FROM pack_revisions r WHERE a.revision_id = r.id"
    )
    op.drop_constraint("uq_pack_revision_tag", "pack_revisions", type_="unique")
    op.create_unique_constraint(
        "uq_pack_revision_source",
        "pack_revisions",
        [
            "organization_id",
            "repository",
            "tag",
            "manifest_path",
            "ref_kind",
            "commit_sha",
        ],
    )
    op.create_index(
        "uq_pack_revision_pinned_tag",
        "pack_revisions",
        ["organization_id", "repository", "tag", "manifest_path"],
        unique=True,
        postgresql_where=sa.text("ref_kind = 'tag'"),
    )
    op.create_check_constraint(
        "ck_pack_ref_kind", "pack_revisions", "ref_kind IN ('tag', 'branch', 'commit')"
    )
    op.create_unique_constraint(
        "uq_pack_revision_manifest_scope",
        "pack_revisions",
        ["organization_id", "repository", "manifest_path", "id"],
    )
    _drop_activation_foreign_keys()
    op.drop_constraint("pack_activations_pkey", "pack_activations", type_="primary")
    op.create_primary_key(
        "pack_activations_pkey",
        "pack_activations",
        ["organization_id", "repository", "manifest_path"],
    )
    op.create_foreign_key(
        "fk_pack_activation_manifest",
        "pack_activations",
        "pack_revisions",
        ["organization_id", "repository", "manifest_path", "revision_id"],
        ["organization_id", "repository", "manifest_path", "id"],
        ondelete="CASCADE",
    )
    op.add_column("pack_catalog", sa.Column("content_digest", sa.String(64)))
    op.add_column(
        "pack_catalog",
        sa.Column("schemas", sa.JSON, nullable=False, server_default=sa.text("'{}'")),
    )


def downgrade():
    if (
        op.get_bind()
        .execute(
            sa.text(
                "SELECT 1 FROM pack_catalog WHERE content_digest IS NOT NULL LIMIT 1"
            )
        )
        .first()
    ):
        raise RuntimeError("Cannot discard manifest provenance and stored schemas")
    _drop_activation_foreign_keys()
    op.drop_constraint("pack_activations_pkey", "pack_activations", type_="primary")
    op.create_primary_key(
        "pack_activations_pkey", "pack_activations", ["organization_id", "repository"]
    )
    op.create_foreign_key(
        "fk_pack_activation_scope",
        "pack_activations",
        "pack_revisions",
        ["organization_id", "repository", "revision_id"],
        ["organization_id", "repository", "id"],
        ondelete="CASCADE",
    )
    op.drop_constraint(
        "uq_pack_revision_manifest_scope", "pack_revisions", type_="unique"
    )
    op.drop_constraint("ck_pack_ref_kind", "pack_revisions", type_="check")
    op.drop_index("uq_pack_revision_pinned_tag", table_name="pack_revisions")
    op.drop_constraint("uq_pack_revision_source", "pack_revisions", type_="unique")
    op.create_unique_constraint(
        "uq_pack_revision_tag",
        "pack_revisions",
        ["organization_id", "repository", "tag"],
    )
    op.drop_column("pack_catalog", "schemas")
    op.drop_column("pack_catalog", "content_digest")
    op.drop_column("pack_activations", "manifest_path")
    op.drop_column("pack_revisions", "ref_kind")
    op.drop_column("pack_revisions", "manifest_path")

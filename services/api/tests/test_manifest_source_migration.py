"""Upgrade legacy pins in an isolated PostgreSQL schema without rewriting IDs."""

import os
import subprocess
import sys
import unittest
from pathlib import Path
from uuid import uuid4

import yaml
from sqlalchemy import JSON, bindparam, create_engine, text


class ManifestSourceMigrationTest(unittest.TestCase):
    def test_existing_roots_and_activation_pointers_survive_upgrade(self):
        engine = create_engine(os.environ["DATABASE_URL"])
        schema = "manifest_upgrade_" + uuid4().hex
        scoped_url = engine.url.update_query_dict(
            {"options": "-csearch_path=" + schema}
        )
        scoped = create_engine(scoped_url)
        environment = {
            **os.environ,
            "DATABASE_URL": scoped_url.render_as_string(hide_password=False),
        }

        def migrate(target):
            return subprocess.run(
                [sys.executable, "-m", "alembic", "upgrade", target],
                env=environment,
                capture_output=True,
                text=True,
            )

        try:
            with engine.begin() as db:
                db.execute(text(f"CREATE SCHEMA {schema}"))
            before = migrate("0021_license_assessments")
            self.assertEqual(before.returncode, 0, before.stderr)
            org = str(uuid4())
            expected = {}
            with scoped.begin() as db:
                db.execute(
                    text(
                        "INSERT INTO principals (id, kind, issuer, subject) VALUES ('user:migration', 'user', 'test', 'migration')"
                    )
                )
                db.execute(
                    text(
                        "INSERT INTO organizations (id, name, owner_principal_id) VALUES (:id, 'Migration', 'user:migration')"
                    ),
                    {"id": org},
                )
                for kind, filename in (
                    ("governance", "pack.yaml"),
                    ("provider", "provider.yaml"),
                ):
                    revision_id = str(uuid4())
                    repository = "legacy/" + kind
                    fixture = Path(__file__).parent / "fixtures" / kind / filename
                    manifest = yaml.safe_load(fixture.read_bytes())
                    db.execute(
                        text(
                            "INSERT INTO pack_revisions (id, organization_id, repository, tag, commit_sha) VALUES (:id, :org, :repo, 'v1', :sha)"
                        ),
                        {
                            "id": revision_id,
                            "org": org,
                            "repo": repository,
                            "sha": "a" * 40,
                        },
                    )
                    statement = text(
                        "INSERT INTO pack_catalog (revision_id, kind, manifest, controls, capabilities) VALUES (:id, :kind, :manifest, '[]', '[]')"
                    ).bindparams(bindparam("manifest", type_=JSON))
                    db.execute(
                        statement,
                        {"id": revision_id, "kind": kind, "manifest": manifest},
                    )
                    db.execute(
                        text(
                            "INSERT INTO pack_activations (organization_id, repository, revision_id) VALUES (:org, :repo, :id)"
                        ),
                        {"org": org, "repo": repository, "id": revision_id},
                    )
                    expected[revision_id] = (filename, manifest)
            upgraded = migrate("0022_manifest_sources")
            self.assertEqual(upgraded.returncode, 0, upgraded.stderr)
            team_id, product_id, binding_id = (str(uuid4()) for _ in range(3))
            with scoped.begin() as db:
                db.execute(
                    text(
                        "INSERT INTO teams (id, organization_id, name) VALUES (:id, :org, 'Legacy team')"
                    ),
                    {"id": team_id, "org": org},
                )
                db.execute(
                    text(
                        "INSERT INTO products (id, owner_team_id, name) VALUES (:id, :team, 'Existing product')"
                    ),
                    {"id": product_id, "team": team_id},
                )
                db.execute(
                    text(
                        "INSERT INTO repo_bindings (id, product_id, provider, repository) VALUES (:id, :product, 'github', 'legacy/product')"
                    ),
                    {"id": binding_id, "product": product_id},
                )
            current = migrate("head")
            self.assertEqual(current.returncode, 0, current.stderr)
            with scoped.begin() as db:
                self.assertEqual(
                    tuple(
                        db.execute(
                            text(
                                "SELECT p.id, p.owner_team_id, p.name, r.id, r.repository FROM products p JOIN repo_bindings r ON r.product_id = p.id"
                            )
                        ).one()
                    ),
                    (
                        product_id,
                        team_id,
                        "Existing product",
                        binding_id,
                        "legacy/product",
                    ),
                )
                self.assertEqual(
                    db.execute(
                        text("SELECT count(*) FROM product_governance")
                    ).scalar_one(),
                    0,
                    "Do not invent a historical profile assignment",
                )
                rows = (
                    db.execute(
                        text(
                            "SELECT r.id, r.manifest_path, a.manifest_path AS active_path, c.manifest, c.content_digest FROM pack_revisions r JOIN pack_activations a ON a.revision_id = r.id JOIN pack_catalog c ON c.revision_id = r.id"
                        )
                    )
                    .mappings()
                    .all()
                )
                self.assertEqual(len(rows), 2)
                for row in rows:
                    path, manifest = expected[row["id"]]
                    self.assertEqual(
                        (row["manifest_path"], row["active_path"], row["manifest"]),
                        (path, path, manifest),
                    )
                    self.assertIsNone(
                        row["content_digest"], "Do not invent historical source hashes"
                    )
                db.execute(
                    text("UPDATE pack_catalog SET content_digest = :digest"),
                    {"digest": "b" * 64},
                )
            rejected = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "alembic",
                    "downgrade",
                    "0021_license_assessments",
                ],
                env=environment,
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(rejected.returncode, 0)
            self.assertIn("Cannot discard manifest provenance", rejected.stderr)
            with scoped.connect() as db:
                self.assertEqual(
                    db.execute(
                        text(
                            "SELECT COUNT(*) FROM pack_revisions WHERE manifest_path IS NOT NULL"
                        )
                    ).scalar_one(),
                    2,
                )
        finally:
            scoped.dispose()
            with engine.begin() as db:
                db.execute(text(f"DROP SCHEMA IF EXISTS {schema} CASCADE"))
            engine.dispose()

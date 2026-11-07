"""Readiness validates the actual database migration before checking the bucket."""

import unittest
from unittest.mock import Mock, patch

from app.readiness import check_readiness, expected_heads
from sqlalchemy import create_engine, text
from sqlalchemy.pool import StaticPool


class ReadinessTest(unittest.TestCase):
    def test_schema_must_match_current_head_before_bucket_check(self):
        engine = create_engine("sqlite://", poolclass=StaticPool)
        with engine.begin() as db:
            db.execute(
                text("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL)")
            )
            for version in expected_heads():
                db.execute(
                    text("INSERT INTO alembic_version (version_num) VALUES (:version)"),
                    {"version": version},
                )
        store = Mock()
        try:
            with (
                patch("app.readiness.get_engine", return_value=engine),
                patch("app.readiness.configured_blobstore", return_value=store),
            ):
                check_readiness()
                store.check_ready.assert_called_once_with()
                with engine.begin() as db:
                    db.execute(
                        text("UPDATE alembic_version SET version_num = 'outdated'")
                    )
                with self.assertRaises(RuntimeError):
                    check_readiness()
                self.assertEqual(store.check_ready.call_count, 1)
        finally:
            engine.dispose()

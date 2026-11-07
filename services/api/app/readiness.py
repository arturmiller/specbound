"""Bounded readiness checks for the database schema and local object bucket."""

from functools import lru_cache
from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import text

from app.database import get_engine
from app.s3_blobstore import configured_blobstore


@lru_cache(maxsize=1)
def expected_heads():
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    return frozenset(ScriptDirectory.from_config(config).get_heads())


def check_readiness():
    with get_engine().connect() as connection:
        connection.execute(text("SELECT 1"))
        current = frozenset(
            connection.execute(
                text("SELECT version_num FROM alembic_version")
            ).scalars()
        )
    if not current or current != expected_heads():
        raise RuntimeError("Database schema is not at the expected migration")
    configured_blobstore(connect_timeout=2, read_timeout=2, retries=0).check_ready()

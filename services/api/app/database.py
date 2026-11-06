import os
from functools import lru_cache

from sqlalchemy import create_engine


@lru_cache(maxsize=1)
def get_engine():
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL is required")
    return create_engine(url, pool_pre_ping=True)


def get_connection():
    with get_engine().begin() as connection:
        yield connection

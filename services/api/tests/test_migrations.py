"""Integration test: use only a new, disposable PostgreSQL database."""

import os
import socket
import subprocess
import sys
import time
import unittest
from urllib.error import URLError
from urllib.request import urlopen

from sqlalchemy import create_engine, inspect, text


class MigrationIntegrationTest(unittest.TestCase):
    def test_empty_database_migrates_and_api_starts(self) -> None:
        url = os.environ.get("TEST_DATABASE_URL")
        if not url:
            self.fail("TEST_DATABASE_URL must point to a new disposable PostgreSQL database")
        engine = create_engine(url)
        try:
            self.assertEqual(inspect(engine).get_table_names(), [], "Test database must be empty")
            environment = {**os.environ, "DATABASE_URL": url}
            for _ in range(2):
                subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], check=True, env=environment)
            with engine.connect() as connection:
                versions = connection.execute(text("SELECT version_num FROM alembic_version")).scalars().all()
            self.assertEqual(versions, ["0001_baseline"])

            with socket.socket() as sock:
                sock.bind(("127.0.0.1", 0))
                port = sock.getsockname()[1]
            process = subprocess.Popen(
                [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(port)],
                env=environment,
            )
            try:
                deadline = time.monotonic() + 20
                while True:
                    try:
                        with urlopen(f"http://127.0.0.1:{port}/healthz", timeout=1) as response:
                            self.assertEqual(response.status, 200)
                            self.assertEqual(response.read(), b'{"status":"ok"}')
                        break
                    except URLError:
                        if process.poll() is not None or time.monotonic() >= deadline:
                            self.fail("API did not start after migration")
                        time.sleep(0.2)
            finally:
                process.terminate()
                process.wait(timeout=10)
        finally:
            engine.dispose()


if __name__ == "__main__":
    unittest.main()

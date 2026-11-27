"""Worker entry points must import without the API's web framework."""

import os
import subprocess
import sys
import unittest
from pathlib import Path

API = Path(__file__).resolve().parents[2]
WORKER = API.parent / "worker"

PROBE = """
import importlib.abc
import sys


class BlockWebFramework(importlib.abc.MetaPathFinder):
    def find_spec(self, name, path=None, target=None):
        if name.split(".")[0] in ("fastapi", "starlette"):
            raise ModuleNotFoundError(f"No module named {name!r}")
        return None


sys.meta_path.insert(0, BlockWebFramework())
import pr_license_worker  # noqa: E402,F401
import public_license_worker  # noqa: E402,F401
"""


class WorkerImportTest(unittest.TestCase):
    def test_license_workers_do_not_need_the_api_web_framework(self):
        result = subprocess.run(
            [sys.executable, "-c", PROBE],
            cwd=WORKER,
            env={**os.environ, "PYTHONPATH": os.pathsep.join((str(API), str(WORKER)))},
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr[-2000:])


if __name__ == "__main__":
    unittest.main()

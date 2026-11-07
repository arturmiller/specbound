"""Each documented command runs as a standalone offline example."""

import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
SCRIPT = ROOT / "services" / "api" / "examples" / "docs_examples.py"


class DocumentationExamplesTest(unittest.TestCase):
    def test_each_documented_example_runs(self):
        expected = {
            "start": {"status": "ok"},
            "packs": {"pack": "com.acme.security", "control": "SEC-NET-001"},
            "evidence": {
                "capability": "net.internet-reachability/v1",
                "observations": 1,
                "valid": True,
            },
            "security": {"original": True, "modified": False},
            "pr": {"repository": "example/repo", "pr": 17, "head": "a" * 40},
        }
        for name, result in expected.items():
            with self.subTest(example=name):
                process = subprocess.run(
                    [sys.executable, str(SCRIPT), name],
                    cwd=ROOT,
                    text=True,
                    capture_output=True,
                    check=True,
                    timeout=30,
                )
                self.assertEqual(json.loads(process.stdout), result)

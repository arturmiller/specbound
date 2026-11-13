"""The bundled example is a valid governance pack, not an implicit approval."""

import unittest
from pathlib import Path

from app.git_source import GitSnapshot
from app.governance_pack import load_governance_pack

ROOT = Path(__file__).resolve().parents[4]


class LicensePolicyPackTest(unittest.TestCase):
    def test_license_policy_is_a_valid_explicit_pack(self):
        pack = ROOT / "policies" / "python-license"
        snapshot = GitSnapshot("a" * 40, {
            "pack.yaml": (pack / "pack.yaml").read_bytes(),
            "controls/PY-LIC-001.yaml": (pack / "controls/PY-LIC-001.yaml").read_bytes(),
        })
        loaded = load_governance_pack(snapshot)
        self.assertEqual(loaded["manifest"]["metadata"]["id"], "org.specbound.example-python-licenses")
        self.assertEqual(loaded["controls"][0]["target"]["kind"], "python.package")
        self.assertEqual(loaded["controls"][0]["assertions"][0]["operator"], "spdx-allowlist")

"""The bundled example is a valid governance pack, not an implicit approval."""

import shutil
import tempfile
import unittest
from pathlib import Path

from app.example_license_pack import POLICY_REVISION, load_example_license_pack
from app.git_source import GitSnapshot
from app.governance_pack import load_governance_pack

ROOT = next(
    parent
    for parent in Path(__file__).resolve().parents
    if (parent / "policies" / "python-license").is_dir()
)


class LicensePolicyPackTest(unittest.TestCase):
    def test_bundle_is_pinned_and_modified_files_are_rejected(self):
        loaded = load_example_license_pack()
        self.assertEqual(loaded["revision"], POLICY_REVISION)
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / "pack"
            shutil.copytree(ROOT / "policies" / "python-license", target)
            (target / "controls" / "PY-LIC-001.yaml").write_text(
                "id: altered\n", encoding="utf-8"
            )
            with self.assertRaises(ValueError):
                load_example_license_pack(target)

    def test_license_policy_is_a_valid_explicit_pack(self):
        pack = ROOT / "policies" / "python-license"
        snapshot = GitSnapshot(
            "a" * 40,
            {
                "pack.yaml": (pack / "pack.yaml").read_bytes(),
                "controls/PY-LIC-001.yaml": (
                    pack / "controls/PY-LIC-001.yaml"
                ).read_bytes(),
            },
        )
        loaded = load_governance_pack(snapshot)
        self.assertEqual(
            loaded["manifest"]["metadata"]["id"],
            "org.specbound.example-python-licenses",
        )
        self.assertEqual(loaded["controls"][0]["target"]["kind"], "python.package")
        self.assertEqual(
            loaded["controls"][0]["assertions"][0]["operator"], "spdx-allowlist"
        )

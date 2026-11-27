"""The bundled example is a valid governance pack, not an implicit approval."""

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from app.example_license_pack import POLICY_REVISION, load_example_license_pack
from app.git_source import GitSnapshot
from app.governance_pack import load_governance_pack
from app.license_policy import evaluate_license
from app.oscal_resources import load_profile
from app.resource_contracts import HERE, compile_bindings, resolve_profile, validate

ROOT = next(
    parent
    for parent in Path(__file__).resolve().parents
    if (parent / "policies" / "python-license").is_dir()
)


class LicensePolicyPackTest(unittest.TestCase):
    def test_distribution_profile_accepts_permissive_licenses_and_keeps_copyleft_review(
        self,
    ):
        examples = ROOT / "contracts" / "phase4" / "examples"
        profile_path = "profiles/license-distribution.json"
        catalog_path = "catalogs/license-controls.json"
        profile = json.loads((examples / profile_path).read_text(encoding="utf-8"))
        product = json.loads(
            (examples / "products/specbound-license.json").read_text(encoding="utf-8")
        )
        validate(product, HERE / "product.schema.json")
        catalog = json.loads((examples / catalog_path).read_text(encoding="utf-8"))
        resolved = resolve_profile(
            profile, {catalog_path: catalog}, profile_path=profile_path
        )
        self.assertEqual(
            product["spec"]["profile"]["version"], resolved["profile"]["version"]
        )
        bindings = json.loads(
            (examples / resolved["bindingPath"]).read_text(encoding="utf-8")
        )
        rule = compile_bindings(bindings, resolved)[0]["assertions"][0]
        self.assertTrue(rule["allowApprovedUse"])
        allowed = rule["allowed"]
        for license_id in ("MIT-0", "MIT AND PSF-2.0", "PSF-2.0", "BSD-3-Clause"):
            self.assertEqual(evaluate_license(license_id, allowed), "PASS", license_id)
        for license_id in ("MPL-2.0", "LGPL-3.0-only"):
            self.assertEqual(evaluate_license(license_id, allowed), "FAIL", license_id)
        # Weak copyleft only through the declared library-use enhancement.
        self.assertEqual(
            rule["libraryUse"],
            {"control": "PY-LIC-001.1", "allowed": ["LGPL-3.0-only", "MPL-2.0"]},
        )
        self.assertEqual(resolved["controlParents"], {"PY-LIC-001.1": "PY-LIC-001"})
        self.assertEqual(
            [item["controlId"] for item in product["spec"]["implementedRequirements"]],
            ["PY-LIC-001.1"],
        )
        self.assertEqual(
            product["spec"]["repositories"][0]["paths"],
            ["services/api", "services/worker"],
        )
        for path in product["spec"]["repositories"][0]["paths"]:
            self.assertTrue((ROOT / path / "uv.lock").is_file(), path)

    def test_distribution_profile_imports_the_enhancement_with_its_binding(self):
        examples = ROOT / "contracts" / "phase4" / "examples"
        files = {
            path: (examples / path).read_bytes()
            for path in (
                "profiles/license-distribution.json",
                "catalogs/license-controls.json",
                "checks/license-controls.json",
            )
        }
        loaded = load_profile(
            GitSnapshot("a" * 40, files), "profiles/license-distribution.json"
        )
        controls = {
            control["id"]: control for control in loaded["resolved"]["controls"]
        }
        self.assertEqual(list(controls), ["PY-LIC-001", "PY-LIC-001.1"])
        self.assertEqual(controls["PY-LIC-001.1"]["parentId"], "PY-LIC-001")
        self.assertEqual(
            controls["PY-LIC-001.1"]["binding"]["assertions"][0]["operator"],
            "spdx-library-use",
        )
        bindings = json.loads(files["checks/license-controls.json"])
        bindings["spec"]["controls"][1]["assertions"][0]["baseAllowedParameter"] = (
            "missing"
        )
        files["checks/license-controls.json"] = json.dumps(bindings).encode()
        with self.assertRaisesRegex(ValueError, "unknown parameter"):
            load_profile(
                GitSnapshot("a" * 40, files), "profiles/license-distribution.json"
            )

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

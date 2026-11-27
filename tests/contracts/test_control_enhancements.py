"""OSCAL control enhancements: one nested level, selected with their parent."""

import copy
import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location(
    "phase4_examples", ROOT / "contracts/phase4/validate_examples.py"
)
contracts = importlib.util.module_from_spec(spec)
spec.loader.exec_module(contracts)

ENHANCEMENT = {
    "id": "PY-LIC-001.1",
    "title": "Weak copyleft for unmodified library use",
    "params": [{"id": "license-library-allowlist"}],
    "parts": [
        {
            "name": "statement",
            "prose": "Packages under {{ insert: param, license-library-allowlist }} "
            "are permitted when used as unmodified libraries.",
        }
    ],
}


def catalog():
    document = {
        "catalog": {
            "uuid": "04c0aaf3-0df0-4476-9951-dc60540a28be",
            "metadata": {
                "title": "Softwarelizenzen",
                "last-modified": "2026-11-27T00:00:00Z",
                "version": "1.1.0",
                "oscal-version": "1.2.3",
                "props": [
                    {
                        "name": "resource-id",
                        "ns": "https://specbound.example/ns/resource",
                        "value": "license-controls",
                    }
                ],
            },
            "controls": [
                {
                    "id": "PY-LIC-001",
                    "title": "Zulässige Paketlizenzen",
                    "params": [{"id": "license-allowlist", "values": ["MIT"]}],
                    "parts": [{"name": "statement", "prose": "Approved licenses."}],
                    "controls": [copy.deepcopy(ENHANCEMENT)],
                }
            ],
        }
    }
    return document


def profile(selected, parameters):
    return {
        "profile": {
            "uuid": "76d50711-927e-49a0-b763-61dc0fac4cc3",
            "metadata": {
                "title": "Lizenzprofil",
                "last-modified": "2026-11-27T00:00:00Z",
                "version": "1.2.0",
                "oscal-version": "1.2.3",
                "props": [
                    {
                        "name": "resource-id",
                        "ns": "https://specbound.example/ns/resource",
                        "value": "license-distribution",
                    }
                ],
            },
            "imports": [
                {
                    "href": "../catalogs/license-controls.json",
                    "include-controls": [{"with-ids": selected}],
                }
            ],
            "merge": {"as-is": True},
            "modify": {
                "set-parameters": [
                    {"param-id": key, "values": values}
                    for key, values in parameters.items()
                ]
            },
        }
    }


def bindings():
    return {
        "apiVersion": "specbound.example/v1alpha1",
        "kind": "ControlBindings",
        "metadata": {"id": "license-checks", "version": "1.1.0", "name": "Lizenzen"},
        "spec": {
            "catalog": {"id": "license-controls", "version": "1.1.0"},
            "controls": [
                {
                    "id": "PY-LIC-001",
                    "target": {"kind": "python.package"},
                    "requiredEvidence": {"capability": "python.package-license/v1"},
                    "assertions": [
                        {
                            "operator": "spdx-allowlist",
                            "path": "licenseExpression",
                            "allowedParameter": "license-allowlist",
                            "allowApprovedUse": True,
                            "libraryUse": {
                                "control": "PY-LIC-001.1",
                                "allowedParameter": "license-library-allowlist",
                            },
                        }
                    ],
                },
                {
                    "id": "PY-LIC-001.1",
                    "target": {"kind": "python.package"},
                    "requiredEvidence": {"capability": "python.package-license/v1"},
                    "assertions": [
                        {
                            "operator": "spdx-library-use",
                            "path": "licenseExpression",
                            "control": "PY-LIC-001.1",
                            "allowedParameter": "license-library-allowlist",
                            "baseAllowedParameter": "license-allowlist",
                        }
                    ],
                },
            ],
        },
    }


def resolve(catalog_document, profile_document):
    return contracts.resolve_example_profile(
        profile_document,
        {"catalogs/license-controls.json": catalog_document},
        profile_path="profiles/license-distribution.json",
    )


class ControlEnhancementTest(unittest.TestCase):
    def test_enhancement_is_selected_with_its_parent_and_owns_its_parameter(self):
        resolved = resolve(
            catalog(),
            profile(
                ["PY-LIC-001", "PY-LIC-001.1"],
                {
                    "license-allowlist": ["MIT"],
                    "license-library-allowlist": ["LGPL-3.0-only", "MPL-2.0"],
                },
            ),
        )
        self.assertEqual(
            [control["id"] for control in resolved["controls"]],
            ["PY-LIC-001", "PY-LIC-001.1"],
        )
        self.assertNotIn("controls", resolved["controls"][0])
        self.assertEqual(resolved["controlParents"], {"PY-LIC-001.1": "PY-LIC-001"})
        self.assertEqual(
            resolved["parameters"]["license-library-allowlist"],
            ["LGPL-3.0-only", "MPL-2.0"],
        )

    def test_profile_without_enhancement_keeps_the_base_control_only(self):
        resolved = resolve(
            catalog(), profile(["PY-LIC-001"], {"license-allowlist": ["MIT"]})
        )
        self.assertEqual([c["id"] for c in resolved["controls"]], ["PY-LIC-001"])
        self.assertNotIn("license-library-allowlist", resolved["parameters"])
        self.assertEqual(resolved["controlParents"], {})

    def test_enhancement_without_its_parent_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "parent"):
            resolve(
                catalog(),
                profile(
                    ["PY-LIC-001.1"],
                    {"license-library-allowlist": ["LGPL-3.0-only"]},
                ),
            )

    def test_enhancement_of_an_enhancement_is_rejected(self):
        document = catalog()
        document["catalog"]["controls"][0]["controls"][0]["controls"] = [
            {"id": "PY-LIC-001.1.1", "title": "Too deep"}
        ]
        with self.assertRaisesRegex(ValueError, "Nested"):
            resolve(document, profile(["PY-LIC-001"], {"license-allowlist": ["MIT"]}))

    def test_enhancement_ids_stay_unique_across_the_catalog(self):
        document = catalog()
        document["catalog"]["controls"].append(
            {"id": "PY-LIC-001.1", "title": "Duplicate"}
        )
        with self.assertRaisesRegex(ValueError, "duplicate"):
            resolve(document, profile(["PY-LIC-001"], {"license-allowlist": ["MIT"]}))


class LibraryUseBindingTest(unittest.TestCase):
    def test_selected_enhancement_extends_the_base_rule_with_its_allowlist(self):
        resolved = resolve(
            catalog(),
            profile(
                ["PY-LIC-001", "PY-LIC-001.1"],
                {
                    "license-allowlist": ["MIT"],
                    "license-library-allowlist": ["LGPL-3.0-only", "MPL-2.0"],
                },
            ),
        )
        base, enhancement = contracts.compile_example_bindings(bindings(), resolved)
        self.assertEqual(
            base["assertions"][0]["libraryUse"],
            {"control": "PY-LIC-001.1", "allowed": ["LGPL-3.0-only", "MPL-2.0"]},
        )
        self.assertEqual(
            enhancement["assertions"][0],
            {
                "operator": "spdx-library-use",
                "path": "licenseExpression",
                "control": "PY-LIC-001.1",
                "allowed": ["LGPL-3.0-only", "MPL-2.0"],
                "baseAllowed": ["MIT"],
            },
        )

    def test_unselected_enhancement_leaves_the_base_rule_unchanged(self):
        resolved = resolve(
            catalog(), profile(["PY-LIC-001"], {"license-allowlist": ["MIT"]})
        )
        (base,) = contracts.compile_example_bindings(bindings(), resolved)
        self.assertNotIn("libraryUse", base["assertions"][0])
        self.assertEqual(base["assertions"][0]["allowed"], ["MIT"])

    def test_library_use_must_name_an_enhancement_of_the_bound_control(self):
        resolved = resolve(
            catalog(),
            profile(
                ["PY-LIC-001", "PY-LIC-001.1"],
                {
                    "license-allowlist": ["MIT"],
                    "license-library-allowlist": ["LGPL-3.0-only"],
                },
            ),
        )
        for mutate in (
            lambda doc: doc["spec"]["controls"][0]["assertions"][0][
                "libraryUse"
            ].update(control="PY-LIC-001"),
            lambda doc: doc["spec"]["controls"][1]["assertions"][0].update(
                control="PY-LIC-001"
            ),
        ):
            document = bindings()
            mutate(document)
            with (
                self.subTest(document=document),
                self.assertRaisesRegex(ValueError, "enhancement"),
            ):
                contracts.compile_example_bindings(document, resolved)


if __name__ == "__main__":
    unittest.main()

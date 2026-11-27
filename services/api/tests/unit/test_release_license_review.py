"""Release decisions must be bound to the built files and reviewed inventory."""

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from app.release_license_review import _component, browser_inventory, review_artifact
from app.release_license_summary import markdown_summary


class ReleaseLicenseReviewTest(unittest.TestCase):
    def test_browser_inventory_rejects_changed_or_unlisted_javascript(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            chunk = root / "build.js"
            chunk.write_bytes(b"const build = true;")
            digest = hashlib.sha256(chunk.read_bytes()).hexdigest()
            (root / "bundled-licenses.json").write_text(
                json.dumps(
                    {
                        "chunks": {"build.js": digest},
                        "dependencies": [
                            {"name": "react", "version": "1", "license": "MIT"}
                        ],
                    }
                ),
                encoding="utf-8",
            )
            self.assertEqual(browser_inventory(root)[1][0]["name"], "react")
            chunk.write_bytes(b"const build = false;")
            with self.assertRaises(ValueError):
                browser_inventory(root)

    def test_release_fails_until_current_inventory_notices_and_component_are_reviewed(
        self,
    ):
        package = [{"name": "driver", "version": "1", "license": "LGPL-3.0-only"}]
        record = {
            "sha256": "a" * 64,
            "inventoryEvidence": "vault:inventory",
            "noticeEvidence": "vault:notices",
            "componentApprovals": {"driver@1": "vault:driver-release"},
        }
        self.assertFalse(
            review_artifact(
                "api-image", "b" * 64, package, ["MIT"], {"api-image": record}
            )["ready"]
        )
        self.assertFalse(
            review_artifact(
                "api-image",
                "a" * 64,
                package,
                ["MIT"],
                {"api-image": {**record, "noticeEvidence": ""}},
            )["ready"]
        )
        accepted = review_artifact(
            "api-image", "a" * 64, package, ["MIT"], {"api-image": record}
        )
        self.assertTrue(accepted["ready"])
        self.assertEqual(accepted["components"][0]["status"], "APPROVED")

    def test_summary_groups_identical_findings_and_keeps_their_locations(self):
        package = {
            "SPDXID": "SPDXRef-Package-deb-test",
            "name": "binary <unsafe>",
            "versionInfo": "1",
            "licenseDeclared": "GPL-3.0-only",
            "licenseConcluded": "NOASSERTION",
        }
        location = "/usr/share/doc/test/copyright"
        native = {
            "purl": "pkg:deb/debian/test@1",
            "type": "deb",
            "licenses": [{"locations": [{"path": location}]}],
        }
        component = _component(package, native)
        self.assertEqual(component["licenseSources"], [location])
        report = {
            "ready": False,
            "projectLicenseReviewed": False,
            "artifacts": {
                key: review_artifact(key, digest, [component], ["MIT"], {})
                for key, digest in (("api-image", "a" * 64), ("worker-image", "b" * 64))
            },
        }
        text = markdown_summary(report)
        self.assertEqual(text.count("binary &lt;unsafe&gt; 1"), 1)
        self.assertEqual(text.count(location), 2)
        self.assertIn("Außerhalb der Richtlinie", text)
        self.assertIn("Rechte am eigenen Code", text)

    def test_findings_report_different_license_gaps(self):
        inputs = [
            ("NOASSERTION", "NOASSERTION", "missing-declaration"),
            ("MIT", "Apache-2.0", "conflicting-declarations"),
            ("LicenseRef-Custom", "NOASSERTION", "unresolved-expression"),
        ]
        for declared, concluded, reason in inputs:
            with self.subTest(reason=reason):
                component = _component(
                    {
                        "SPDXID": "SPDXRef-Package-test",
                        "name": "test",
                        "licenseDeclared": declared,
                        "licenseConcluded": concluded,
                    },
                    {},
                )
                report = review_artifact(
                    "api-image", "a" * 64, [component], ["MIT"], {}
                )
                self.assertEqual(report["components"][0]["reason"], reason)

    def test_image_inventory_only_normalizes_exact_python_license_names(self):
        for name, expected in (
            ("MIT license", "MIT"),
            ("Apache License 2.0", "Apache-2.0"),
            ("Dual License", "LicenseRef-Dual-License"),
        ):
            with self.subTest(name=name):
                original = "LicenseRef-" + name.replace(" ", "-")
                package = {
                    "SPDXID": "SPDXRef-Package-test",
                    "name": "example",
                    "licenseDeclared": original,
                    "licenseConcluded": "NOASSERTION",
                }
                licenses = [{"value": name, "type": "declared"}]
                native = {"type": "python", "licenses": licenses}
                self.assertEqual(_component(package, native)["license"], expected)
                self.assertEqual(
                    _component(package, {**native, "type": "deb"})["license"],
                    original,
                )
                self.assertIsNone(
                    _component({**package, "licenseConcluded": "ISC"}, native)[
                        "license"
                    ]
                )

"""Release decisions must be bound to the built files and reviewed inventory."""

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from app.release_license_review import browser_inventory, review_artifact


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

"""Governance manifest validation from pinned snapshot files."""

import unittest
from pathlib import Path

from app.git_source import GitSnapshot
from app.governance_pack import ManifestError, load_governance_pack

FIXTURES = Path(__file__).parent.parent / "fixtures" / "governance"


def fixture(name):
    return (FIXTURES / name).read_bytes()


class GovernancePackTest(unittest.TestCase):
    def load(self, pack="pack.yaml", control="control.yaml"):
        return load_governance_pack(
            GitSnapshot(
                "a" * 40,
                {
                    "pack.yaml": fixture(pack),
                    "controls/SEC-NET-001.yaml": fixture(control),
                },
            )
        )

    def test_valid_manifest_loads_referenced_controls_and_capabilities(self):
        result = self.load()
        self.assertEqual(result["revision"], "a" * 40)
        self.assertEqual(result["manifest"]["metadata"]["id"], "com.acme.security")
        self.assertEqual(result["controls"][0]["id"], "SEC-NET-001")
        self.assertEqual(
            result["controls"][0]["requiredEvidence"]["capability"],
            "net.internet-reachability/v1",
        )

    def test_target_labels_are_parsed_and_must_be_strings(self):
        control = fixture("control.yaml").replace(
            b"  kind: database", b"  kind: database\n  labels: {environment: prod}"
        )
        files = {
            "pack.yaml": fixture("pack.yaml"),
            "controls/SEC-NET-001.yaml": control,
        }
        result = load_governance_pack(GitSnapshot("a" * 40, files))
        self.assertEqual(
            result["controls"][0]["target"]["labels"], {"environment": "prod"}
        )
        files["controls/SEC-NET-001.yaml"] = control.replace(
            b"environment: prod", b"environment: 12"
        )
        with self.assertRaises(ManifestError):
            load_governance_pack(GitSnapshot("a" * 40, files))

    def test_invalid_fixtures_are_rejected(self):
        for pack, control in (
            ("pack-unknown-version.yaml", "control.yaml"),
            ("pack.yaml", "control-missing-id.yaml"),
            ("pack.yaml", "control-invalid-capability.yaml"),
        ):
            with (
                self.subTest(pack=pack, control=control),
                self.assertRaises(ManifestError),
            ):
                self.load(pack, control)

    def test_undeclared_capability_missing_file_and_yaml_alias_are_rejected(self):
        pack = fixture("pack.yaml")
        control = fixture("control.yaml").replace(
            b"net.internet-reachability/v1", b"other.capability/v1"
        )
        with self.assertRaises(ManifestError):
            load_governance_pack(
                GitSnapshot(
                    "a" * 40, {"pack.yaml": pack, "controls/SEC-NET-001.yaml": control}
                )
            )
        with self.assertRaises(ManifestError):
            load_governance_pack(GitSnapshot("a" * 40, {"pack.yaml": pack}))
        with self.assertRaises(ManifestError):
            load_governance_pack(
                GitSnapshot("a" * 40, {"pack.yaml": b"x: &a {}\ny: *a"})
            )

    def test_duplicate_controls_and_unsafe_paths_are_rejected(self):
        pack = fixture("pack.yaml")
        original = b"  - controls/SEC-NET-001.yaml"
        two = pack.replace(original, original + b"\n  - controls/duplicate.yaml")
        with self.assertRaises(ManifestError):
            load_governance_pack(
                GitSnapshot(
                    "a" * 40,
                    {
                        "pack.yaml": two,
                        "controls/SEC-NET-001.yaml": fixture("control.yaml"),
                        "controls/duplicate.yaml": fixture("control.yaml"),
                    },
                )
            )
        unsafe = pack.replace(b"controls/SEC-NET-001.yaml", b"controls/../pack.yaml")
        with self.assertRaises(ManifestError):
            load_governance_pack(GitSnapshot("a" * 40, {"pack.yaml": unsafe}))
        duplicate = pack + b"\nkind: GovernancePack\n"
        with self.assertRaises(ManifestError):
            load_governance_pack(GitSnapshot("a" * 40, {"pack.yaml": duplicate}))
        non_json = fixture("control.yaml").replace(
            b"expected: false", b"expected: .nan"
        )
        with self.assertRaises(ManifestError):
            load_governance_pack(
                GitSnapshot(
                    "a" * 40,
                    {
                        "pack.yaml": pack,
                        "controls/SEC-NET-001.yaml": non_json,
                    },
                )
            )

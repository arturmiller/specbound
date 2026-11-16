"""Manifest path isolation without granting the pack access to sibling files."""

import unittest
from pathlib import Path

from app.git_source import GitSnapshot
from app.manifest_io import ManifestError
from app.manifest_source import checked_manifest_path, load_pack_at, snapshot_for_ref

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


class ManifestSourceTest(unittest.TestCase):
    def test_explicit_branch_name_cannot_select_a_tag_with_the_same_name(self):
        class Source:
            repository = "example/resources"

            def fetch(self, ref):
                return GitSnapshot("b" * 40 if ref == "heads/release" else "a" * 40, {})

            def resolve_tag(self, tag):
                return "a" * 40

        self.assertEqual(
            snapshot_for_ref(Source(), "example/resources", "release", "branch").commit,
            "b" * 40,
        )
        self.assertEqual(
            snapshot_for_ref(Source(), "example/resources", "release", "tag").commit,
            "a" * 40,
        )

    def test_custom_manifest_reuses_existing_pack_contract(self):
        files = {
            "nested/custom.json": (FIXTURES / "governance/pack.yaml").read_bytes(),
            "nested/controls/SEC-NET-001.yaml": (
                FIXTURES / "governance/control.yaml"
            ).read_bytes(),
        }
        snapshot = GitSnapshot("a" * 40, files)
        result = load_pack_at(snapshot, "nested/custom.json", "governance")
        self.assertEqual(result["controls"][0]["id"], "SEC-NET-001")
        self.assertEqual(result["revision"], snapshot.commit)
        self.assertEqual(len(result["contentDigest"]), 64)
        del files["nested/controls/SEC-NET-001.yaml"]
        files["controls/SEC-NET-001.yaml"] = (
            FIXTURES / "governance/control.yaml"
        ).read_bytes()
        with self.assertRaises(ManifestError):
            load_pack_at(
                GitSnapshot("a" * 40, files), "nested/custom.json", "governance"
            )

    def test_path_rejects_ambiguous_and_external_names(self):
        for path in (
            "../pack.yaml",
            "/pack.yaml",
            "a//b.yaml",
            "C:/pack.json",
            "a\\b.yaml",
            "%2e%2e/pack.yaml",
            "a/./pack.yaml",
        ):
            with self.subTest(path=path), self.assertRaises(ManifestError):
                checked_manifest_path(path)

    def test_changing_a_dependency_changes_the_digest(self):
        files = {
            "pack.yaml": (FIXTURES / "governance/pack.yaml").read_bytes(),
            "controls/SEC-NET-001.yaml": (
                FIXTURES / "governance/control.yaml"
            ).read_bytes(),
        }
        first = load_pack_at(GitSnapshot("a" * 40, files), "pack.yaml", "governance")
        files["controls/SEC-NET-001.yaml"] += b"\n# new source revision\n"
        second = load_pack_at(GitSnapshot("b" * 40, files), "pack.yaml", "governance")
        self.assertNotEqual(first["contentDigest"], second["contentDigest"])

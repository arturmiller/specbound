"""Tests for real lockfile parsing and conservative license decisions."""

import hashlib
import io
import json
import tarfile
import unittest

from app.git_source import GitSnapshot
from app.license_policy import evaluate_license
from app.pypi_license_metadata import read_pypi_license
from app.python_license_scan import scan_python_licenses, scan_python_repository
from app.python_lockfiles import LockedPackage, find_uv_locks, parse_uv_lock


class LicensePolicyTest(unittest.TestCase):
    def test_known_allowed_and_denied_licenses(self):
        self.assertEqual(evaluate_license("MIT"), "PASS")
        self.assertEqual(evaluate_license("GPL-3.0-only"), "FAIL")
        self.assertEqual(evaluate_license("AGPL-3.0-only", {"AGPL-3.0-only"}), "PASS")
        self.assertEqual(evaluate_license("LicenseRef-Unverified"), "UNKNOWN")

    def test_expressions_preserve_alternatives_and_unknown(self):
        cases = {
            "MIT OR GPL-3.0-only": "PASS",
            "MIT AND GPL-3.0-only": "FAIL",
            "GPL-3.0-only OR LicenseRef-Other": "UNKNOWN",
            "MIT AND LicenseRef-Other": "UNKNOWN",
            "GPL-3.0-only AND LicenseRef-Other": "UNKNOWN",
            "GPL-3.0-only OR MIT AND Apache-2.0": "PASS",
            "(GPL-3.0-only OR MIT) AND Apache-2.0": "PASS",
            "MIT WITH Exception-unknown": "UNKNOWN",
            "MIT OR": "UNKNOWN",
            "MIT OR (GPL-3.0-only": "UNKNOWN",
            "": "UNKNOWN",
        }
        for expression, expected in cases.items():
            with self.subTest(expression=expression):
                self.assertEqual(evaluate_license(expression), expected)

    def test_explicit_exception_requires_exact_policy_entry(self):
        self.assertEqual(
            evaluate_license(
                "GPL-2.0-only WITH Classpath-exception-2.0", {"GPL-2.0-only"}
            ),
            "UNKNOWN",
        )
        self.assertEqual(
            evaluate_license(
                "GPL-2.0-only WITH Classpath-exception-2.0",
                {"GPL-2.0-only WITH Classpath-exception-2.0"},
            ),
            "PASS",
        )


class UVLockTest(unittest.TestCase):
    def test_paths_versions_artifact_hashes_and_conditional_packages(self):
        content = b"""version = 1
revision = 3
[[package]]
name = "My_Package"
version = "1.2.3"
source = { registry = "https://pypi.org/simple" }
resolution-markers = ["python_version >= '3.12'"]
wheels = [{ url = "https://files.pythonhosted.org/example.whl", hash = "sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa" }]
[[package]]
name = "private"
version = "2.0"
source = { registry = "https://private.example/simple" }
"""
        locks = find_uv_locks({"nested/uv.lock": content, "notes.txt": b""})
        public, private = locks["nested/uv.lock"]
        self.assertEqual(
            (public.name, public.version, public.source),
            ("my-package", "1.2.3", "pypi"),
        )
        self.assertEqual(public.artifact_hashes, ("a" * 64,))
        self.assertEqual(public.markers, ("python_version >= '3.12'",))
        self.assertEqual(private.source, "unsupported:registry")

    def test_invalid_and_unsupported_lockfiles_do_not_report_success(self):
        for data in (
            b"version = 2",
            b"version = true",
            b"version = 1\nrevision = 999",
            b"not-toml",
            b"version = 1\npackage = 'wrong'",
        ):
            with self.subTest(data=data), self.assertRaises(ValueError):
                parse_uv_lock("uv.lock", data)
        self.assertEqual(find_uv_locks({"pyproject.toml": b""}), {})


class PyPIMetadataTest(unittest.TestCase):
    def setUp(self):
        self.artifact_hash = "a" * 64
        self.metadata = b"Metadata-Version: 2.4\nName: example\nVersion: 1.2\nLicense-Expression: MIT\n\n"
        self.metadata_hash = hashlib.sha256(self.metadata).hexdigest()
        self.package = LockedPackage(
            "uv.lock", "example", "1.2", "pypi", (self.artifact_hash,), ()
        )
        self.item = {
            "url": "https://files.pythonhosted.org/packages/ab/example.whl",
            "hashes": {"sha256": self.artifact_hash},
            "core-metadata": {"sha256": self.metadata_hash},
        }

    def fetch(self, url, **kwargs):
        if url.startswith("https://pypi.org/simple/"):
            return json.dumps({"files": [self.item]}).encode()
        if url == self.item["url"] + ".metadata":
            return self.metadata
        raise AssertionError("unexpected URL")

    def test_verified_metadata_for_the_locked_artifact(self):
        result = read_pypi_license(self.package, self.fetch)
        self.assertEqual(result["status"], "OBSERVED")
        self.assertEqual(result["expression"], "MIT")
        self.assertEqual(result["artifacts"][0]["artifactSha256"], self.artifact_hash)

    def test_missing_hash_wrong_metadata_and_untrusted_source_are_unknown(self):
        self.item["core-metadata"]["sha256"] = "b" * 64
        self.assertEqual(
            read_pypi_license(self.package, self.fetch)["status"], "UNKNOWN"
        )
        self.item["core-metadata"]["sha256"] = self.metadata_hash
        self.item["url"] = "https://attacker.example/metadata"
        self.assertEqual(
            read_pypi_license(self.package, self.fetch)["status"], "UNKNOWN"
        )
        self.item["url"] = "https://files.pythonhosted.org/packages/ab/example.whl"
        self.metadata = self.metadata.replace(b"Version: 1.2", b"Version: 2.0")
        self.item["core-metadata"]["sha256"] = hashlib.sha256(self.metadata).hexdigest()
        self.assertEqual(
            read_pypi_license(self.package, self.fetch)["status"], "UNKNOWN"
        )

    def test_private_sources_are_not_queried(self):
        package = LockedPackage(
            "uv.lock", "example", "1.2", "git", (self.artifact_hash,), ()
        )
        self.assertEqual(read_pypi_license(package, self.fetch)["status"], "UNKNOWN")

    def test_unhashed_artifact_cannot_inherit_a_different_artifacts_license(self):
        package = LockedPackage(
            "uv.lock", "example", "1.2", "pypi", (self.artifact_hash,), (), True
        )
        self.assertEqual(read_pypi_license(package, self.fetch)["status"], "UNKNOWN")

    def test_source_archive_is_hashed_and_read_without_extracting_files(self):
        archive_bytes = io.BytesIO()
        with tarfile.open(fileobj=archive_bytes, mode="w:gz") as archive:
            info = tarfile.TarInfo("example-1.2/PKG-INFO")
            info.size = len(self.metadata)
            archive.addfile(info, io.BytesIO(self.metadata))
        artifact = archive_bytes.getvalue()
        digest = hashlib.sha256(artifact).hexdigest()
        package = LockedPackage("uv.lock", "example", "1.2", "pypi", (digest,), ())
        item = {
            "url": "https://files.pythonhosted.org/packages/ab/example.tar.gz",
            "hashes": {"sha256": digest},
            "core-metadata": False,
        }

        def fetch(url, **kwargs):
            return (
                json.dumps({"files": [item]}).encode()
                if url.startswith("https://pypi.org/")
                else artifact
            )

        result = read_pypi_license(package, fetch)
        self.assertEqual((result["status"], result["expression"]), ("OBSERVED", "MIT"))
        item["hashes"]["sha256"] = "a" * 64
        package = LockedPackage("uv.lock", "example", "1.2", "pypi", ("a" * 64,), ())
        self.assertEqual(read_pypi_license(package, fetch)["status"], "UNKNOWN")


class LicenseScanTest(unittest.TestCase):
    def test_repository_scan_pins_snapshot_and_does_not_re_fetch(self):
        class Source:
            calls = []

            def fetch(self, ref):
                self.calls.append(ref)
                return GitSnapshot("a" * 40, {"uv.lock": b"version = 1\n"})

        source = Source()
        result = scan_python_repository(source, "main")
        self.assertEqual(source.calls, ["main"])
        self.assertEqual(result["requestedRef"], "main")
        self.assertEqual(result["sourceRevision"], "a" * 40)
        self.assertEqual(result["coverage"], "UNKNOWN")

    def test_realistic_mixed_results_remain_scoped_to_lockfile(self):
        lock = b"""version = 1
[[package]]
name = "allowed"
version = "1.0"
source = { registry = "https://pypi.org/simple" }
[[package]]
name = "blocked"
version = "2.0"
source = { registry = "https://pypi.org/simple" }
[[package]]
name = "unknown"
version = "3.0"
source = { git = "https://example.invalid/repository" }
"""

        def resolve(package):
            expressions = {"allowed": "MIT", "blocked": "GPL-3.0-only"}
            return (
                {"status": "OBSERVED", "expression": expressions[package.name]}
                if package.name in expressions
                else {"status": "UNKNOWN"}
            )

        result = scan_python_licenses({"a/uv.lock": lock}, resolve=resolve)
        self.assertEqual(result["coverage"], "partial")
        self.assertEqual(result["files"], ["a/uv.lock"])
        self.assertEqual(
            [p["status"] for p in result["packages"]], ["PASS", "FAIL", "UNKNOWN"]
        )
        self.assertTrue(all(p["path"] == "a/uv.lock" for p in result["packages"]))

    def test_absent_or_broken_lock_does_not_succeed(self):
        self.assertEqual(scan_python_licenses({})["coverage"], "UNKNOWN")
        self.assertEqual(
            scan_python_licenses({"uv.lock": b"garbage"})["coverage"], "UNKNOWN"
        )

    def test_unsupported_lockfile_prevents_full_coverage(self):
        lock = b"""version = 1
[[package]]
name = "demo"
version = "1.0"
source = { registry = "https://pypi.org/simple" }
"""
        result = scan_python_licenses(
            {"uv.lock": lock, "other/poetry.lock": b""},
            resolve=lambda _: {"status": "OBSERVED", "expression": "MIT"},
        )
        self.assertEqual(result["coverage"], "partial")
        self.assertEqual(result["unsupportedFiles"], ["other/poetry.lock"])


if __name__ == "__main__":
    unittest.main()

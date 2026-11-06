"""OpenAPI and JSON Schema discovery against a fixture Git snapshot."""

import json
import unittest
from datetime import datetime, timezone
from pathlib import Path

from app.git_source import GitSnapshot, SourceNotFound
from app.openapi_scanner import scan_repository
from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry, Resource


class FixtureSource:
    def __init__(self, files):
        self.files = files

    def fetch(self, ref):
        if ref != "main":
            raise SourceNotFound("missing ref")
        return GitSnapshot("a" * 40, self.files)


class ScannerContractTest(unittest.TestCase):
    def setUp(self):
        directory = Path(__file__).parent.parent / "fixtures" / "scanner" / "service"
        self.files = {path.name: path.read_bytes() for path in directory.iterdir()}
        self.when = datetime(2026, 1, 1, tzinfo=timezone.utc)

    def scan(self, files=None, ref="main"):
        return scan_repository(
            FixtureSource(self.files if files is None else files),
            ref,
            product_id="product-1",
            repository_id="binding-1",
            observed_at=self.when,
        )

    def test_fixture_subjects_are_stable_and_pin_source(self):
        first = self.scan()
        second = self.scan(dict(reversed(list(self.files.items()))))
        self.assertEqual(first, second)
        self.assertEqual(first.errors, ())
        self.assertEqual(first.files_scanned, ("address.schema.json", "openapi.yaml"))
        self.assertEqual(len(first.subjects), 6)
        self.assertEqual(len({s["id"] for s in first.subjects}), 6)
        self.assertEqual(sum(s["type"] == "api.path" for s in first.subjects), 2)
        self.assertEqual(sum(s["type"] == "api.schema" for s in first.subjects), 4)
        for subject in first.subjects:
            self.assertEqual(subject["scope"]["productId"], "product-1")
            self.assertEqual(subject["scope"]["targetRevision"], "a" * 40)
            self.assertEqual(subject["provenance"]["sourceRevision"], "a" * 40)
            self.assertTrue(
                subject["provenance"]["sourceRef"].startswith("repo:binding-1/")
            )
            self.assertEqual(subject["observedAt"], "2026-01-01T00:00:00Z")
        refs = [s["provenance"]["sourceRef"] for s in first.subjects]
        self.assertIn("repo:binding-1/openapi.yaml#/paths/~1pets", refs)
        self.assertIn("repo:binding-1/address.schema.json#/%24defs/PostalCode", refs)
        schema_dir = Path(__file__).resolve().parents[4] / "contracts" / "v1"
        schemas = [
            json.loads((schema_dir / name).read_text(encoding="utf-8"))
            for name in ("common.schema.json", "subject.schema.json")
        ]
        registry = Registry().with_resources(
            (s["$id"], Resource.from_contents(s)) for s in schemas
        )
        validator = Draft202012Validator(
            schemas[1], registry=registry, format_checker=FormatChecker()
        )
        for subject in first.subjects:
            validator.validate(subject)

    def test_missing_or_invalid_source_is_explicit(self):
        self.assertTrue(self.scan({}, ref="missing").errors)
        self.assertTrue(self.scan({"readme.txt": b"nothing"}).errors)
        self.assertTrue(self.scan({"openapi.yaml": b"openapi: [broken"}).errors)
        self.assertTrue(
            self.scan({"openapi.yaml": b"openapi: 3.1.0\npaths: []"}).errors
        )
        self.assertTrue(
            self.scan({"openapi.yaml": b"openapi: 3.1.0\npaths: {}\npaths: {}"}).errors
        )

    def test_partial_scan_keeps_findings_and_reports_failed_file(self):
        result = self.scan({**self.files, "other.openapi.json": b"{"})
        self.assertEqual(len(result.subjects), 6)
        self.assertEqual(len(result.errors), 1)
        self.assertEqual(result.errors[0].path, "other.openapi.json")

    def test_openapi_json_and_unrelated_files(self):
        result = self.scan(
            {
                "api.openapi.json": b'{"openapi":"3.0.3","paths":{"/a/b":{"get":{}},"x-extra":"ok"}}',
                "other.json": b"not parsed",
            }
        )
        self.assertEqual(result.errors, ())
        self.assertEqual(result.files_scanned, ("api.openapi.json",))
        self.assertEqual(
            result.subjects[0]["provenance"]["sourceRef"],
            "repo:binding-1/api.openapi.json#/paths/~1a~1b",
        )

    def test_unsafe_or_ambiguous_documents_are_reported(self):
        for payload in (
            b"openapi: 3.1.0\npaths: &p {}\ncomponents: *p",
            b"openapi: 3.1.0\n" + b" " * (2 * 1024 * 1024),
        ):
            with self.subTest(length=len(payload)):
                result = self.scan({"openapi.yaml": payload})
                self.assertEqual(result.subjects, ())
                self.assertEqual(len(result.errors), 1)

    def test_timestamp_must_have_timezone(self):
        with self.assertRaises(ValueError):
            scan_repository(
                FixtureSource(self.files),
                "main",
                product_id="p",
                repository_id="r",
                observed_at=datetime(2026, 1, 1),
            )


if __name__ == "__main__":
    unittest.main()

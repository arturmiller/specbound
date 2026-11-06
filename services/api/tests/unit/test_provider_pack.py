"""Validate pinned provider definitions and their declared JSON Schemas."""

import unittest
from pathlib import Path

from app.git_source import GitSnapshot
from app.manifest_io import ManifestError
from app.provider_pack import load_provider_pack

FIXTURES = Path(__file__).parent.parent / "fixtures" / "provider"


class ProviderPackTest(unittest.TestCase):
    def setUp(self):
        self.manifest = (FIXTURES / "provider.yaml").read_bytes()
        schema = (FIXTURES / "schema.json").read_bytes()
        self.files = {
            "provider.yaml": self.manifest,
            "contracts/collect-request.json": schema,
            "contracts/observation.json": schema,
            "schemas/reachability.json": schema,
            "tests/reachability.yaml": b"name: fixture\n",
        }

    def load(self, files=None):
        return load_provider_pack(
            GitSnapshot("a" * 40, self.files if files is None else files)
        )

    def test_valid_fixture_preserves_pinned_image_and_declared_schemas(self):
        pack = self.load()
        self.assertEqual(pack["revision"], "a" * 40)
        self.assertTrue(pack["manifest"]["runtime"]["image"].endswith("a" * 64))
        self.assertIn("schemas/reachability.json", pack["schemas"])

    def test_unversioned_image_and_missing_output_schema_are_rejected(self):
        unpinned = self.manifest.replace(b"@sha256:" + b"a" * 64, b":latest")
        with self.assertRaises(ManifestError):
            self.load({**self.files, "provider.yaml": unpinned})
        missing = {
            name: value
            for name, value in self.files.items()
            if name != "schemas/reachability.json"
        }
        with self.assertRaises(ManifestError):
            self.load(missing)
        undeclared = self.manifest.replace(
            b"    outputSchema: schemas/reachability.json\n", b""
        )
        with self.assertRaises(ManifestError):
            self.load({**self.files, "provider.yaml": undeclared})

    def test_invalid_schema_and_unsafe_external_references_are_rejected(self):
        for schema in (
            b'{"$schema":"https://json-schema.org/draft/2020-12/schema","type":"nonsense"}',
            b'{"$schema":"https://json-schema.org/draft/2020-12/schema","$ref":"https://example.com/schema"}',
            b'{"type":"object","type":"string"}',
        ):
            with self.subTest(schema=schema), self.assertRaises(ManifestError):
                self.load({**self.files, "schemas/reachability.json": schema})

    def test_missing_runtime_contract_and_duplicate_capabilities_are_rejected(self):
        files = {
            name: value
            for name, value in self.files.items()
            if name != "contracts/observation.json"
        }
        with self.assertRaises(ManifestError):
            self.load(files)
        duplicate = self.manifest.replace(
            b"permissions:",
            b"  - id: net.internet-reachability\n    version: v1\n    outputSchema: schemas/reachability.json\npermissions:",
        )
        with self.assertRaises(ManifestError):
            self.load({**self.files, "provider.yaml": duplicate})

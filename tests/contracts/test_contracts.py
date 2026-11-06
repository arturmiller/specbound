import copy
import json
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry, Resource

ROOT = Path(__file__).resolve().parents[2]
SCHEMAS = ROOT / "contracts" / "v1"
FIXTURES = Path(__file__).resolve().parent / "fixtures"
KINDS = ("subject", "fact", "evidence")


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


class ContractSchemaTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        schemas = {name: read_json(SCHEMAS / f"{name}.schema.json") for name in ("common", *KINDS)}
        for schema in schemas.values():
            Draft202012Validator.check_schema(schema)
        registry = Registry().with_resources(
            (schema["$id"], Resource.from_contents(schema)) for schema in schemas.values()
        )
        checker = FormatChecker(formats=["date-time"])
        cls.validators = {
            name: Draft202012Validator(schemas[name], registry=registry, format_checker=checker)
            for name in KINDS
        }
        cls.valid = {name: read_json(FIXTURES / "valid" / f"{name}.json") for name in KINDS}

    def test_valid_and_invalid_fixture_files(self):
        for kind in KINDS:
            with self.subTest(kind=kind, valid=True):
                self.assertTrue(self.validators[kind].is_valid(self.valid[kind]))
            invalid = list((FIXTURES / "invalid").glob(f"{kind}-*.json"))
            self.assertTrue(invalid, f"No invalid fixtures for {kind}")
            for path in invalid:
                with self.subTest(fixture=path.name):
                    self.assertFalse(self.validators[kind].is_valid(read_json(path)))

    def test_required_metadata_and_version(self):
        for kind in KINDS:
            for field in ("schemaVersion", "id", "scope", "provenance", "observedAt"):
                with self.subTest(kind=kind, missing=field):
                    item = copy.deepcopy(self.valid[kind])
                    del item[field]
                    self.assertFalse(self.validators[kind].is_valid(item))
            for version in (2, "1", True):
                with self.subTest(kind=kind, version=version):
                    item = copy.deepcopy(self.valid[kind])
                    item["schemaVersion"] = version
                    self.assertFalse(self.validators[kind].is_valid(item))

    def test_invalid_values_and_timestamp_format(self):
        for kind in KINDS:
            cases = (
                ("id", "  "),
                ("scope", {"productId": ""}),
                ("provenance", {"sourceRef": " "}),
                ("observedAt", "2026-13-99T10:30:00Z"),
                ("observedAt", "2026-11-06T10:30:00"),
            )
            for field, value in cases:
                with self.subTest(kind=kind, field=field, value=value):
                    item = copy.deepcopy(self.valid[kind])
                    item[field] = value
                    self.assertFalse(self.validators[kind].is_valid(item))
            with self.subTest(kind=kind, unknown_property=True):
                item = copy.deepcopy(self.valid[kind])
                item["unexpected"] = True
                self.assertFalse(self.validators[kind].is_valid(item))

    def test_kind_specific_fields_are_required(self):
        fields = {
            "subject": ("type",),
            "fact": ("subjectId", "predicate", "value"),
            "evidence": ("subjectId", "capability"),
        }
        for kind, required in fields.items():
            for field in required:
                with self.subTest(kind=kind, missing=field):
                    item = copy.deepcopy(self.valid[kind])
                    del item[field]
                    self.assertFalse(self.validators[kind].is_valid(item))

    def test_nested_metadata_rejects_unknown_fields(self):
        for kind in KINDS:
            for field in ("scope", "provenance"):
                with self.subTest(kind=kind, field=field):
                    item = copy.deepcopy(self.valid[kind])
                    item[field]["unknown"] = "unexpected"
                    self.assertFalse(self.validators[kind].is_valid(item))

    def test_evidence_context_and_fact_references(self):
        for field in ("productId", "environment", "targetRevision"):
            with self.subTest(missing=field):
                item = copy.deepcopy(self.valid["evidence"])
                del item["scope"][field]
                self.assertFalse(self.validators["evidence"].is_valid(item))
        item = copy.deepcopy(self.valid["evidence"])
        item["factIds"] = ["fact:encryption", "fact:encryption"]
        self.assertFalse(self.validators["evidence"].is_valid(item))

    def test_fact_json_values_preserve_null_false_and_zero(self):
        for value in (None, False, 0, "", [], {"enabled": False}):
            with self.subTest(value=value):
                item = copy.deepcopy(self.valid["fact"])
                item["value"] = value
                self.assertTrue(self.validators["fact"].is_valid(item))


if __name__ == "__main__":
    unittest.main()

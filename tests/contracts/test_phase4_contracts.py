"""Exercise the accepted contract subset, official schemas and legacy bridge."""

import copy
import importlib.util
import sys
import unittest
from pathlib import Path

from jsonschema import ValidationError

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services/api"))
from app.git_source import GitSnapshot  # noqa: E402
from app.provider_pack import load_provider_pack  # noqa: E402
from app.rule_engine import evaluate_assertions  # noqa: E402

spec = importlib.util.spec_from_file_location(
    "phase4_examples", ROOT / "contracts/phase4/validate_examples.py"
)
contracts = importlib.util.module_from_spec(spec)
spec.loader.exec_module(contracts)
EXAMPLES = ROOT / "contracts/phase4/examples"


class Phase4ContractsTest(unittest.TestCase):
    def setUp(self):
        self.profile = contracts.read(EXAMPLES / "profiles/application-baseline.json")
        self.catalog = contracts.read(EXAMPLES / "catalogs/application.json")
        self.bindings = contracts.read(EXAMPLES / "checks/application.json")

    def resolve(self):
        return contracts.resolve_example_profile(
            self.profile,
            {"catalogs/application.json": self.catalog},
            profile_path="profiles/application-baseline.json",
        )

    def test_official_schemas_and_complete_local_examples(self):
        checks = contracts.check_examples()
        self.assertEqual(len(checks), 2)
        self.assertEqual(
            checks[1]["assertions"][0]["allowed"], ["MIT", "Apache-2.0", "ISC"]
        )
        self.assertEqual(
            evaluate_assertions(
                checks[0]["assertions"], {"auth_required": True}
            ).truth.value,
            "PASS",
        )
        self.assertEqual(
            evaluate_assertions(
                checks[0]["assertions"], {"auth_required": False}
            ).truth.value,
            "FAIL",
        )

    def test_native_profile_parameter_changes_reach_existing_rule_engine(self):
        self.profile["profile"]["modify"]["set-parameters"].append(
            {"param-id": "auth-required", "values": ["false"]}
        )
        checks = contracts.compile_example_bindings(self.bindings, self.resolve())
        self.assertIs(checks[0]["assertions"][0]["expected"], False)
        self.assertEqual(
            evaluate_assertions(
                checks[0]["assertions"], {"auth_required": True}
            ).truth.value,
            "FAIL",
        )

    def test_schema_valid_but_unsupported_profile_is_explicitly_rejected(self):
        self.profile["profile"]["imports"][0] = {
            "href": "../catalogs/application.json",
            "include-all": {},
        }
        contracts.validate(
            self.profile, ROOT / "contracts/oscal/1.2.3/oscal_profile_schema.json"
        )
        with self.assertRaisesRegex(ValueError, "explicit"):
            self.resolve()

    def test_imports_stay_in_the_same_pinned_snapshot(self):
        for href in (
            "https://example.com/catalog.json",
            "../../escape.json",
            "../catalogs/application.json?ref=main",
            "../catalogs/%61pplication.json",
        ):
            with self.subTest(href=href):
                self.profile["profile"]["imports"][0]["href"] = href
                with self.assertRaises(ValueError):
                    self.resolve()

    def test_duplicate_unknown_controls_and_missing_parameters_are_not_ignored(self):
        self.profile["profile"]["imports"][0]["include-controls"][0]["with-ids"].append(
            "MISSING-001"
        )
        with self.assertRaisesRegex(ValueError, "does not exist"):
            self.resolve()
        self.setUp()
        group = self.catalog["catalog"]["groups"][0]
        group["controls"].append(copy.deepcopy(group["controls"][0]))
        with self.assertRaisesRegex(ValueError, "duplicate"):
            self.resolve()
        self.setUp()
        self.profile["profile"]["modify"]["set-parameters"][0]["param-id"] = "missing"
        with self.assertRaisesRegex(ValueError, "parameter"):
            self.resolve()

    def test_excluded_control_parameter_is_not_imported(self):
        self.profile["profile"]["imports"][0]["include-controls"][0]["with-ids"] = [
            "SEC-API-001"
        ]
        with self.assertRaisesRegex(ValueError, "parameter"):
            self.resolve()
        del self.profile["profile"]["modify"]
        resolved = self.resolve()
        checks = contracts.compile_example_bindings(self.bindings, resolved)
        self.assertEqual([c["id"] for c in checks], ["SEC-API-001"])

    def test_resource_identity_is_not_the_document_uuid(self):
        previous = self.resolve()["catalog"]
        self.catalog["catalog"]["uuid"] = "00fa9bd1-f5ee-4a4f-9ad6-224597799c33"
        self.assertEqual(self.resolve()["catalog"], previous)
        self.catalog["catalog"]["metadata"]["props"] = []
        with self.assertRaises((ValueError, ValidationError)):
            self.resolve()

    def test_selected_controls_without_bindings_remain_in_the_profile(self):
        resolved = self.resolve()
        self.bindings["spec"]["controls"] = self.bindings["spec"]["controls"][1:]
        checks = contracts.compile_example_bindings(self.bindings, resolved)
        self.assertEqual(
            [c["id"] for c in resolved["controls"]], ["SEC-API-001", "PY-LIC-001"]
        )
        self.assertEqual([c["id"] for c in checks], ["PY-LIC-001"])

    def test_binding_conflict_and_unresolved_parameter_are_rejected(self):
        resolved = self.resolve()
        self.bindings["spec"]["catalog"]["version"] = "2.0.0"
        with self.assertRaisesRegex(ValueError, "different catalog"):
            contracts.compile_example_bindings(self.bindings, resolved)
        self.setUp()
        self.bindings["spec"]["controls"][0]["assertions"][0]["expected"] = True
        with self.assertRaises(ValidationError):
            contracts.compile_example_bindings(self.bindings, resolved)

    def test_binding_operators_and_operands_have_explicit_schemas(self):
        resolved = self.resolve()
        for rule in (
            {"operator": "equals", "path": "auth_required"},
            {
                "operator": "equals",
                "path": "auth_required",
                "expectedParamter": "auth-required",
            },
            {"operator": "exists", "path": "$.unsafe"},
            {"operator": "execute", "path": "auth_required"},
            {"operator": "any", "assertions": []},
            {"operator": "spdx-allowlist", "path": "licenseExpression", "allowed": []},
        ):
            with self.subTest(rule=rule):
                self.bindings["spec"]["controls"][0]["assertions"] = [rule]
                with self.assertRaises(ValidationError):
                    contracts.compile_example_bindings(self.bindings, resolved)

    def test_two_manifest_paths_in_one_repository_have_distinct_sources(self):
        source = contracts.read(EXAMPLES / "sources/evidence-example.json")
        other = contracts.read(EXAMPLES / "sources/evidence-second.json")
        for value in (source, other):
            contracts.validate(
                value, ROOT / "contracts/phase4/resource-source.schema.json"
            )
            pack = contracts.read(EXAMPLES / value["spec"]["manifestPath"])
            self.assertEqual(pack["metadata"]["id"], value["spec"]["expected"]["id"])
        self.assertEqual(source["spec"]["repository"], other["spec"]["repository"])
        self.assertNotEqual(
            source["spec"]["manifestPath"], other["spec"]["manifestPath"]
        )
        for path in (
            "../escape.json",
            "/absolute.json",
            "C:/drive.json",
            "a//b.json",
            "%2e%2e/escape.json",
            "a\\b.json",
        ):
            with self.subTest(path=path):
                other["spec"]["manifestPath"] = path
                with self.assertRaises(ValidationError):
                    contracts.validate(
                        other, ROOT / "contracts/phase4/resource-source.schema.json"
                    )

    def test_unicode_token_patterns_in_official_schema_are_enforced(self):
        self.catalog["catalog"]["groups"][0]["controls"][0]["id"] = "invalid control id"
        with self.assertRaises(ValidationError):
            contracts.validate(
                self.catalog, ROOT / "contracts/oscal/1.2.3/oscal_catalog_schema.json"
            )

    def test_workspace_needs_explicit_valid_scope_ids(self):
        value = contracts.read(EXAMPLES / "workspace.json")
        del value["defaultOwnerTeamId"]
        with self.assertRaises(ValidationError):
            contracts.validate(value, ROOT / "contracts/phase4/workspace.schema.json")
        value["defaultOwnerTeamId"] = "first-team"
        with self.assertRaises(ValidationError):
            contracts.validate(value, ROOT / "contracts/phase4/workspace.schema.json")

    def test_existing_provider_contract_and_local_schemas_still_validate(self):
        folder = EXAMPLES / "evidence/example"
        files = {
            str(p.relative_to(folder)).replace("\\", "/"): p.read_bytes()
            for p in folder.rglob("*.json")
        }
        files["provider.yaml"] = files.pop("provider.json")
        pack = load_provider_pack(GitSnapshot("a" * 40, files))
        self.assertEqual(pack["manifest"]["runtime"]["kind"], "approved-container")
        unpinned = contracts.read(folder / "provider.json")
        unpinned["runtime"]["image"] = "registry.example/auth-example:latest"
        with self.assertRaises(ValidationError):
            contracts.validate(
                unpinned, ROOT / "contracts/v1/evidence-provider-pack.schema.json"
            )


if __name__ == "__main__":
    unittest.main()

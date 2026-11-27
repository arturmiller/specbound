"""Weak copyleft passes only for a declared, verifiably unmodified library."""

import unittest

from app.rule_engine import RuleTruth, evaluate_assertions

BASE = {
    "operator": "spdx-allowlist",
    "path": "licenseExpression",
    "allowed": ["MIT"],
    "allowApprovedUse": True,
    "libraryUse": {"control": "PY-LIC-001.1", "allowed": ["LGPL-3.0-only"]},
}
ENHANCEMENT = {
    "operator": "spdx-library-use",
    "path": "licenseExpression",
    "control": "PY-LIC-001.1",
    "allowed": ["LGPL-3.0-only"],
    "baseAllowed": ["MIT"],
}
DECLARED = {
    "implemented": frozenset({"PY-LIC-001.1"}),
    "basis": "Produkt specbound-license (Commit abc1234), Profil license-distribution 1.2.0",
}


def observed(expression, *, source="pypi", hashes_verified=True, coverage="complete"):
    return {
        "licenseExpression": expression,
        "licenseCoverage": coverage,
        "lockedSource": source,
        "artifactHashesVerified": hashes_verified,
        "artifacts": [
            {
                "status": "OBSERVED",
                "artifactSha256": "a" * 64,
                "licenseExpression": expression,
            }
        ],
    }


def evaluate(rule, value, library_use=DECLARED):
    return evaluate_assertions(
        [rule], value, require_artifact_licenses=True, library_use=library_use
    )


class BaseControlLibraryUseTest(unittest.TestCase):
    def test_declared_unmodified_library_passes_and_names_its_basis(self):
        decision = evaluate(BASE, observed("LGPL-3.0-only"))
        self.assertEqual(decision.truth, RuleTruth.PASS)
        self.assertIn("PY-LIC-001.1", decision.reason)
        self.assertIn("specbound-license", decision.reason)

    def test_undeclared_library_use_fails(self):
        decision = evaluate(
            BASE,
            observed("LGPL-3.0-only"),
            {"implemented": frozenset(), "basis": DECLARED["basis"]},
        )
        self.assertEqual(decision.truth, RuleTruth.FAIL)
        self.assertIn("erklärt", decision.reason)
        self.assertEqual(
            evaluate(BASE, observed("LGPL-3.0-only"), None).truth, RuleTruth.FAIL
        )

    def test_modified_or_non_pypi_artifacts_fail(self):
        for value in (
            observed("LGPL-3.0-only", hashes_verified=False),
            observed("LGPL-3.0-only", source="git"),
            {
                key: item
                for key, item in observed("LGPL-3.0-only").items()
                if key != "artifactHashesVerified"
            },
        ):
            with self.subTest(value=value):
                decision = evaluate(BASE, value)
                self.assertEqual(decision.truth, RuleTruth.FAIL)
                self.assertIn("PyPI", decision.reason)

    def test_license_outside_both_lists_still_fails(self):
        self.assertEqual(evaluate(BASE, observed("GPL-3.0-only")).truth, RuleTruth.FAIL)

    def test_base_license_passes_without_a_declaration(self):
        self.assertEqual(evaluate(BASE, observed("MIT"), None).truth, RuleTruth.PASS)

    def test_rule_without_library_use_ignores_a_declaration(self):
        rule = {key: value for key, value in BASE.items() if key != "libraryUse"}
        self.assertEqual(
            evaluate(rule, observed("LGPL-3.0-only")).truth, RuleTruth.FAIL
        )

    def test_incomplete_evidence_never_uses_the_library_exception(self):
        value = observed("LGPL-3.0-only", coverage="incomplete")
        self.assertEqual(evaluate(BASE, value).truth, RuleTruth.FAIL)


class EnhancementControlTest(unittest.TestCase):
    def test_package_that_needs_the_exception_passes_when_declared(self):
        decision = evaluate(ENHANCEMENT, observed("LGPL-3.0-only"))
        self.assertEqual(decision.truth, RuleTruth.PASS)
        self.assertIn("specbound-license", decision.reason)

    def test_package_that_needs_the_exception_fails_without_declaration(self):
        decision = evaluate(ENHANCEMENT, observed("LGPL-3.0-only"), None)
        self.assertEqual(decision.truth, RuleTruth.FAIL)

    def test_package_outside_the_exception_is_not_applicable(self):
        for expression in ("MIT", "GPL-3.0-only"):
            with self.subTest(expression=expression):
                decision = evaluate(ENHANCEMENT, observed(expression))
                self.assertEqual(decision.truth, RuleTruth.NOT_APPLICABLE)
                self.assertTrue(decision.reason)

    def test_incomplete_evidence_is_unknown(self):
        value = observed("LGPL-3.0-only", coverage="incomplete")
        self.assertEqual(evaluate(ENHANCEMENT, value).truth, RuleTruth.UNKNOWN)

    def test_operator_requires_locked_artifact_evidence(self):
        decision = evaluate_assertions([ENHANCEMENT], observed("LGPL-3.0-only"))
        self.assertEqual(decision.truth, RuleTruth.UNKNOWN)


class NotApplicableCombinationTest(unittest.TestCase):
    def test_not_applicable_does_not_hide_a_pass_or_a_failure(self):
        mit = {
            "operator": "spdx-allowlist",
            "path": "licenseExpression",
            "allowed": ["MIT"],
        }
        value = observed("MIT")
        self.assertEqual(
            evaluate_assertions(
                [ENHANCEMENT, mit], value, require_artifact_licenses=True
            ).truth,
            RuleTruth.PASS,
        )
        self.assertEqual(
            evaluate_assertions(
                [ENHANCEMENT, {**mit, "allowed": ["ISC"]}],
                value,
                require_artifact_licenses=True,
            ).truth,
            RuleTruth.FAIL,
        )
        self.assertEqual(
            evaluate_assertions(
                [{"operator": "any", "assertions": [ENHANCEMENT, mit]}],
                value,
                require_artifact_licenses=True,
            ).truth,
            RuleTruth.PASS,
        )


if __name__ == "__main__":
    unittest.main()

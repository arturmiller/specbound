"""The small rule language is conservative and has type-safe JSON semantics."""

import unittest

from app.rule_engine import RuleTruth, evaluate_assertions


class RuleEngineTest(unittest.TestCase):
    def evaluate(self, assertion, value):
        return evaluate_assertions([assertion], value).truth

    def test_spdx_policy_evaluates_the_actual_expression_conservatively(self):
        rule = {"operator": "spdx-allowlist", "path": "licenseExpression", "allowed": ["MIT", "Apache-2.0"]}
        for expression, expected in (
            ("MIT", RuleTruth.PASS),
            ("GPL-3.0-only", RuleTruth.FAIL),
            ("MIT OR GPL-3.0-only", RuleTruth.PASS),
            ("MIT AND GPL-3.0-only", RuleTruth.FAIL),
            ("LicenseRef-Unverified", RuleTruth.UNKNOWN),
            (None, RuleTruth.UNKNOWN),
        ):
            with self.subTest(expression=expression):
                self.assertEqual(self.evaluate(rule, {"licenseExpression": expression}), expected)
        self.assertEqual(self.evaluate({**rule, "allowed": []}, {"licenseExpression": "MIT"}), RuleTruth.UNKNOWN)

    def test_equals_is_type_safe_and_missing_is_unknown(self):
        rule = {"operator": "equals", "path": "publicly_reachable", "expected": False}
        self.assertEqual(
            self.evaluate(rule, {"publicly_reachable": False}), RuleTruth.PASS
        )
        self.assertEqual(
            self.evaluate(rule, {"publicly_reachable": True}), RuleTruth.FAIL
        )
        self.assertEqual(self.evaluate(rule, {"publicly_reachable": 0}), RuleTruth.FAIL)
        self.assertEqual(self.evaluate(rule, {}), RuleTruth.UNKNOWN)

    def test_exists_distinguishes_null_from_absence(self):
        rule = {"operator": "exists", "path": "nested.value"}
        self.assertEqual(
            self.evaluate(rule, {"nested": {"value": None}}), RuleTruth.PASS
        )
        self.assertEqual(self.evaluate(rule, {"nested": {}}), RuleTruth.FAIL)
        self.assertEqual(self.evaluate(rule, {"nested": 1}), RuleTruth.UNKNOWN)

    def test_all_and_any_preserve_indeterminate_results(self):
        yes = {"operator": "equals", "path": "a", "expected": True}
        no = {"operator": "equals", "path": "b", "expected": True}
        missing = {"operator": "equals", "path": "c", "expected": True}
        value = {"a": True, "b": False}
        for operator, children, expected in (
            ("all", [yes, missing], RuleTruth.UNKNOWN),
            ("all", [no, missing], RuleTruth.FAIL),
            ("any", [yes, missing], RuleTruth.PASS),
            ("any", [no, missing], RuleTruth.UNKNOWN),
        ):
            with self.subTest(operator=operator, expected=expected):
                self.assertEqual(
                    self.evaluate(
                        {"operator": operator, "assertions": children}, value
                    ),
                    expected,
                )

    def test_unsupported_or_malformed_rules_cannot_pass(self):
        for rule in (
            {"operator": "shell"},
            {"operator": "all", "assertions": []},
            {"operator": "equals", "path": "a"},
            {"operator": "exists", "path": "a..b"},
        ):
            with self.subTest(rule=rule):
                self.assertEqual(self.evaluate(rule, {"a": True}), RuleTruth.UNKNOWN)


if __name__ == "__main__":
    unittest.main()

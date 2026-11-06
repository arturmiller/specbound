import unittest

from app.assessment import (
    Applicability,
    AssessmentResult,
    AssessmentStatus,
    RuleOutcome,
    determine_assessment,
)


class AssessmentStateTest(unittest.TestCase):
    def test_missing_evidence_is_unknown_even_with_a_rule_outcome(self):
        for outcome in RuleOutcome:
            with self.subTest(outcome=outcome):
                result = determine_assessment(
                    applicability=Applicability.APPLICABLE, outcome=outcome, outcome_reason="result"
                )
                self.assertEqual(result.status, AssessmentStatus.UNKNOWN)
                self.assertEqual(result.reason, "Nachweise fehlen")

    def test_not_applicable_needs_documented_scope(self):
        for reason in (None, "", "   "):
            with self.subTest(reason=reason):
                result = determine_assessment(applicability=Applicability.NOT_APPLICABLE, scope_reason=reason)
                self.assertEqual(result.status, AssessmentStatus.UNKNOWN)
                self.assertEqual(result.reason, "Geltungsbereich nicht dokumentiert")
        result = determine_assessment(applicability=Applicability.NOT_APPLICABLE, scope_reason="Nur Datenbanken")
        self.assertEqual(result.status, AssessmentStatus.NOT_APPLICABLE)
        self.assertEqual(result.scope_reason, "Nur Datenbanken")

    def test_unknown_scope_cannot_become_pass(self):
        result = determine_assessment(
            applicability=Applicability.UNKNOWN,
            evidence_ids=("ev:1",),
            outcome=RuleOutcome.PASS,
            outcome_reason="verified",
        )
        self.assertEqual(result.status, AssessmentStatus.UNKNOWN)

    def test_rule_result_requires_evidence_and_reason(self):
        for outcome, expected in ((RuleOutcome.PASS, AssessmentStatus.PASS), (RuleOutcome.FAIL, AssessmentStatus.FAIL)):
            with self.subTest(outcome=outcome):
                result = determine_assessment(
                    applicability=Applicability.APPLICABLE,
                    evidence_ids=("ev:1",),
                    outcome=outcome,
                    outcome_reason="Geprüft",
                )
                self.assertEqual((result.status, result.reason, result.evidence_ids), (expected, "Geprüft", ("ev:1",)))
        for outcome, reason in ((None, None), (RuleOutcome.PASS, " ")):
            result = determine_assessment(
                applicability=Applicability.APPLICABLE, evidence_ids=("ev:1",), outcome=outcome, outcome_reason=reason
            )
            self.assertEqual(result.status, AssessmentStatus.UNKNOWN)

    def test_direct_construction_rejects_invalid_results(self):
        for status in (AssessmentStatus.PASS, AssessmentStatus.FAIL):
            with self.subTest(status=status), self.assertRaises(ValueError):
                AssessmentResult(status, "reason")
        with self.assertRaises(ValueError):
            AssessmentResult(AssessmentStatus.NOT_APPLICABLE, "reason")
        with self.assertRaises(ValueError):
            AssessmentResult(AssessmentStatus.UNKNOWN, " ")
        with self.assertRaises(ValueError):
            determine_assessment(applicability=Applicability.APPLICABLE, evidence_ids=(" ",))


if __name__ == "__main__":
    unittest.main()

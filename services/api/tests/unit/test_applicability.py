"""Resolve a governance target against explicitly classified subjects."""

import unittest

from app.applicability import match_applicability
from app.assessment import Applicability, AssessmentStatus, determine_assessment


class ApplicabilityTest(unittest.TestCase):
    def test_database_matches_api_does_not_and_unknown_is_not_a_negative(self):
        target = {"kind": "database"}
        for kind, expected in (
            ("database", Applicability.APPLICABLE),
            ("api", Applicability.NOT_APPLICABLE),
            ("api.path", Applicability.NOT_APPLICABLE),
            ("unknown", Applicability.UNKNOWN),
            ("unregistered.class", Applicability.UNKNOWN),
        ):
            with self.subTest(kind=kind):
                result = match_applicability(target, {"type": kind})
                self.assertEqual(result.applicability, expected)
                self.assertTrue(result.reason)

    def test_labels_need_confirmed_values_but_known_mismatch_is_decisive(self):
        target = {"kind": "database", "labels": {"environment": "prod", "zone": "eu"}}
        matching = {
            "type": "database",
            "labels": {"environment": "prod", "zone": "eu", "name": "db"},
        }
        self.assertEqual(
            match_applicability(target, matching).applicability,
            Applicability.APPLICABLE,
        )
        self.assertEqual(
            match_applicability(
                target, {"type": "database", "labels": {"environment": "prod"}}
            ).applicability,
            Applicability.UNKNOWN,
        )
        self.assertEqual(
            match_applicability(
                target, {"type": "database", "labels": {"environment": "dev"}}
            ).applicability,
            Applicability.NOT_APPLICABLE,
        )
        self.assertEqual(
            match_applicability(target, {"type": "database"}).applicability,
            Applicability.UNKNOWN,
        )

    def test_unknown_is_propagated_to_assessment(self):
        result = match_applicability({"kind": "database"}, {"type": "unknown"})
        assessment = determine_assessment(
            applicability=result.applicability, scope_reason=result.reason
        )
        self.assertEqual(assessment.status, AssessmentStatus.UNKNOWN)

    def test_unregistered_target_and_malformed_subject_are_unknown(self):
        for subject in ({}, {"type": None}, {"type": "database", "labels": None}):
            target = {"kind": "database", "labels": {"owner": "team"}}
            with self.subTest(subject=subject):
                self.assertEqual(
                    match_applicability(target, subject).applicability,
                    Applicability.UNKNOWN,
                )
        self.assertEqual(
            match_applicability(
                {"kind": "unregistered"}, {"type": "api"}
            ).applicability,
            Applicability.UNKNOWN,
        )

    def test_explicitly_registered_extension_can_be_matched(self):
        target = {"kind": "queue"}
        subject = {"type": "queue"}
        self.assertEqual(
            match_applicability(target, subject).applicability, Applicability.UNKNOWN
        )
        self.assertEqual(
            match_applicability(target, subject, known_types={"queue"}).applicability,
            Applicability.APPLICABLE,
        )


if __name__ == "__main__":
    unittest.main()

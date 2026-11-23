"""Only a complete and unambiguous ScanCode license text becomes evidence."""

import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from app.scancode_license import _detect_license, detect_license


class ScanCodeLicenseTest(unittest.TestCase):
    def setUp(self):
        _detect_license.cache_clear()
        self.addCleanup(_detect_license.cache_clear)
        self.match = SimpleNamespace(
            rule=SimpleNamespace(
                is_license_text=True, license_expression="mit", identifier="mit.LICENSE"
            ),
            score=lambda: 100,
            coverage=lambda: 100,
            matched_text=lambda **options: "License terms\nFinal terms",
            start_line=3,
            end_line=4,
        )
        self.content = b"Copyright (c) 2024 Example\n\nLicense terms\nFinal terms\n"
        self.index = Mock()
        self.index.match.return_value = [self.match]
        scanner = patch(
            "app.scancode_license._scanner",
            return_value=("32.5.0", self.index, lambda value: value.upper()),
        )
        self.mock_scanner = self.enterContext(scanner)

    def test_records_license_version_rule_and_lines_and_reuses_detection(self):
        result = detect_license(self.content)
        self.assertEqual(
            result,
            {
                "licenseExpression": "MIT",
                "licenseDetection": {
                    "tool": "scancode-toolkit",
                    "version": "32.5.0",
                    "rule": "mit.LICENSE",
                    "startLine": 3,
                    "endLine": 4,
                },
            },
        )
        self.assertEqual(detect_license(self.content), result)
        self.index.match.assert_called_once()

    def test_fragments_conflicts_and_additional_terms_are_not_accepted(self):
        self.assertIsNone(detect_license(self.content + b"Additional terms.\n"))
        self.assertIsNone(
            detect_license(self.content.rstrip() + b". Additional terms.\n")
        )
        self.match.rule.is_license_text = False
        self.assertIsNone(detect_license(self.content))
        self.match.rule.is_license_text = True
        self.match.coverage = lambda: 90
        self.assertIsNone(detect_license(self.content + b"\n"))
        self.match.coverage = lambda: 100
        self.index.match.return_value = [self.match, self.match]
        self.assertIsNone(detect_license(self.content + b"\n\n"))

    def test_unavailable_detector_keeps_the_license_unresolved(self):
        self.mock_scanner.return_value = None
        self.assertIsNone(detect_license(self.content))
        self.index.match.assert_not_called()

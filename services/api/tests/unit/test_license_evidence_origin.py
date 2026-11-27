"""License evidence states whether locked artifacts are unmodified PyPI files."""

import unittest

from app.public_license_assessment import _verified_metadata


def package(*, hashes=("a" * 64,), observed=("a" * 64,)):
    return {
        "path": "services/api/uv.lock",
        "name": "psycopg-c",
        "version": "3.3.3",
        "source": "pypi",
        "markers": [],
        "artifactHashes": None if hashes is None else list(hashes),
        "metadata": {
            "status": "OBSERVED",
            "artifacts": [
                {
                    "sourceUrl": f"https://files.pythonhosted.org/packages/ab/{index}.tar.gz",
                    "sourceKind": "distribution-metadata",
                    "artifactSha256": digest,
                    "metadataSha256": "b" * 64,
                    "licenseExpression": "LGPL-3.0-only",
                }
                for index, digest in enumerate(observed)
            ],
        },
    }


class LicenseEvidenceOriginTest(unittest.TestCase):
    def test_locked_hashes_matching_pypi_are_marked_as_verified(self):
        value = _verified_metadata(package())
        self.assertEqual(value["lockedSource"], "pypi")
        self.assertIs(value["artifactHashesVerified"], True)

    def test_differing_or_missing_locked_hashes_are_not_verified(self):
        for case in (
            package(hashes=("c" * 64,)),
            package(hashes=None),
            package(hashes=()),
            package(observed=("a" * 64, "c" * 64)),
        ):
            with self.subTest(hashes=case["artifactHashes"]):
                self.assertIs(_verified_metadata(case)["artifactHashesVerified"], False)


if __name__ == "__main__":
    unittest.main()

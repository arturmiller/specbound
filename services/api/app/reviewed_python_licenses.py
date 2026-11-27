"""License observations reviewed against specific PyPI distribution bytes."""

from dataclasses import dataclass


@dataclass(frozen=True)
class ReviewedLicense:
    expression: str
    metadata_sha256: str
    license_file: str
    license_sha256: str
    source: str


# Keep these records bound to all three identifiers. See the release review
# documentation for the rationale and the upstream declaration for each file.
REVIEWED_PYPI_ARTIFACTS = {
    (
        "boolean-py",
        "5.0",
        "60cbc4bad079753721d32649545505362c754e121570ada4658b852a3a318d95",
    ): ReviewedLicense(
        "BSD-2-Clause",
        "9e43aeae17a73073abee61deb5fb267dfdf0eeb67d6e3123270b52aac5ed87fa",
        "LICENSE.txt",
        "5ea0cdf8cfc824b446cccf597ff6518c3607a659e9804bc75f1261f9c6ac4ada",
        "https://pypi.org/project/boolean.py/5.0/",
    ),
    (
        "certifi",
        "2026.11.20",
        "af1cb240a8133f105aa52684a3a3258339d7f2fd0bd4e2812698ff5cf5588c4e",
    ): ReviewedLicense(
        "MPL-2.0",
        "940f90089b8c6f2bbd0fa6e93a66634289853a5bc1453e9f9b88ae53859a2553",
        "LICENSE",
        "e93716da6b9c0d5a4a1df60fe695b370f0695603d21f6f83f053e42cfc10caf7",
        "https://pypi.org/project/certifi/2026.11.20/",
    ),
    (
        "python-dateutil",
        "2.9.0.post0",
        "37dd54208da7e1cd875388217d5e00ebd4179249f90fb72437e91a35459a0ad3",
    ): ReviewedLicense(
        "BSD-3-Clause",
        "d19fba9fe39f32faf5f738882f3f368893b0a5f1ad2fe33e20920657cb0b52b1",
        "LICENSE",
        "ba00f51a0d92823b5a1cde27d8b5b9d2321e67ed8da9bc163eff96d5e17e577e",
        "https://pypi.org/project/python-dateutil/2.9.0.post0/",
    ),
    (
        "python-dateutil",
        "2.9.0.post0",
        "a8b2bc7bffae282281c8140a97d3aa9c14da0b136dfe83f850eea9a5f7470427",
    ): ReviewedLicense(
        "BSD-3-Clause",
        "a9d436da322be808332f98d88325998e87cb693a678a9969feb4cfad729a6e93",
        "python_dateutil-2.9.0.post0.dist-info/LICENSE",
        "ba00f51a0d92823b5a1cde27d8b5b9d2321e67ed8da9bc163eff96d5e17e577e",
        "https://pypi.org/project/python-dateutil/2.9.0.post0/",
    ),
}

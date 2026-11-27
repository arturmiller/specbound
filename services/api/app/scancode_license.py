"""Identify complete license texts in already verified package files."""

import hashlib
import logging
import re
import sys
from contextlib import redirect_stdout
from functools import lru_cache
from importlib.metadata import PackageNotFoundError, version
from threading import Lock
from time import time

from app.license_policy import canonical_license_id

MAX_LICENSE_BYTES = 128 * 1024
logger = logging.getLogger(__name__)
_scan_lock = Lock()
_COPYRIGHT = re.compile(r"copyright\s+\(c\)\s+[0-9]{4}[0-9, -]*\s+.+", re.IGNORECASE)
_MIT_HEADINGS = frozenset({"mit license", "the mit license (mit)"})
# Whitespace-normalized SPDX MIT conditions, starting at the grant.
# https://spdx.org/licenses/MIT.html
_MIT_TERMS_SHA256 = "fe2a9817987f862eaced948f0468c7f51d2fedfc48c5c505b246a49a3870e9a5"


def _standard_preamble(lines, license_id):
    return all(
        not line.strip()
        or _COPYRIGHT.fullmatch(line.strip())
        or (license_id == "MIT" and line.strip().casefold() in _MIT_HEADINGS)
        for line in lines
    )


def matches_mit_terms(content):
    if not content or len(content) > MAX_LICENSE_BYTES:
        return False
    try:
        text = content.decode("utf-8-sig")
    except UnicodeError:
        return False
    heading, grant, remainder = text.partition("Permission is hereby granted")
    if not grant or (heading and not heading.endswith(("\n", "\r"))):
        return False
    terms = " ".join((grant + remainder).split()).encode("utf-8")
    return (
        _standard_preamble(heading.splitlines(), "MIT")
        and hashlib.sha256(terms).hexdigest() == _MIT_TERMS_SHA256
    )


@lru_cache(maxsize=1)
def _scanner():
    try:
        release = version("scancode-toolkit")
    except PackageNotFoundError:
        return None
    try:
        from licensedcode.cache import build_spdx_license_expression, get_index

        return release, get_index(), build_spdx_license_expression
    except Exception:
        logger.warning("ScanCode license detector failed to initialize")
        return None


def detect_license(content):
    if not content or len(content) > MAX_LICENSE_BYTES:
        return None
    # Loading and matching against the index takes place once at a time.
    # Third-party diagnostics must stay out of the runner's JSON response.
    with _scan_lock, redirect_stdout(sys.stderr):
        return _detect_license(content)


@lru_cache(maxsize=128)
def _detect_license(content):
    scanner = _scanner()
    if scanner is None:
        return None
    release, index, to_spdx = scanner
    try:
        text = content.decode("utf-8-sig")
        matches = index.match(query_string=text, deadline=time() + 3)
        if len(matches) != 1:
            return None
        match = matches[0]
        if (
            not match.rule.is_license_text
            or match.score() != 100
            or match.coverage() != 100
        ):
            return None
        license_id = canonical_license_id(to_spdx(match.rule.license_expression))
        matched_text = match.matched_text(highlight_not_matched="")
    except UnicodeError:
        return None
    except Exception:
        logger.warning("ScanCode license detection failed")
        return None
    if not license_id:
        return None
    lines = text.splitlines()
    start, end = match.start_line, match.end_line
    # A complete rule match may still be an excerpt of a file with additional
    # terms. Allow only whitespace, copyright notices and standard MIT headings
    # outside the match.
    if (
        not 1 <= start <= end <= len(lines)
        or any(line.strip() for line in lines[end:])
        or not _standard_preamble(lines[: start - 1], license_id)
        or re.findall(r"[^\W_]+", "\n".join(lines[start - 1 : end]))
        != re.findall(r"[^\W_]+", matched_text)
    ):
        return None
    return {
        "licenseExpression": license_id,
        "licenseDetection": {
            "tool": "scancode-toolkit",
            "version": release,
            "rule": match.rule.identifier,
            "startLine": start,
            "endLine": end,
        },
    }

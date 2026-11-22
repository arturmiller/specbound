"""Evaluate SPDX expressions against an explicit, conservative allowlist."""

import re
from functools import lru_cache

from license_expression import (
    AND,
    OR,
    ExpressionError,
    LicenseSymbol,
    LicenseWithExceptionSymbol,
    get_spdx_licensing,
)

MAX_EXPRESSION = 2048
DEFAULT_ALLOWED = frozenset(
    {"MIT", "Apache-2.0", "BSD-2-Clause", "BSD-3-Clause", "ISC"}
)
LEGACY_LICENSE_NAMES = {
    "mit license": "MIT",
    "apache license 2.0": "Apache-2.0",
}


@lru_cache(maxsize=1)
def _licensing():
    return get_spdx_licensing()


def canonical_license_id(value):
    """Accept a single SPDX identifier with the same spelling apart from case."""
    if len(value) > MAX_EXPRESSION or not re.fullmatch(
        r"[A-Za-z0-9][A-Za-z0-9.-]*", value
    ):
        return None
    try:
        parsed = _licensing().parse(value, validate=True, strict=True)
    except (ExpressionError, ValueError, TypeError, RecursionError):
        return None
    if isinstance(parsed, LicenseSymbol) and str(parsed).casefold() == value.casefold():
        return str(parsed)
    return None


def _decision(node, allowed, depth=0):
    if depth > 32:
        return "UNKNOWN"
    if isinstance(node, LicenseWithExceptionSymbol):
        # An exception changes the terms; never silently accept the base license.
        return "PASS" if str(node) in allowed else "UNKNOWN"
    if isinstance(node, LicenseSymbol):
        return "PASS" if str(node) in allowed else "FAIL"
    if isinstance(node, (AND, OR)):
        outcomes = [_decision(child, allowed, depth + 1) for child in node.args]
        if isinstance(node, AND):
            return (
                "FAIL"
                if "FAIL" in outcomes
                else "UNKNOWN"
                if "UNKNOWN" in outcomes
                else "PASS"
            )
        return (
            "PASS"
            if "PASS" in outcomes
            else "UNKNOWN"
            if "UNKNOWN" in outcomes
            else "FAIL"
        )
    return "UNKNOWN"


def evaluate_license(expression, allowed=DEFAULT_ALLOWED):
    """Evaluate a valid SPDX expression; unknown identifiers never imply PASS."""
    if (
        not isinstance(expression, str)
        or not expression.strip()
        or len(expression) > MAX_EXPRESSION
    ):
        return "UNKNOWN"
    try:
        parsed = _licensing().parse(expression, validate=True, strict=True)
        return _decision(parsed, frozenset(allowed))
    except (ExpressionError, ValueError, TypeError, RecursionError):
        # This also includes LicenseRef identifiers that the SPDX catalog does
        # not know, malformed expressions and unrecognised license exceptions.
        return "UNKNOWN"


def artifact_license_outcomes(value, allowed):
    """Return the decisions for locked artifacts, retaining any evidence gaps."""
    if not isinstance(value, dict):
        return {"UNKNOWN"}
    if "licenseCoverage" not in value:
        return {evaluate_license(value.get("licenseExpression"), allowed)}
    outcomes = {
        evaluate_license(item.get("licenseExpression"), allowed)
        if item.get("status") == "OBSERVED"
        else "UNKNOWN"
        for item in value.get("artifacts", [])
    }
    if value["licenseCoverage"] != "complete" or not outcomes:
        outcomes.add("UNKNOWN")
    return outcomes

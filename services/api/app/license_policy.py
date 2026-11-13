"""Evaluate SPDX expressions against an explicit, conservative allowlist."""

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


@lru_cache(maxsize=1)
def _licensing():
    return get_spdx_licensing()


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

"""A bounded, non-executable three-valued rule language over JSON observations."""

import re
from dataclasses import dataclass
from enum import Enum

from app.license_policy import artifact_license_outcomes, evaluate_license


class RuleTruth(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    UNKNOWN = "UNKNOWN"
    NOT_APPLICABLE = "NOT_APPLICABLE"


@dataclass(frozen=True)
class RuleDecision:
    truth: RuleTruth
    reason: str
    basis: str | None = None


PATH = re.compile(r"^[A-Za-z_][A-Za-z0-9_-]*(?:\.[A-Za-z_][A-Za-z0-9_-]*)*$")


def _same_json(left, right, depth=0):
    if depth > 64:
        raise ValueError("JSON nesting exceeds limit")
    if isinstance(left, bool) or isinstance(right, bool):
        return type(left) is type(right) and left == right
    if isinstance(left, (int, float)) and isinstance(right, (int, float)):
        return left == right
    if type(left) is not type(right):
        return False
    if isinstance(left, dict):
        return left.keys() == right.keys() and all(
            _same_json(left[key], right[key], depth + 1) for key in left
        )
    if isinstance(left, list):
        return len(left) == len(right) and all(
            _same_json(a, b, depth + 1) for a, b in zip(left, right)
        )
    return left == right


def _passed(reason, decisions):
    basis = next((item.basis for item in decisions if item.basis), None)
    return RuleDecision(
        RuleTruth.PASS, f"{reason}: {basis}" if basis else reason, basis
    )


def _combine(operator, decisions):
    # NOT_APPLICABLE is neutral; it is only the result if nothing else applies.
    applicable = [
        item for item in decisions if item.truth is not RuleTruth.NOT_APPLICABLE
    ]
    if not applicable:
        return RuleDecision(RuleTruth.NOT_APPLICABLE, decisions[0].reason)
    if operator == "all":
        failure = next(
            (item for item in applicable if item.truth is RuleTruth.FAIL), None
        )
        if failure:
            return RuleDecision(
                RuleTruth.FAIL,
                f"Mindestens eine Regel ist nicht erfüllt: {failure.reason}",
            )
        if all(item.truth is RuleTruth.PASS for item in applicable):
            return _passed("Alle Regeln sind erfüllt", applicable)
    else:
        passed = [item for item in applicable if item.truth is RuleTruth.PASS]
        if passed:
            return _passed("Mindestens eine Regel ist erfüllt", passed)
        if all(item.truth is RuleTruth.FAIL for item in applicable):
            return RuleDecision(RuleTruth.FAIL, "Keine Regel ist erfüllt")
    incomplete = next(
        (item for item in decisions if item.truth is RuleTruth.UNKNOWN), None
    )
    return RuleDecision(
        RuleTruth.UNKNOWN,
        f"Regelergebnis ist unvollständig: {incomplete.reason}"
        if incomplete
        else "Regelergebnis ist unvollständig",
    )


def _valid_list(allowed):
    return (
        isinstance(allowed, list)
        and 0 < len(allowed) <= 100
        and all(isinstance(item, str) and item and len(item) <= 200 for item in allowed)
    )


def _library_use_failure(value, control, library_use):
    """Why a declared library exception cannot be used, or None if it can."""
    implemented = (library_use or {}).get("implemented") or frozenset()
    if control not in implemented:
        return f"Das Produkt erklärt die Bibliotheksnutzung nach {control} nicht"
    if (
        value.get("licenseCoverage") != "complete"
        or value.get("lockedSource") != "pypi"
        or value.get("artifactHashesVerified") is not True
    ):
        return "Unveränderte Paketdateien aus PyPI sind nicht belegt"
    return None


def _library_use_pass(control, library_use):
    basis = (library_use or {}).get("basis")
    reason = (
        f"Lizenz ist über {control} bei unveränderter Bibliotheksnutzung freigegeben"
    )
    if isinstance(basis, str) and basis:
        reason = f"{reason} ({basis[:500]})"
    return RuleDecision(RuleTruth.PASS, reason, reason)


def evaluate_assertions(
    assertions, value, *, require_artifact_licenses=False, library_use=None
):
    """Root assertions are combined with all; unknown input never becomes PASS.

    ``library_use`` carries the product's declared control implementations
    (``implemented``) and a human-readable ``basis`` for the explanation.
    """
    budget = [256]

    def evaluate(rule, depth):
        budget[0] -= 1
        if budget[0] < 0 or depth > 16 or not isinstance(rule, dict):
            return RuleDecision(RuleTruth.UNKNOWN, "Regel ungültig oder zu komplex")
        operator = rule.get("operator")
        if operator in ("all", "any"):
            children = rule.get("assertions")
            if not isinstance(children, list) or not 0 < len(children) <= 32:
                return RuleDecision(RuleTruth.UNKNOWN, "Regelgruppe ist ungültig")
            return _combine(
                operator, [evaluate(child, depth + 1) for child in children]
            )
        if operator not in ("equals", "exists", "spdx-allowlist", "spdx-library-use"):
            return RuleDecision(RuleTruth.UNKNOWN, "Operator wird nicht unterstützt")
        path = rule.get("path")
        if not isinstance(path, str) or len(path) > 500 or not PATH.fullmatch(path):
            return RuleDecision(RuleTruth.UNKNOWN, "Regelpfad ist ungültig")
        if operator == "equals" and "expected" not in rule:
            return RuleDecision(RuleTruth.UNKNOWN, "Vergleichswert fehlt")
        current = value
        for segment in path.split("."):
            if not isinstance(current, dict):
                return RuleDecision(
                    RuleTruth.UNKNOWN, "Beobachtungsstruktur ist unvollständig"
                )
            if segment not in current:
                if operator == "exists":
                    return RuleDecision(
                        RuleTruth.FAIL, f"Erforderliches Feld {path} fehlt"
                    )
                return RuleDecision(RuleTruth.UNKNOWN, f"Vergleichsfeld {path} fehlt")
            current = current[segment]
        if operator == "exists":
            return RuleDecision(
                RuleTruth.PASS, f"Erforderliches Feld {path} ist vorhanden"
            )
        if operator == "spdx-library-use":
            allowed, base = rule.get("allowed"), rule.get("baseAllowed")
            control = rule.get("control")
            if (
                not _valid_list(allowed)
                or not _valid_list(base)
                or not isinstance(control, str)
                or not control
                or not require_artifact_licenses
                or path != "licenseExpression"
            ):
                return RuleDecision(
                    RuleTruth.UNKNOWN, "Bibliotheksausnahme ist nicht bewertbar"
                )
            outcomes = artifact_license_outcomes(value, base)
            if outcomes == {"PASS"}:
                return RuleDecision(
                    RuleTruth.NOT_APPLICABLE,
                    "Lizenz ist ohne Bibliotheksausnahme freigegeben",
                )
            if "UNKNOWN" in outcomes:
                return RuleDecision(
                    RuleTruth.UNKNOWN,
                    "Lizenznachweis für mindestens eine Paketdatei fehlt oder ist ungeklärt",
                )
            if artifact_license_outcomes(value, [*base, *allowed]) != {"PASS"}:
                return RuleDecision(
                    RuleTruth.NOT_APPLICABLE,
                    "Lizenz fällt nicht unter die Bibliotheksausnahme",
                )
            failure = _library_use_failure(value, control, library_use)
            if failure:
                return RuleDecision(RuleTruth.FAIL, failure)
            return _library_use_pass(control, library_use)
        if operator == "spdx-allowlist":
            allowed = rule.get("allowed")
            if not _valid_list(allowed):
                return RuleDecision(
                    RuleTruth.UNKNOWN, "Lizenzfreigabeliste ist ungültig"
                )
            if require_artifact_licenses and path == "licenseExpression":
                outcomes = artifact_license_outcomes(value, allowed)
                if "UNKNOWN" in outcomes:
                    return RuleDecision(
                        RuleTruth.FAIL,
                        "Lizenznachweis für mindestens eine Paketdatei fehlt oder ist ungeklärt",
                    )
                library = rule.get("libraryUse")
                if (
                    "FAIL" in outcomes
                    and isinstance(library, dict)
                    and _valid_list(library.get("allowed"))
                    and artifact_license_outcomes(
                        value, [*allowed, *library["allowed"]]
                    )
                    == {"PASS"}
                ):
                    failure = _library_use_failure(
                        value, library.get("control"), library_use
                    )
                    if failure:
                        return RuleDecision(
                            RuleTruth.FAIL,
                            f"Lizenzausdruck ist durch die Richtlinie nicht freigegeben; {failure}",
                        )
                    return _library_use_pass(library["control"], library_use)
                outcome = "FAIL" if "FAIL" in outcomes else "PASS"
            else:
                outcome = evaluate_license(current, allowed)
            return RuleDecision(
                RuleTruth(outcome),
                {
                    "PASS": "Lizenzausdruck ist durch die Richtlinie freigegeben",
                    "FAIL": "Lizenzausdruck ist durch die Richtlinie nicht freigegeben",
                    "UNKNOWN": "Lizenzausdruck oder Ausnahme ist nicht eindeutig bewertbar",
                }[outcome],
            )
        try:
            equal = _same_json(current, rule["expected"])
        except (RecursionError, ValueError):
            return RuleDecision(RuleTruth.UNKNOWN, "Vergleich ist zu komplex")
        return RuleDecision(
            RuleTruth.PASS if equal else RuleTruth.FAIL,
            f"Vergleich für {path} stimmt überein"
            if equal
            else f"Vergleich für {path} stimmt nicht überein",
        )

    if not isinstance(assertions, list) or not 0 < len(assertions) <= 32:
        return RuleDecision(RuleTruth.UNKNOWN, "Assertions fehlen oder sind ungültig")
    return _combine("all", [evaluate(rule, 0) for rule in assertions])

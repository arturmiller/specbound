"""A bounded, non-executable three-valued rule language over JSON observations."""

import re
from dataclasses import dataclass
from enum import Enum


class RuleTruth(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class RuleDecision:
    truth: RuleTruth
    reason: str


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


def _combine(operator, decisions):
    if operator == "all":
        failure = next(
            (item for item in decisions if item.truth is RuleTruth.FAIL), None
        )
        if failure:
            return RuleDecision(
                RuleTruth.FAIL,
                f"Mindestens eine Regel ist nicht erfüllt: {failure.reason}",
            )
        if all(item.truth is RuleTruth.PASS for item in decisions):
            return RuleDecision(RuleTruth.PASS, "Alle Regeln sind erfüllt")
    else:
        if any(item.truth is RuleTruth.PASS for item in decisions):
            return RuleDecision(RuleTruth.PASS, "Mindestens eine Regel ist erfüllt")
        if all(item.truth is RuleTruth.FAIL for item in decisions):
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


def evaluate_assertions(assertions, value):
    """Root assertions are combined with all; unknown input never becomes PASS."""
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
        if operator not in ("equals", "exists"):
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

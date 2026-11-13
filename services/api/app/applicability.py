"""Resolve a control target against a known subject classification."""

from dataclasses import dataclass

from app.assessment import Applicability

KNOWN_SUBJECT_TYPES = frozenset({"database", "api", "api.path", "api.schema", "python.package"})


@dataclass(frozen=True)
class ApplicabilityMatch:
    applicability: Applicability
    reason: str


def match_applicability(target, subject, *, known_types=KNOWN_SUBJECT_TYPES):
    """Match exact registered types and labels without guessing missing facts."""
    if not isinstance(target, dict) or not isinstance(subject, dict):
        return ApplicabilityMatch(Applicability.UNKNOWN, "Klassifikation fehlt")
    target_kind, subject_kind = target.get("kind"), subject.get("type")
    if (
        not isinstance(target_kind, str)
        or not isinstance(subject_kind, str)
        or target_kind not in known_types
        or subject_kind not in known_types
    ):
        return ApplicabilityMatch(
            Applicability.UNKNOWN, "Subject-Typ nicht klassifiziert"
        )
    if target_kind != subject_kind:
        return ApplicabilityMatch(
            Applicability.NOT_APPLICABLE, "Subject-Typ stimmt nicht überein"
        )
    required = target.get("labels", {})
    if not isinstance(required, dict) or any(
        not isinstance(key, str) or not isinstance(value, str)
        for key, value in required.items()
    ):
        return ApplicabilityMatch(Applicability.UNKNOWN, "Control-Labels sind ungültig")
    if not required:
        return ApplicabilityMatch(
            Applicability.APPLICABLE, "Subject-Typ stimmt überein"
        )
    labels = subject.get("labels")
    if not isinstance(labels, dict):
        return ApplicabilityMatch(Applicability.UNKNOWN, "Subject-Labels fehlen")
    missing = False
    for key, expected in required.items():
        actual = labels.get(key)
        if not isinstance(actual, str):
            missing = True
        elif actual != expected:
            return ApplicabilityMatch(
                Applicability.NOT_APPLICABLE, "Subject-Label stimmt nicht überein"
            )
    if missing:
        return ApplicabilityMatch(
            Applicability.UNKNOWN, "Erforderliches Subject-Label fehlt"
        )
    return ApplicabilityMatch(
        Applicability.APPLICABLE, "Subject-Typ und Labels stimmen überein"
    )

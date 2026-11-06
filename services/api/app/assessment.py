"""Conservative assessment states; rule evaluation and evidence lookup are separate."""

from dataclasses import dataclass
from enum import Enum


class AssessmentStatus(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    UNKNOWN = "UNKNOWN"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class Applicability(str, Enum):
    APPLICABLE = "APPLICABLE"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    UNKNOWN = "UNKNOWN"


class RuleOutcome(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"


@dataclass(frozen=True)
class AssessmentResult:
    status: AssessmentStatus
    reason: str
    evidence_ids: tuple[str, ...] = ()
    scope_reason: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.status, AssessmentStatus):
            raise ValueError("status must be an AssessmentStatus")
        if not isinstance(self.reason, str) or not self.reason.strip():
            raise ValueError("reason must be a nonempty string")
        if not isinstance(self.evidence_ids, tuple) or any(
            not isinstance(item, str) or not item.strip() for item in self.evidence_ids
        ):
            raise ValueError("evidence_ids must be a tuple of nonempty identifiers")
        if self.status in (AssessmentStatus.PASS, AssessmentStatus.FAIL) and not self.evidence_ids:
            raise ValueError("PASS and FAIL require evidence")
        if self.scope_reason is not None and not isinstance(self.scope_reason, str):
            raise ValueError("scope_reason must be a string")
        if self.status is AssessmentStatus.NOT_APPLICABLE and not (self.scope_reason or "").strip():
            raise ValueError("NOT_APPLICABLE requires a documented scope reason")


def determine_assessment(
    *,
    applicability: Applicability,
    evidence_ids: tuple[str, ...] = (),
    outcome: RuleOutcome | None = None,
    outcome_reason: str | None = None,
    scope_reason: str | None = None,
) -> AssessmentResult:
    """Combine caller-provided scope, evidence references and an already evaluated rule."""
    if not isinstance(applicability, Applicability):
        raise ValueError("applicability must be an Applicability")
    if outcome is not None and not isinstance(outcome, RuleOutcome):
        raise ValueError("outcome must be a RuleOutcome")
    if outcome_reason is not None and not isinstance(outcome_reason, str):
        raise ValueError("outcome_reason must be a string")
    if scope_reason is not None and not isinstance(scope_reason, str):
        raise ValueError("scope_reason must be a string")
    if not isinstance(evidence_ids, tuple) or any(
        not isinstance(item, str) or not item.strip() for item in evidence_ids
    ):
        raise ValueError("evidence_ids must be a tuple of nonempty identifiers")

    if applicability is Applicability.UNKNOWN:
        return AssessmentResult(AssessmentStatus.UNKNOWN, "Geltungsbereich ungeklärt", evidence_ids)
    if applicability is Applicability.NOT_APPLICABLE:
        if not (scope_reason or "").strip():
            return AssessmentResult(AssessmentStatus.UNKNOWN, "Geltungsbereich nicht dokumentiert", evidence_ids)
        return AssessmentResult(AssessmentStatus.NOT_APPLICABLE, scope_reason, evidence_ids, scope_reason)
    if not evidence_ids:
        return AssessmentResult(AssessmentStatus.UNKNOWN, "Nachweise fehlen")
    if outcome is None or not (outcome_reason or "").strip():
        return AssessmentResult(AssessmentStatus.UNKNOWN, "Regelergebnis oder Begründung fehlt", evidence_ids)
    return AssessmentResult(AssessmentStatus(outcome.value), outcome_reason, evidence_ids)

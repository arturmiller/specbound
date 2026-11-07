"""Evaluate one scoped control and retain its outcome and explanation."""

import re
from datetime import datetime, timezone
from urllib.parse import quote
from uuid import uuid4

from sqlalchemy import insert, select
from sqlalchemy.engine import Connection

from app.applicability import match_applicability
from app.assessment import (
    Applicability,
    AssessmentResult,
    AssessmentStatus,
    RuleOutcome,
)
from app.coverage import scan_covers
from app.evidence_records import assess_with_evidence, current_evidence
from app.manifest_io import validate
from app.rule_engine import RuleTruth, evaluate_assertions
from app.tables import products, rule_evaluations, teams


def _serialize(row):
    return {
        "id": row["id"],
        "organizationId": row["organization_id"],
        "productId": row["product_id"],
        "subjectId": row["subject_id"],
        "environment": row["environment"],
        "targetRevision": row["target_revision"],
        "controlId": row["control_id"],
        "governanceRevision": row["governance_revision"],
        "scanId": row["scan_id"],
        "status": row["status"],
        "reason": row["reason"],
        "evidenceIds": row["evidence_ids"],
        "control": row["control"],
        "subject": row["subject"],
        "evaluatedAt": row["evaluated_at"],
    }


def get_evaluation(db: Connection, organization_id, evaluation_id):
    row = (
        db.execute(
            select(rule_evaluations).where(
                rule_evaluations.c.organization_id == organization_id,
                rule_evaluations.c.id == evaluation_id,
            )
        )
        .mappings()
        .one_or_none()
    )
    return _serialize(row) if row is not None else None


def evaluate_and_store(
    db: Connection,
    organization_id,
    scope,
    subject,
    control,
    governance_revision,
    *,
    now,
    scan_id,
    binding_id,
    ref,
):
    """Only trusted scanner output and a pinned, validated control are accepted."""
    if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("A timezone-aware evaluation time is required")
    now = now.astimezone(timezone.utc)
    if not isinstance(governance_revision, str) or not re.fullmatch(
        r"(?:[0-9a-f]{40}|[0-9a-f]{64})", governance_revision
    ):
        raise ValueError("A pinned governance commit is required")
    validate(control, "governance-control.schema.json", "control")
    if (
        not isinstance(subject, dict)
        or not isinstance(subject.get("id"), str)
        or not 0 < len(subject["id"]) <= 500
    ):
        raise ValueError("A subject ID is required")
    if not isinstance(scope, dict) or not all(
        isinstance(scope.get(key), str) and scope[key]
        for key in ("productId", "environment", "targetRevision")
    ):
        raise ValueError("A complete evaluation scope is required")
    if len(scope["environment"]) > 200 or not re.fullmatch(
        r"(?:[0-9a-f]{40}|[0-9a-f]{64}|sha256:[0-9a-f]{64})", scope["targetRevision"]
    ):
        raise ValueError("Invalid evaluation scope")
    owned = db.execute(
        select(products.c.id)
        .select_from(products.join(teams, products.c.owner_team_id == teams.c.id))
        .where(
            products.c.id == scope["productId"],
            teams.c.organization_id == organization_id,
        )
    ).first()
    if owned is None:
        raise LookupError("Product not found in organization")

    subject_scope = subject.get("scope")
    provenance = subject.get("provenance")
    source_prefix = (
        f"repo:{quote(binding_id, safe='')}/" if isinstance(binding_id, str) else None
    )
    valid_source = (
        subject.get("type") in ("api.path", "api.schema")
        and isinstance(subject_scope, dict)
        and subject_scope.get("productId") == scope["productId"]
        and subject_scope.get("targetRevision") == scope["targetRevision"]
        and isinstance(provenance, dict)
        and provenance.get("sourceRevision") == scope["targetRevision"]
        and isinstance(provenance.get("sourceRef"), str)
        and source_prefix is not None
        and provenance["sourceRef"].startswith(source_prefix)
        and scan_covers(
            db,
            scan_id=scan_id,
            product_id=scope["productId"],
            binding_id=binding_id,
            ref=ref,
            expected_commit=scope["targetRevision"],
            not_after=now,
        )
    )
    if not valid_source:
        result = AssessmentResult(
            AssessmentStatus.UNKNOWN, "Quellabdeckung fehlt oder ist unvollständig"
        )
    else:
        match = match_applicability(control["target"], subject)
        if match.applicability is Applicability.UNKNOWN:
            result = AssessmentResult(AssessmentStatus.UNKNOWN, match.reason)
        elif match.applicability is Applicability.NOT_APPLICABLE:
            result = AssessmentResult(
                AssessmentStatus.NOT_APPLICABLE, match.reason, scope_reason=match.reason
            )
        else:
            capability = control["requiredEvidence"]["capability"]
            evidence = current_evidence(
                db, organization_id, scope, subject["id"], capability, now=now
            )
            if len(evidence) != 1:
                result = AssessmentResult(
                    AssessmentStatus.UNKNOWN,
                    "Aktueller Nachweis fehlt oder ist mehrdeutig",
                )
            else:
                decision = evaluate_assertions(
                    control["assertions"], evidence[0]["value"]
                )
                evidence_ids = (evidence[0]["id"],)
                if decision.truth is RuleTruth.UNKNOWN:
                    result = AssessmentResult(
                        AssessmentStatus.UNKNOWN, decision.reason, evidence_ids
                    )
                else:
                    result = assess_with_evidence(
                        db,
                        organization_id,
                        scope,
                        subject["id"],
                        capability,
                        evidence_ids=evidence_ids,
                        now=now,
                        applicability=Applicability.APPLICABLE,
                        outcome=RuleOutcome(decision.truth.value),
                        outcome_reason=decision.reason,
                    )
    row = (
        db.execute(
            insert(rule_evaluations)
            .values(
                id=str(uuid4()),
                organization_id=organization_id,
                product_id=scope["productId"],
                subject_id=subject["id"],
                environment=scope["environment"],
                target_revision=scope["targetRevision"],
                control_id=control["id"],
                governance_revision=governance_revision,
                scan_id=scan_id,
                status=result.status.value,
                reason=result.reason,
                evidence_ids=list(result.evidence_ids),
                control=control,
                subject=subject,
                evaluated_at=now,
            )
            .returning(rule_evaluations)
        )
        .mappings()
        .one()
    )
    return _serialize(row)

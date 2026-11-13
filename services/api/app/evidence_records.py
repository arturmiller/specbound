"""Persist validated observations and select only evidence current in a scope."""

import re
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from sqlalchemy import insert, select
from sqlalchemy.engine import Connection

from app.assessment import AssessmentResult, AssessmentStatus, determine_assessment
from app.collector_contracts import validate_response
from app.tables import evidence_records, products, teams

MAX_TTL_SECONDS = 365 * 24 * 60 * 60
REVISION = re.compile(r"(?:[0-9a-f]{40}|[0-9a-f]{64}|sha256:[0-9a-f]{64})")
GIT_REVISION = re.compile(r"(?:[0-9a-f]{40}|[0-9a-f]{64})")


def _utc(value):
    if (
        not isinstance(value, datetime)
        or value.tzinfo is None
        or value.utcoffset() is None
    ):
        raise ValueError("A timezone-aware datetime is required")
    return value.astimezone(timezone.utc)


def _observation_time(value):
    try:
        return _utc(datetime.fromisoformat(value.replace("Z", "+00:00")))
    except (AttributeError, TypeError, ValueError) as exc:
        raise ValueError("Invalid observation timestamp") from exc


def _serialize(row):
    return {
        "id": row["id"],
        "organizationId": row["organization_id"],
        "productId": row["product_id"],
        "subjectId": row["subject_id"],
        "capability": row["capability"],
        "environment": row["environment"],
        "targetRevision": row["target_revision"],
        "collectorRevision": row["collector_revision"],
        "collectorImage": row["collector_image"],
        "producerKind": row["producer_kind"] or "collector",
        "producerScanId": row["producer_scan_id"],
        "provenance": row["provenance"],
        "value": row["value"],
        "observedAt": row["observed_at"],
        "expiresAt": row["expires_at"],
        "ttlSeconds": row["ttl_seconds"],
    }


def store_evidence(
    db: Connection, organization_id, provider, request, response, *, ttl_seconds, now
):
    """Store a validated response; callers must obtain it from their trusted runner."""
    now = _utc(now)
    if type(ttl_seconds) is not int or not 0 < ttl_seconds <= MAX_TTL_SECONDS:
        raise ValueError("TTL must be a positive number of seconds, at most one year")
    validate_response(provider, request, response)
    scope = request["scope"]
    revision = provider.get("revision")
    target = scope["targetRevision"]
    image = provider["manifest"]["runtime"]["image"]
    if (
        not isinstance(revision, str)
        or not GIT_REVISION.fullmatch(revision)
        or not isinstance(target, str)
        or not REVISION.fullmatch(target)
        or not isinstance(image, str)
        or len(image) > 500
        or len(scope["environment"]) > 200
        or any(
            len(item["subjectId"]) > 500 or len(item["capability"]) > 500
            for item in response["observations"]
        )
    ):
        raise ValueError("Evidence provenance or scope is invalid")
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

    values = []
    for observation in response["observations"]:
        observed = _observation_time(observation["observedAt"])
        if observed > now:
            raise ValueError("Future observations cannot be current evidence")
        values.append(
            {
                "id": str(uuid4()),
                "organization_id": organization_id,
                "product_id": scope["productId"],
                "subject_id": observation["subjectId"],
                "capability": observation["capability"],
                "environment": scope["environment"],
                "target_revision": target,
                "collector_revision": revision,
                "collector_image": image,
                "provenance": observation["provenance"],
                "value": observation["value"],
                "observed_at": observed,
                "expires_at": observed + timedelta(seconds=ttl_seconds),
                "ttl_seconds": ttl_seconds,
            }
        )
    rows = (
        db.execute(insert(evidence_records).returning(evidence_records), values)
        .mappings()
        .all()
    )
    return [_serialize(row) for row in rows]


def current_evidence(
    db: Connection, organization_id, scope, subject_id, capability, *, now
):
    """Only the exact tenant, subject, capability and revision can be selected."""
    now = _utc(now)
    rows = (
        db.execute(
            select(evidence_records)
            .select_from(
                evidence_records.join(
                    products, evidence_records.c.product_id == products.c.id
                ).join(teams, products.c.owner_team_id == teams.c.id)
            )
            .where(
                evidence_records.c.organization_id == organization_id,
                teams.c.organization_id == organization_id,
                evidence_records.c.product_id == scope["productId"],
                evidence_records.c.environment == scope["environment"],
                evidence_records.c.target_revision == scope["targetRevision"],
                evidence_records.c.subject_id == subject_id,
                evidence_records.c.capability == capability,
                evidence_records.c.observed_at <= now,
                evidence_records.c.expires_at > now,
            )
            .order_by(evidence_records.c.observed_at.desc(), evidence_records.c.id)
        )
        .mappings()
        .all()
    )
    return [_serialize(row) for row in rows]


def assess_with_evidence(
    db: Connection,
    organization_id,
    scope,
    subject_id,
    capability,
    *,
    evidence_ids,
    now,
    applicability,
    outcome=None,
    outcome_reason=None,
    scope_reason=None,
):
    """Guard a proposed assessment against missing, foreign, or expired records."""
    _utc(now)
    if not isinstance(evidence_ids, tuple) or any(
        not isinstance(item, str) or not item for item in evidence_ids
    ):
        raise ValueError("evidence_ids must be a tuple of identifiers")
    if evidence_ids:
        current = {
            item["id"]
            for item in current_evidence(
                db, organization_id, scope, subject_id, capability, now=now
            )
        }
        if not set(evidence_ids).issubset(current):
            return AssessmentResult(
                AssessmentStatus.UNKNOWN, "Nachweise fehlen oder sind abgelaufen"
            )
    return determine_assessment(
        applicability=applicability,
        evidence_ids=evidence_ids,
        outcome=outcome,
        outcome_reason=outcome_reason,
        scope_reason=scope_reason,
    )

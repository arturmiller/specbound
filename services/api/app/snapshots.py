"""Immutable snapshots distinguish PR checks from product baselines."""

import re
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import insert, select
from sqlalchemy.engine import Connection

from app.coverage import OPENAPI_SCANNER, PYTHON_LICENSE_SCANNER, scan_covers
from app.tables import (
    assessment_snapshots,
    evidence_records,
    products,
    repo_bindings,
    rule_evaluations,
    scanner_coverage,
    teams,
)

STATUSES = ("PASS", "FAIL", "UNKNOWN", "NOT_APPLICABLE")
COMMIT = re.compile(r"(?:[0-9a-f]{40}|[0-9a-f]{64})")


def _serialize(row):
    return {
        "id": row["id"],
        "organizationId": row["organization_id"],
        "productId": row["product_id"],
        "bindingId": row["binding_id"],
        "context": row["context"],
        "pullRequestNumber": row["pull_request_number"],
        "environment": row["environment"],
        "gitSha": row["git_sha"],
        "packSha": row["pack_sha"],
        "evaluationIds": row["evaluation_ids"],
        "evidenceIds": row["evidence_ids"],
        "counts": row["counts"],
        "evaluations": row["evaluations"],
        "createdAt": row["created_at"],
    }


def get_snapshot(db: Connection, organization_id, snapshot_id):
    row = (
        db.execute(
            select(assessment_snapshots).where(
                assessment_snapshots.c.id == snapshot_id,
                assessment_snapshots.c.organization_id == organization_id,
            )
        )
        .mappings()
        .one_or_none()
    )
    return _serialize(row) if row is not None else None


def list_snapshots(db: Connection, organization_id, product_id):
    rows = (
        db.execute(
            select(assessment_snapshots)
            .where(
                assessment_snapshots.c.organization_id == organization_id,
                assessment_snapshots.c.product_id == product_id,
            )
            .order_by(
                assessment_snapshots.c.created_at.desc(), assessment_snapshots.c.id
            )
        )
        .mappings()
        .all()
    )
    return [_serialize(row) for row in rows]


def create_snapshot(
    db: Connection,
    organization_id,
    product_id,
    *,
    context,
    binding_id,
    pull_request_number,
    environment,
    git_sha,
    pack_sha,
    evaluation_ids,
    now,
):
    """Freeze evaluated results only when all provenance matches the requested context."""
    if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("A timezone-aware snapshot time is required")
    now = now.astimezone(timezone.utc)
    if not (
        (
            context == "pull_request"
            and type(pull_request_number) is int
            and pull_request_number > 0
        )
        or (context in ("baseline", "repository") and pull_request_number is None)
    ):
        raise ValueError("Invalid assessment context")
    if (
        not isinstance(environment, str)
        or not environment.strip()
        or len(environment) > 200
    ):
        raise ValueError("A valid environment is required")
    if any(
        not isinstance(value, str) or not COMMIT.fullmatch(value)
        for value in (git_sha, pack_sha)
    ):
        raise ValueError("Full Git commit IDs are required")
    if (
        not isinstance(evaluation_ids, list)
        or not 0 < len(evaluation_ids) <= 1000
        or any(not isinstance(item, str) or not item for item in evaluation_ids)
        or len(set(evaluation_ids)) != len(evaluation_ids)
    ):
        raise ValueError("Distinct evaluation IDs are required")

    owned = db.execute(
        select(repo_bindings.c.id)
        .select_from(
            repo_bindings.join(
                products, repo_bindings.c.product_id == products.c.id
            ).join(teams, products.c.owner_team_id == teams.c.id)
        )
        .where(
            repo_bindings.c.id == binding_id,
            products.c.id == product_id,
            teams.c.organization_id == organization_id,
        )
        .with_for_update(of=products)
    ).first()
    if owned is None:
        raise LookupError("Product or repository binding not found in organization")
    rows = (
        db.execute(
            select(rule_evaluations).where(
                rule_evaluations.c.id.in_(evaluation_ids),
                rule_evaluations.c.organization_id == organization_id,
                rule_evaluations.c.product_id == product_id,
                rule_evaluations.c.environment == environment,
                rule_evaluations.c.target_revision == git_sha,
                rule_evaluations.c.governance_revision == pack_sha,
                rule_evaluations.c.evaluated_at <= now,
            )
        )
        .mappings()
        .all()
    )
    if len(rows) != len(evaluation_ids):
        raise ValueError("Evaluations do not match the snapshot scope or time")
    counts = dict.fromkeys(STATUSES, 0)
    evidence_ids, pairs, details = set(), set(), []
    for row in sorted(rows, key=lambda item: item["id"]):
        identity = (row["subject_id"], row["control_id"])
        if identity in pairs:
            raise ValueError("Duplicate subject and control evaluation")
        pairs.add(identity)
        scan = None
        if row["scan_id"] is not None:
            scan = (
                db.execute(
                    select(scanner_coverage).where(
                        scanner_coverage.c.id == row["scan_id"],
                        scanner_coverage.c.binding_id == binding_id,
                    )
                )
                .mappings()
                .one_or_none()
            )
            if scan is None:
                raise ValueError("Evaluation belongs to a different repository binding")
        subject_scanners = {"api.path": OPENAPI_SCANNER, "api.schema": OPENAPI_SCANNER, "python.package": PYTHON_LICENSE_SCANNER}
        expected_scanner = subject_scanners.get(row["subject"].get("type"))
        if row["status"] != "UNKNOWN" and (
            scan is None
            or expected_scanner is None
            or scan["scanner"] != expected_scanner
            or not scan_covers(
                db,
                scan_id=row["scan_id"],
                product_id=product_id,
                binding_id=binding_id,
                ref=scan["ref"],
                expected_commit=git_sha,
                not_after=now,
                scanner=expected_scanner,
            )
        ):
            raise ValueError("Evaluation no longer has current scanner coverage")
        ids = row["evidence_ids"]
        if not isinstance(ids, list) or (row["status"] in ("PASS", "FAIL") and not ids):
            raise ValueError("Evaluation evidence is invalid")
        for evidence_id in ids:
            found = db.execute(
                select(evidence_records.c.id).where(
                    evidence_records.c.id == evidence_id,
                    evidence_records.c.organization_id == organization_id,
                    evidence_records.c.product_id == product_id,
                    evidence_records.c.subject_id == row["subject_id"],
                    evidence_records.c.environment == environment,
                    evidence_records.c.target_revision == git_sha,
                    evidence_records.c.capability
                    == row["control"]["requiredEvidence"]["capability"],
                    evidence_records.c.observed_at <= now,
                    evidence_records.c.expires_at > now,
                )
            ).first()
            if found is None:
                raise ValueError("Evaluation evidence is missing, foreign or expired")
            evidence_ids.add(evidence_id)
        counts[row["status"]] += 1
        details.append(
            {
                "id": row["id"],
                "subjectId": row["subject_id"],
                "controlId": row["control_id"],
                "status": row["status"],
                "reason": row["reason"],
                "evidenceIds": ids,
            }
        )
    row = (
        db.execute(
            insert(assessment_snapshots)
            .values(
                id=str(uuid4()),
                organization_id=organization_id,
                product_id=product_id,
                binding_id=binding_id,
                context=context,
                pull_request_number=pull_request_number,
                environment=environment,
                git_sha=git_sha,
                pack_sha=pack_sha,
                evaluation_ids=sorted(evaluation_ids),
                evidence_ids=sorted(evidence_ids),
                counts=counts,
                evaluations=details,
                created_at=now,
            )
            .returning(assessment_snapshots)
        )
        .mappings()
        .one()
    )
    return _serialize(row)

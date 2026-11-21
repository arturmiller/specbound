"""Read an exact immutable assessment with its authorized provenance."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.engine import Connection

from app.database import get_connection
from app.evidence_records import _serialize as serialize_evidence
from app.findings import _serialize as serialize_finding
from app.findings import get_history
from app.github_source import REPOSITORY
from app.identity import get_current_principal
from app.products import _product
from app.pull_request_events import parse_pr_event
from app.snapshots import _serialize as serialize_snapshot
from app.tables import (
    assessment_jobs,
    assessment_snapshots,
    evidence_records,
    finding_history,
    findings,
    github_events,
    public_license_scans,
    rule_evaluations,
    scanner_coverage,
)

router = APIRouter(dependencies=[Depends(get_current_principal)])


def _pull_request_url(db, snapshot):
    if snapshot["context"] != "pull_request":
        return None
    delivery = db.execute(
        select(github_events.c.payload, assessment_jobs.c.pull_request_id)
        .join(
            assessment_jobs,
            github_events.c.delivery_id == assessment_jobs.c.delivery_id,
        )
        .where(
            assessment_jobs.c.result_snapshot_id == snapshot["id"],
            assessment_jobs.c.organization_id == snapshot["organization_id"],
            assessment_jobs.c.product_id == snapshot["product_id"],
            assessment_jobs.c.binding_id == snapshot["binding_id"],
            assessment_jobs.c.pull_request_number == snapshot["pull_request_number"],
            assessment_jobs.c.head_sha == snapshot["git_sha"],
            github_events.c.organization_id == snapshot["organization_id"],
            github_events.c.event_type == "pull_request",
        )
    ).one_or_none()
    if delivery is None:
        return None
    payload, pull_request_id = delivery
    try:
        event = parse_pr_event(payload)
    except ValueError:
        return None
    if (
        event is None
        or event["pr_id"] != pull_request_id
        or event["number"] != snapshot["pull_request_number"]
        or event["head"] != snapshot["git_sha"]
    ):
        return None
    repository = event["repository"]
    if not REPOSITORY.fullmatch(repository) or any(
        part in (".", "..") for part in repository.split("/")
    ):
        return None
    return f"https://github.com/{repository}/pull/{event['number']}"


@router.get("/organizations/{organization_id}/findings/{finding_id}/history")
def finding_history_report(
    organization_id: str,
    finding_id: str,
    principal: Annotated[str, Depends(get_current_principal)],
    db: Annotated[Connection, Depends(get_connection, scope="function")],
):
    finding = (
        db.execute(
            select(findings).where(
                findings.c.id == finding_id,
                findings.c.organization_id == organization_id,
            )
        )
        .mappings()
        .one_or_none()
    )
    if finding is None:
        raise HTTPException(status_code=404, detail="Finding not found")
    _, team = _product(db, finding["product_id"], principal, "read")
    if team["organization_id"] != organization_id:
        raise HTTPException(status_code=403, detail="Insufficient permission")
    history = get_history(db, organization_id, finding_id)
    snapshot_ids = [item["snapshotId"] for item in history]
    snapshots = (
        db.execute(
            select(assessment_snapshots).where(
                assessment_snapshots.c.id.in_(snapshot_ids),
                assessment_snapshots.c.organization_id == organization_id,
                assessment_snapshots.c.product_id == finding["product_id"],
                assessment_snapshots.c.binding_id == finding["binding_id"],
                assessment_snapshots.c.context == finding["context"],
                assessment_snapshots.c.pull_request_number
                == finding["pull_request_number"],
                assessment_snapshots.c.environment == finding["environment"],
            )
        )
        .mappings()
        .all()
    )
    by_id = {snapshot["id"]: snapshot for snapshot in snapshots}
    if len(by_id) != len(snapshot_ids) or (
        history and history[-1]["snapshotId"] != finding["last_snapshot_id"]
    ):
        raise HTTPException(status_code=409, detail="Finding provenance is incomplete")
    return {
        "finding": serialize_finding(finding),
        "history": [
            {
                **event,
                "gitSha": by_id[event["snapshotId"]]["git_sha"],
                "packSha": by_id[event["snapshotId"]]["pack_sha"],
            }
            for event in history
        ],
    }


@router.get("/assessments/{snapshot_id}")
def assessment_report(
    snapshot_id: str,
    principal: Annotated[str, Depends(get_current_principal)],
    db: Annotated[Connection, Depends(get_connection, scope="function")],
):
    snapshot = (
        db.execute(
            select(assessment_snapshots).where(assessment_snapshots.c.id == snapshot_id)
        )
        .mappings()
        .one_or_none()
    )
    if snapshot is None:
        raise HTTPException(status_code=404, detail="Assessment not found")
    _, team = _product(db, snapshot["product_id"], principal, "read")
    if team["organization_id"] != snapshot["organization_id"]:
        raise HTTPException(status_code=403, detail="Insufficient permission")
    evaluations = (
        db.execute(
            select(rule_evaluations).where(
                rule_evaluations.c.id.in_(snapshot["evaluation_ids"]),
                rule_evaluations.c.organization_id == snapshot["organization_id"],
                rule_evaluations.c.product_id == snapshot["product_id"],
                rule_evaluations.c.target_revision == snapshot["git_sha"],
                rule_evaluations.c.governance_revision == snapshot["pack_sha"],
                rule_evaluations.c.environment == snapshot["environment"],
            )
        )
        .mappings()
        .all()
    )
    evidence = (
        db.execute(
            select(evidence_records).where(
                evidence_records.c.id.in_(snapshot["evidence_ids"]),
                evidence_records.c.organization_id == snapshot["organization_id"],
                evidence_records.c.product_id == snapshot["product_id"],
                evidence_records.c.target_revision == snapshot["git_sha"],
                evidence_records.c.environment == snapshot["environment"],
            )
        )
        .mappings()
        .all()
    )
    if len(evaluations) != len(snapshot["evaluation_ids"]) or len(evidence) != len(
        snapshot["evidence_ids"]
    ):
        raise HTTPException(
            status_code=409, detail="Assessment provenance is incomplete"
        )
    history = (
        db.execute(
            select(finding_history, findings.c.fingerprint)
            .select_from(
                finding_history.join(
                    findings, findings.c.id == finding_history.c.finding_id
                )
            )
            .where(
                finding_history.c.snapshot_id == snapshot_id,
                findings.c.organization_id == snapshot["organization_id"],
                findings.c.product_id == snapshot["product_id"],
            )
        )
        .mappings()
        .all()
    )
    scan_ids = [row["scan_id"] for row in evaluations if row["scan_id"] is not None]
    scans = (
        db.execute(
            select(scanner_coverage).where(
                scanner_coverage.c.id.in_(scan_ids),
                scanner_coverage.c.binding_id == snapshot["binding_id"],
            )
        )
        .mappings()
        .all()
    )
    scan_by_id = {row["id"]: row for row in scans}
    public_scan = (
        db.execute(
            select(public_license_scans).where(
                public_license_scans.c.assessment_id == snapshot_id,
                public_license_scans.c.organization_id == snapshot["organization_id"],
                public_license_scans.c.product_id == snapshot["product_id"],
                public_license_scans.c.binding_id == snapshot["binding_id"],
            )
        )
        .mappings()
        .one_or_none()
    )
    source_scan = None
    if public_scan is not None:
        result = public_scan["result"] or {}
        observed = result.get("sourceRevision")
        unavailable = (
            snapshot["context"] == "pull_request"
            and public_scan["status"] == "failed"
            and public_scan["ref"] == snapshot["git_sha"]
            and observed is None
            and result.get("sourceCoverage") == "UNKNOWN"
            and not result.get("files")
        )
        if not unavailable and observed != snapshot["git_sha"]:
            raise HTTPException(
                status_code=409, detail="Scan provenance does not match assessment"
            )
        source_scan = {
            "id": public_scan["id"],
            "repository": public_scan["repository"],
            "ref": public_scan["ref"],
            "sourceRevision": observed,
            "coverage": result.get("sourceCoverage"),
            "files": result.get("files", []),
            "unsupportedFiles": result.get("unsupportedFiles", []),
            "reason": result.get("reason"),
        }
    return {
        "assessment": serialize_snapshot(snapshot),
        "pullRequestUrl": _pull_request_url(db, snapshot),
        "sourceScan": source_scan,
        "evaluations": [
            {
                "id": row["id"],
                "subject": row["subject"],
                "control": row["control"],
                "status": row["status"],
                "reason": row["reason"],
                "evidenceIds": row["evidence_ids"],
                "coverage": (
                    {
                        "status": scan_by_id[row["scan_id"]]["status"],
                        "revision": scan_by_id[row["scan_id"]]["source_revision"],
                        "errors": scan_by_id[row["scan_id"]]["errors"],
                    }
                    if row["scan_id"] in scan_by_id
                    else None
                ),
            }
            for row in evaluations
        ],
        "evidence": [serialize_evidence(row) for row in evidence],
        "findings": [
            {
                "id": row["finding_id"],
                "fingerprint": row["fingerprint"],
                "evaluationId": row["evaluation_id"],
                "state": row["state_after"],
                "outcome": row["outcome"],
                "reason": row["reason"],
            }
            for row in history
        ],
    }

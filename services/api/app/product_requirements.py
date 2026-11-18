"""Product-scoped requirements, complete assessments and their selected evidence."""

import copy
import json
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.engine import Connection

from app.assessment_reports import assessment_report
from app.database import get_connection
from app.identity import get_current_principal
from app.products import _product, get_product_governance
from app.snapshots import COMMIT
from app.tables import assessment_snapshots, public_license_scans

router = APIRouter()


def _definitions(context, report):
    if context and context["mode"] == "profile":
        return (
            copy.deepcopy(context["profile"]["resolved"]["controls"]),
            context["profile"]["resolved"]["groups"],
            "profile",
        )
    observed = {}
    bindings = (
        context["policy"]["controls"]
        if context and context["mode"] == "legacy-example"
        else [item["control"] for item in (report or {}).get("evaluations", [])]
    )
    for binding in bindings:
        control = observed.setdefault(
            binding["id"],
            {
                "id": binding["id"],
                "title": binding["id"],
                "parts": [],
                "parameters": [],
                "groupKey": "$root",
                "binding": binding,
                "methodStatus": "configured",
                "definitionVariants": [],
            },
        )
        if json.dumps(binding, sort_keys=True) not in {
            json.dumps(value, sort_keys=True) for value in control["definitionVariants"]
        }:
            control["definitionVariants"].append(binding)
    return (
        list(observed.values()),
        [
            {
                "key": "$root",
                "title": "Gespeicherte Control-Definitionen",
                "parent": None,
            }
        ],
        "legacy-policy" if context else "historical-unknown",
    )


def _summary(control, evaluations, saved, run):
    if saved:
        return saved
    statuses = [item["status"] for item in evaluations]
    status = (
        "FAIL"
        if "FAIL" in statuses
        else "UNKNOWN"
        if not statuses or "UNKNOWN" in statuses
        else "PASS"
        if "PASS" in statuses
        else "NOT_APPLICABLE"
    )
    return {
        "controlId": control["id"],
        "status": status,
        "executionStatus": "evaluated" if evaluations else "not_evaluated",
        "reason": "individual-evaluations"
        if evaluations
        else "scan-" + run["status"]
        if run
        else "no-assessment",
        "evaluationIds": [item["id"] for item in evaluations],
        "evidenceIds": sorted(
            {value for item in evaluations for value in item["evidenceIds"]}
        ),
    }


@router.get("/products/{product_id}/requirements")
def product_requirements(
    product_id: str,
    principal: Annotated[str, Depends(get_current_principal)],
    db: Annotated[Connection, Depends(get_connection, scope="function")],
    assessment: Annotated[str, Query(max_length=100)] = "",
):
    _, team = _product(db, product_id, principal, "read")
    org = team["organization_id"]
    scans = (
        db.execute(
            select(
                public_license_scans.c.id,
                public_license_scans.c.status,
                public_license_scans.c.created_at,
                public_license_scans.c.ref,
                public_license_scans.c.repository,
                public_license_scans.c.assessment_id,
                public_license_scans.c.governance_context["profile"]["name"]
                .as_string()
                .label("profile_name"),
                public_license_scans.c.governance_context["profile"]["version"]
                .as_string()
                .label("profile_version"),
            ).where(
                public_license_scans.c.organization_id == org,
                public_license_scans.c.product_id == product_id,
            )
        )
        .mappings()
        .all()
    )
    snapshots = (
        db.execute(
            select(
                assessment_snapshots.c.id,
                assessment_snapshots.c.created_at,
                assessment_snapshots.c.context,
                assessment_snapshots.c.pull_request_number,
                assessment_snapshots.c.git_sha,
                assessment_snapshots.c.governance_context["profile"]["name"]
                .as_string()
                .label("profile_name"),
                assessment_snapshots.c.governance_context["profile"]["version"]
                .as_string()
                .label("profile_version"),
            ).where(
                assessment_snapshots.c.organization_id == org,
                assessment_snapshots.c.product_id == product_id,
            )
        )
        .mappings()
        .all()
    )
    linked = {scan["assessment_id"] for scan in scans}
    options = [
        {
            "id": scan["assessment_id"] or "scan:" + scan["id"],
            "createdAt": scan["created_at"],
            "status": scan["status"],
            "context": "repository",
            "ref": scan["ref"],
            "repository": scan["repository"],
            "profileName": scan["profile_name"],
            "profileVersion": scan["profile_version"],
        }
        for scan in scans
    ]
    options += [
        {
            "id": row["id"],
            "createdAt": row["created_at"],
            "status": "completed",
            "context": row["context"],
            "ref": row["git_sha"],
            "pullRequestNumber": row["pull_request_number"],
            "profileName": row["profile_name"],
            "profileVersion": row["profile_version"],
        }
        for row in snapshots
        if row["id"] not in linked
    ]
    options.sort(key=lambda item: (item["createdAt"], item["id"]), reverse=True)
    selection = assessment or (options[0]["id"] if options else "current")
    report, run, context, source_scan = None, None, None, None
    if selection.startswith("scan:"):
        row = (
            db.execute(
                select(public_license_scans).where(
                    public_license_scans.c.organization_id == org,
                    public_license_scans.c.product_id == product_id,
                    public_license_scans.c.id == selection[5:],
                )
            )
            .mappings()
            .one_or_none()
        )
        if row is None:
            raise HTTPException(
                status_code=404, detail="Scan is not available for this product"
            )
        result = row["result"] or {}
        run = {
            "id": row["id"],
            "status": row["status"],
            "errorCode": row["error_code"],
            "coverage": result.get("sourceCoverage"),
            "reason": result.get("reason"),
            "files": result.get("files", []),
            "unsupportedFiles": result.get("unsupportedFiles", []),
        }
        revision = result.get("sourceRevision")
        if isinstance(revision, str) and COMMIT.fullmatch(revision):
            source_scan = {
                "id": row["id"],
                "repository": row["repository"],
                "ref": row["ref"],
                "sourceRevision": revision,
                "coverage": result.get("sourceCoverage"),
                "files": result.get("files", []),
                "unsupportedFiles": result.get("unsupportedFiles", []),
                "reason": result.get("reason"),
            }
        context = row["governance_context"]
        if row["assessment_id"]:
            selection = row["assessment_id"]
    if selection != "current" and not selection.startswith("scan:"):
        if selection not in {row["id"] for row in snapshots}:
            raise HTTPException(
                status_code=404, detail="Assessment is not available for this product"
            )
        report = assessment_report(selection, principal, db)
        context = report["assessment"]["governanceContext"]
        source_scan = report.get("sourceScan")
    if selection == "current":
        governance = get_product_governance(product_id, principal, db)
        if governance["profile"]:
            context = {
                "mode": "profile",
                "product": governance["product"],
                "profile": governance["profile"],
            }
    controls, groups, provenance = _definitions(context, report)
    results = {
        item["controlId"]: item
        for item in (report or {}).get("assessment", {}).get("controls") or []
    }
    evaluations = (report or {}).get("evaluations", [])
    for control in controls:
        control["evaluations"] = [
            item for item in evaluations if item["control"]["id"] == control["id"]
        ]
        control["result"] = _summary(
            control, control["evaluations"], results.get(control["id"]), run
        )
    now = datetime.now(timezone.utc)
    evidence = (report or {}).get("evidence", [])
    for item in evidence:
        expires = item.get("expiresAt")
        item["freshness"] = (
            "unknown" if expires is None else "expired" if expires <= now else "current"
        )
    if selection == "current" and context is None:
        provenance = "profile-unassigned"
    return {
        "productId": product_id,
        "selectionId": selection,
        "options": options,
        "run": run,
        "context": context,
        "provenanceStatus": provenance,
        "groups": groups,
        "controls": controls,
        "evidence": evidence,
        "findings": (report or {}).get("findings", []),
        "sourceScan": source_scan,
        "assessment": (report or {}).get("assessment"),
        "asOf": now,
    }

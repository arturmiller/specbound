"""Publish fail-closed, commit-specific GitHub checks for PR assessments."""

from datetime import timedelta, timezone

from sqlalchemy import select

from app.coverage import scan_covers
from app.git_source import SourceUnavailable
from app.pr_comment import STATUSES
from app.pr_comment_delivery import deliver_once
from app.tables import evidence_records, rule_evaluations, scanner_coverage

CHECK_NAME = "Specbound assessment"


def assess_snapshot(db, snapshot, now):
    """Return a conservative conclusion and the earliest evidence expiration."""
    counts, evaluations = snapshot["counts"], snapshot["evaluations"]
    if (
        not isinstance(counts, dict)
        or set(counts) != {key for _, key in STATUSES}
        or any(type(x) is not int or x < 0 for x in counts.values())
        or not isinstance(evaluations, list)
        or len(evaluations) != sum(counts.values())
        or counts["FAIL"]
        or counts["UNKNOWN"]
        or not counts["PASS"]
    ):
        return "failure", None
    expected_ids = snapshot["evaluation_ids"]
    if (
        not isinstance(expected_ids, list)
        or len(expected_ids) != len(set(expected_ids))
        or len(expected_ids) != len(evaluations)
    ):
        return "failure", None
    observed = dict.fromkeys(counts, 0)
    seen = set()
    expiry = None
    for detail in evaluations:
        if not isinstance(detail, dict) or detail.get("status") not in observed:
            return "failure", None
        status = detail["status"]
        if detail.get("id") not in expected_ids or detail.get("id") in seen:
            return "failure", None
        seen.add(detail["id"])
        observed[status] += 1
        row = (
            db.execute(
                select(rule_evaluations).where(
                    rule_evaluations.c.id == detail.get("id"),
                    rule_evaluations.c.organization_id == snapshot["organization_id"],
                    rule_evaluations.c.product_id == snapshot["product_id"],
                    rule_evaluations.c.environment == snapshot["environment"],
                    rule_evaluations.c.target_revision == snapshot["git_sha"],
                    rule_evaluations.c.governance_revision == snapshot["pack_sha"],
                    rule_evaluations.c.evaluated_at <= now,
                )
            )
            .mappings()
            .one_or_none()
        )
        if (
            row is None
            or row["status"] != status
            or row["subject_id"] != detail.get("subjectId")
            or row["control_id"] != detail.get("controlId")
            or row["evidence_ids"] != detail.get("evidenceIds")
        ):
            return "failure", None
        scan = (
            db.execute(
                select(scanner_coverage).where(
                    scanner_coverage.c.id == row["scan_id"],
                    scanner_coverage.c.binding_id == snapshot["binding_id"],
                )
            )
            .mappings()
            .one_or_none()
        )
        if scan is None or not scan_covers(
            db,
            scan_id=row["scan_id"],
            product_id=snapshot["product_id"],
            binding_id=snapshot["binding_id"],
            ref=scan["ref"],
            expected_commit=snapshot["git_sha"],
            not_after=now,
        ):
            return "failure", None
        ids = row["evidence_ids"]
        if not isinstance(ids, list) or (status == "PASS" and not ids):
            return "failure", None
        try:
            capability = row["control"]["requiredEvidence"]["capability"]
        except (TypeError, KeyError):
            return "failure", None
        for evidence_id in ids:
            evidence = db.execute(
                select(evidence_records.c.expires_at).where(
                    evidence_records.c.id == evidence_id,
                    evidence_records.c.organization_id == snapshot["organization_id"],
                    evidence_records.c.product_id == snapshot["product_id"],
                    evidence_records.c.subject_id == row["subject_id"],
                    evidence_records.c.environment == snapshot["environment"],
                    evidence_records.c.target_revision == snapshot["git_sha"],
                    evidence_records.c.capability == capability,
                    evidence_records.c.observed_at <= now,
                    evidence_records.c.expires_at > now,
                )
            ).scalar_one_or_none()
            if evidence is None:
                return "failure", None
            expiry = min(expiry, evidence) if expiry else evidence
    if observed != counts or expiry is None:
        return "failure", None
    if expiry.tzinfo is None:
        expiry = expiry.replace(tzinfo=timezone.utc)
    return "success", min(expiry, now + timedelta(minutes=5))


def publish_check(db, source, job, snapshot, _portal, now):
    token = source._token(permissions={"pull_requests": "read", "checks": "write"})
    prefix = f"/repos/{source.repository}"
    pull = source._request("GET", f"{prefix}/pulls/{job['pull_request_number']}", token)
    if not isinstance(pull.get("head"), dict) or not isinstance(
        pull["head"].get("sha"), str
    ):
        raise SourceUnavailable("Invalid GitHub PR head")
    current = pull["head"]["sha"] == job["head_sha"]
    matches = []
    for page in range(1, 101):
        payload = source._request(
            "GET",
            f"{prefix}/commits/{job['head_sha']}/check-runs",
            token,
            params={
                "check_name": CHECK_NAME,
                "filter": "all",
                "per_page": 100,
                "page": page,
            },
        )
        runs = payload.get("check_runs")
        if not isinstance(runs, list):
            raise SourceUnavailable("Invalid GitHub check runs")
        for run in runs:
            if (
                isinstance(run, dict)
                and run.get("name") == CHECK_NAME
                and run.get("external_id") == job["id"]
                and isinstance(run.get("app"), dict)
                and str(run["app"].get("id")) == source.app_id
            ):
                if type(run.get("id")) is not int or run["id"] <= 0:
                    raise SourceUnavailable("Invalid GitHub check ID")
                matches.append(run["id"])
        if len(runs) < 100:
            break
    else:
        raise SourceUnavailable("Too many GitHub check runs")
    if len(matches) > 1:
        raise SourceUnavailable("Duplicate GitHub checks")
    if not current:
        if matches:
            source._request(
                "PATCH",
                f"{prefix}/check-runs/{matches[0]}",
                token,
                json={
                    "name": CHECK_NAME,
                    "status": "completed",
                    "conclusion": "failure",
                    "output": {
                        "title": "Assessment superseded",
                        "summary": "The pull request head changed.",
                    },
                },
            )
        return None
    conclusion, expires = assess_snapshot(db, snapshot, now)
    body = {
        "name": CHECK_NAME,
        "status": "completed",
        "conclusion": conclusion,
        "output": {
            "title": "Assessment " + conclusion,
            "summary": "Evidence and coverage are current."
            if conclusion == "success"
            else "Assessment failed or evidence and coverage are insufficient.",
        },
    }
    if matches:
        source._request("PATCH", f"{prefix}/check-runs/{matches[0]}", token, json=body)
    else:
        source._request(
            "POST",
            f"{prefix}/check-runs",
            token,
            json={**body, "head_sha": job["head_sha"], "external_id": job["id"]},
        )
    return expires


def publish_check_once(engine, organization_id, source_factory, portal_url, *, clock):
    return deliver_once(
        engine,
        organization_id,
        source_factory,
        portal_url,
        clock=clock,
        mode="check",
        send=publish_check,
    )

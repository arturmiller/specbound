"""Turn a trusted public scan into scoped evidence and a repository assessment."""

import hashlib
import json
import re
from datetime import timedelta
from urllib.parse import quote, urlsplit
from uuid import uuid4

from sqlalchemy import insert

from app.coverage import PYTHON_LICENSE_SCANNER
from app.findings import apply_snapshot
from app.frozen_governance import plan_public_scan
from app.license_policy import evaluate_license
from app.license_scope import (
    approval_rule,
    approval_scope,
    current_license_configuration,
    license_decision,
    license_use,
    live_approvals,
    locked_artifact_digest,
)
from app.pypi_license_metadata import MAX_ARTIFACTS
from app.rule_evaluation import evaluate_and_store
from app.snapshots import COMMIT, create_snapshot
from app.tables import evidence_records, scanner_coverage

CAPABILITY = "python.package-license/v1"
ENVIRONMENT = "repository"
TTL_SECONDS = 24 * 60 * 60
SHA256 = re.compile(r"[0-9a-f]{64}")


def _subject(job, package, revision, now):
    path, name, version = (
        package.get("path"),
        package.get("name"),
        package.get("version"),
    )
    markers, source = package.get("markers"), package.get("source")
    if not all(
        isinstance(value, str) and value and len(value) <= 500
        for value in (path, name, version, source)
    ):
        raise ValueError("Invalid locked package")
    if not isinstance(markers, list) or any(
        not isinstance(item, str) for item in markers
    ):
        raise ValueError("Invalid package markers")
    identity = json.dumps(
        [path, name, version, source, sorted(markers)],
        ensure_ascii=True,
        separators=(",", ":"),
    )
    return {
        "schemaVersion": 1,
        "id": "python-package:" + hashlib.sha256(identity.encode()).hexdigest(),
        "type": "python.package",
        "labels": {"name": name, "version": version, "lockfile": path},
        "scope": {"productId": job["product_id"], "targetRevision": revision},
        "provenance": {
            "sourceRef": f"repo:{quote(job['binding_id'], safe='')}/{quote(path, safe='/')}",
            "sourceRevision": revision,
        },
        "observedAt": now.isoformat(),
        "licenseArtifactDigest": locked_artifact_digest(package),
    }


def _verified_metadata(package):
    metadata = package.get("metadata")
    expression = package.get("licenseExpression")
    if (
        package.get("source") != "pypi"
        or not isinstance(metadata, dict)
        or metadata.get("status") != "OBSERVED"
    ):
        return None
    if not isinstance(expression, str) or not expression or len(expression) > 2048:
        return None
    artifacts = metadata.get("artifacts")
    if not isinstance(artifacts, list) or not 0 < len(artifacts) <= MAX_ARTIFACTS:
        return None
    for artifact in artifacts:
        if (
            not isinstance(artifact, dict)
            or artifact.get("licenseExpression") != expression
        ):
            return None
        if artifact.get("sourceKind") not in (
            "distribution-metadata",
            "source-archive-pkg-info",
        ):
            return None
        if any(
            not isinstance(artifact.get(key), str)
            or not SHA256.fullmatch(artifact[key])
            for key in ("artifactSha256", "metadataSha256")
        ):
            return None
        url = artifact.get("sourceUrl")
        if not isinstance(url, str) or len(url) > 4096:
            return None
        parsed = urlsplit(url)
        if (
            parsed.scheme != "https"
            or parsed.netloc != "files.pythonhosted.org"
            or not parsed.path.startswith("/packages/")
            or parsed.query
            or parsed.fragment
        ):
            return None
    return {"licenseExpression": expression, "artifacts": artifacts}


def _evidence(db, job, subject, value, revision, environment, now, approval=None):
    expires = now + timedelta(seconds=TTL_SECONDS)
    if approval:
        value = {
            **(value or {"licenseExpression": None, "artifacts": []}),
            "licenseApproval": license_decision(approval),
        }
        if approval["expires_at"] is not None:
            expires = min(expires, approval["expires_at"])
    return db.execute(
        insert(evidence_records)
        .values(
            id=str(uuid4()),
            organization_id=job["organization_id"],
            product_id=job["product_id"],
            subject_id=subject["id"],
            capability=CAPABILITY,
            environment=environment,
            target_revision=revision,
            collector_revision=None,
            collector_image=None,
            producer_kind="public-license-scan",
            producer_scan_id=job["id"],
            provenance={
                "sourceRef": value["artifacts"][0]["sourceUrl"]
                if value["artifacts"]
                else subject["provenance"]["sourceRef"],
                "scanId": job["id"],
                "repository": job["repository"],
                "lockfile": subject["labels"]["lockfile"],
            },
            value=value,
            observed_at=now,
            expires_at=expires,
            ttl_seconds=max(1, int((expires - now).total_seconds())),
        )
        .returning(evidence_records.c.id)
    ).scalar_one()


def _approval_for(db, job, context, subject, control, value, now):
    scope = approval_scope(context, job["binding_id"], subject, control)
    if scope is None:
        return None
    if (
        value
        and evaluate_license(
            value["licenseExpression"], approval_rule(control)["allowed"]
        )
        == "PASS"
    ):
        return None
    matches = db.execute(live_approvals(scope, now).limit(2)).mappings().all()
    if len(matches) != 1:
        return None
    approval = matches[0]
    if approval["kind"] == "conditions-met" and value is None:
        return None
    return approval


def create_public_license_assessment(db, job, result, *, now, pull_request_number=None):
    """Use only this worker's result; incomplete information never becomes PASS."""
    packages, files = result.get("packages"), result.get("files")
    source_coverage, revision = (
        result.get("sourceCoverage"),
        result.get("sourceRevision"),
    )
    context = job.get("governance_context")
    environment = license_use(context) or ENVIRONMENT
    approval_context = (
        context
        if environment != ENVIRONMENT and current_license_configuration(db, context)
        else None
    )
    profile_bound = context is not None and context.get("mode") == "profile"
    is_pr = pull_request_number is not None
    if is_pr:
        # A source error still has a known target, but no observed revision.
        if (
            revision is None
            and source_coverage == "UNKNOWN"
            and not packages
            and not files
        ):
            revision = job["ref"]
        if revision != job["ref"]:
            raise ValueError("License scan did not observe the queued commit")
    if (
        (not (profile_bound or is_pr) and source_coverage not in ("covered", "partial"))
        or not isinstance(revision, str)
        or not COMMIT.fullmatch(revision)
    ):
        return None
    if (
        not isinstance(packages, list)
        or not 0 <= len(packages) <= 200
        or not isinstance(files, list)
        or (not (profile_bound or is_pr) and (not packages or not files))
    ):
        return None
    if any(not isinstance(path, str) or not path or len(path) > 500 for path in files):
        raise ValueError("Invalid lockfile coverage")
    policy, execution_gaps = plan_public_scan(context, len(packages))
    coverage_status = (
        source_coverage if source_coverage in ("covered", "partial") else "failed"
    )
    scan = db.execute(
        insert(scanner_coverage)
        .values(
            binding_id=job["binding_id"],
            scanner=PYTHON_LICENSE_SCANNER,
            ref=job["ref"],
            status=coverage_status,
            source_revision=revision,
            observed_at=now,
            files=files,
            errors=(
                [
                    {"path": path, "reason": "unsupported lockfile"}
                    for path in result.get("unsupportedFiles", [])
                ]
                + (
                    [
                        {
                            "path": "",
                            "reason": str(
                                result.get("reason", "Source coverage unavailable")
                            )[:500],
                        }
                    ]
                    if coverage_status == "failed"
                    else []
                )
            ),
        )
        .returning(scanner_coverage.c.id)
    ).scalar_one()
    evaluation_ids = []
    for package in packages:
        if not isinstance(package, dict) or package.get("path") not in files:
            raise ValueError("Package is outside scanned lockfiles")
        subject = _subject(job, package, revision, now)
        value = _verified_metadata(package)
        evidence_id = (
            _evidence(db, job, subject, value, revision, environment, now)
            if value is not None
            else None
        )
        scope = {
            "productId": job["product_id"],
            "targetRevision": revision,
            "environment": environment,
        }
        for control in policy["controls"]:
            approved = _approval_for(
                db, job, approval_context, subject, control, value, now
            )
            selected = (
                _evidence(db, job, subject, value, revision, environment, now, approved)
                if approved
                else evidence_id
            )
            evaluation = evaluate_and_store(
                db,
                job["organization_id"],
                scope,
                subject,
                control,
                policy["revision"],
                now=now,
                scan_id=scan,
                binding_id=job["binding_id"],
                ref=job["ref"],
                selected_evidence_id=selected,
                approved_license_use=approved is not None,
            )
            evaluation_ids.append(evaluation["id"])
    snapshot = create_snapshot(
        db,
        job["organization_id"],
        job["product_id"],
        context="pull_request" if is_pr else "repository",
        binding_id=job["binding_id"],
        pull_request_number=pull_request_number,
        environment=environment,
        git_sha=revision,
        pack_sha=policy["revision"],
        evaluation_ids=evaluation_ids,
        now=now,
        governance_context=context,
        execution_gaps=execution_gaps,
    )
    if not is_pr:
        apply_snapshot(db, job["organization_id"], snapshot["id"])
    return snapshot["id"]

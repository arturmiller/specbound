"""Turn a trusted public scan into scoped evidence and a repository assessment."""

import hashlib
import json
import re
from datetime import timedelta
from urllib.parse import quote, urlsplit
from uuid import uuid4

from sqlalchemy import insert

from app.coverage import PYTHON_LICENSE_SCANNER
from app.example_license_pack import load_example_license_pack
from app.findings import apply_snapshot
from app.rule_evaluation import evaluate_and_store
from app.snapshots import create_snapshot
from app.tables import evidence_records, scanner_coverage

CAPABILITY = "python.package-license/v1"
ENVIRONMENT = "repository"
TTL_SECONDS = 24 * 60 * 60
SHA256 = re.compile(r"[0-9a-f]{64}")
GIT_SHA = re.compile(r"[0-9a-f]{40}")


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
    if not isinstance(artifacts, list) or not 0 < len(artifacts) <= 100:
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


def create_public_license_assessment(db, job, result, *, now):
    """Use only this worker's result; incomplete information never becomes PASS."""
    packages, files = result.get("packages"), result.get("files")
    source_coverage, revision = (
        result.get("sourceCoverage"),
        result.get("sourceRevision"),
    )
    if (
        source_coverage not in ("covered", "partial")
        or not isinstance(revision, str)
        or not GIT_SHA.fullmatch(revision)
    ):
        return None
    if (
        not isinstance(packages, list)
        or not 0 < len(packages) <= 200
        or not isinstance(files, list)
        or not files
    ):
        return None
    if any(not isinstance(path, str) or not path or len(path) > 500 for path in files):
        raise ValueError("Invalid lockfile coverage")
    policy = load_example_license_pack()
    control = policy["controls"][0]
    scan = db.execute(
        insert(scanner_coverage)
        .values(
            binding_id=job["binding_id"],
            scanner=PYTHON_LICENSE_SCANNER,
            ref=job["ref"],
            status=source_coverage,
            source_revision=revision,
            observed_at=now,
            files=files,
            errors=[
                {"path": path, "reason": "unsupported lockfile"}
                for path in result.get("unsupportedFiles", [])
            ],
        )
        .returning(scanner_coverage.c.id)
    ).scalar_one()
    evaluation_ids = []
    for package in packages:
        if not isinstance(package, dict) or package.get("path") not in files:
            raise ValueError("Package is outside scanned lockfiles")
        subject = _subject(job, package, revision, now)
        value = _verified_metadata(package)
        evidence_id = None
        if value is not None:
            evidence_id = str(uuid4())
            db.execute(
                insert(evidence_records).values(
                    id=evidence_id,
                    organization_id=job["organization_id"],
                    product_id=job["product_id"],
                    subject_id=subject["id"],
                    capability=CAPABILITY,
                    environment=ENVIRONMENT,
                    target_revision=revision,
                    collector_revision=None,
                    collector_image=None,
                    producer_kind="public-license-scan",
                    producer_scan_id=job["id"],
                    provenance={
                        "sourceRef": value["artifacts"][0]["sourceUrl"],
                        "scanId": job["id"],
                        "repository": job["repository"],
                        "lockfile": package["path"],
                    },
                    value=value,
                    observed_at=now,
                    expires_at=now + timedelta(seconds=TTL_SECONDS),
                    ttl_seconds=TTL_SECONDS,
                )
            )
        scope = {
            "productId": job["product_id"],
            "targetRevision": revision,
            "environment": ENVIRONMENT,
        }
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
            selected_evidence_id=evidence_id,
        )
        evaluation_ids.append(evaluation["id"])
    snapshot = create_snapshot(
        db,
        job["organization_id"],
        job["product_id"],
        context="repository",
        binding_id=job["binding_id"],
        pull_request_number=None,
        environment=ENVIRONMENT,
        git_sha=revision,
        pack_sha=policy["revision"],
        evaluation_ids=evaluation_ids,
        now=now,
    )
    apply_snapshot(db, job["organization_id"], snapshot["id"])
    return snapshot["id"]

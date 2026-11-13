"""Persist observed scanner scope and guard evaluations that depend on it."""

from datetime import datetime, timezone

from sqlalchemy import insert, select
from sqlalchemy.engine import Connection

from app.assessment import AssessmentResult, AssessmentStatus, determine_assessment
from app.git_source import GitSource
from app.openapi_scanner import scan_repository
from app.tables import repo_bindings, scanner_coverage

OPENAPI_SCANNER = "openapi-v1"
PYTHON_LICENSE_SCANNER = "python-license-v1"


def _serialize(row):
    return {
        "id": row["id"],
        "bindingId": row["binding_id"],
        "scanner": row["scanner"],
        "ref": row["ref"],
        "status": row["status"],
        "commit": row["source_revision"],
        "observedAt": row["observed_at"],
        "files": row["files"],
        "errors": row["errors"],
    }


def get_scan(db: Connection, scan_id: int):
    row = (
        db.execute(select(scanner_coverage).where(scanner_coverage.c.id == scan_id))
        .mappings()
        .one_or_none()
    )
    return _serialize(row) if row is not None else None


def run_openapi_scan(
    db: Connection, binding_id: str, source: GitSource, ref: str, observed_at: datetime
):
    binding = (
        db.execute(select(repo_bindings).where(repo_bindings.c.id == binding_id))
        .mappings()
        .one_or_none()
    )
    if binding is None:
        raise LookupError("Repository binding not found")
    if not isinstance(ref, str) or not ref.strip() or len(ref) > 200:
        raise ValueError("ref must be a nonempty string of at most 200 characters")
    result = scan_repository(
        source,
        ref,
        product_id=binding["product_id"],
        repository_id=binding_id,
        observed_at=observed_at,
    )
    failed_files = {error.path for error in result.errors if error.path}
    successful_files = set(result.files_scanned) - failed_files
    status = (
        "covered"
        if not result.errors
        else "partial"
        if successful_files or result.subjects
        else "failed"
    )
    row = (
        db.execute(
            insert(scanner_coverage)
            .values(
                binding_id=binding_id,
                scanner=OPENAPI_SCANNER,
                ref=ref,
                status=status,
                source_revision=result.commit,
                observed_at=observed_at,
                files=list(result.files_scanned),
                errors=[{"path": e.path, "reason": e.reason} for e in result.errors],
            )
            .returning(scanner_coverage)
        )
        .mappings()
        .one()
    )
    return {**_serialize(row), "subjects": result.subjects}


def scan_covers(
    db: Connection,
    *,
    scan_id: int | None,
    product_id: str,
    binding_id: str,
    ref: str,
    expected_commit: str,
    not_after: datetime | None = None,
    scanner: str = OPENAPI_SCANNER,
):
    """Return whether the latest scan covers the exact binding and revision."""
    if scanner not in (OPENAPI_SCANNER, PYTHON_LICENSE_SCANNER):
        return False
    row = (
        db.execute(
            select(scanner_coverage)
            .select_from(
                scanner_coverage.join(
                    repo_bindings, scanner_coverage.c.binding_id == repo_bindings.c.id
                )
            )
            .where(
                repo_bindings.c.id == binding_id,
                repo_bindings.c.product_id == product_id,
                scanner_coverage.c.scanner == scanner,
                scanner_coverage.c.ref == ref,
            )
            .order_by(
                scanner_coverage.c.observed_at.desc(), scanner_coverage.c.id.desc()
            )
            .limit(1)
        )
        .mappings()
        .one_or_none()
    )
    if not_after is not None:
        if not_after.tzinfo is None or not_after.utcoffset() is None:
            raise ValueError("not_after must be timezone-aware")
        if row is not None:
            observed = row["observed_at"]
            if observed.tzinfo is None:  # SQLite returns naive UTC timestamps.
                observed = observed.replace(tzinfo=timezone.utc)
            if observed > not_after:
                return False
    return not (
        row is None
        or scan_id is None
        or row["id"] != scan_id
        or row["status"] != "covered"
        or row["source_revision"] != expected_commit
        or not expected_commit
    )


def assess_with_scan(
    db: Connection,
    *,
    scan_id: int | None,
    product_id: str,
    binding_id: str,
    ref: str,
    expected_commit: str,
    **assessment_inputs,
) -> AssessmentResult:
    """Evaluate only when the latest scan of the requested scope covered this revision."""
    assessment = determine_assessment(**assessment_inputs)
    if not scan_covers(
        db,
        scan_id=scan_id,
        product_id=product_id,
        binding_id=binding_id,
        ref=ref,
        expected_commit=expected_commit,
    ):
        return AssessmentResult(
            AssessmentStatus.UNKNOWN,
            "Quellabdeckung fehlt oder ist unvollständig",
            assessment.evidence_ids,
        )
    return assessment

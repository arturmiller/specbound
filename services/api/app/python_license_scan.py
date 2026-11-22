"""Scan versioned uv lockfile data without installing or executing packages."""

import re
from concurrent.futures import ThreadPoolExecutor

from app.license_policy import DEFAULT_ALLOWED, evaluate_license
from app.pypi_license_metadata import read_pypi_license
from app.python_lockfiles import find_uv_locks

MAX_TOTAL_PACKAGES = 200
METADATA_WORKERS = 4


def _artifact_key(package):
    return (
        package.source,
        package.name,
        package.version,
        package.artifact_hashes,
        package.has_unhashed_artifacts,
    )


def scan_python_repository(source, ref, *, policy=DEFAULT_ALLOWED, resolve=None):
    """Resolve a Git reference once and scan only the resulting pinned snapshot."""
    fetch = getattr(source, "fetch_python_lockfiles", source.fetch)
    snapshot = fetch(ref)
    return {
        "requestedRef": ref,
        "sourceRevision": snapshot.commit,
        **scan_python_licenses(snapshot.files, policy=policy, resolve=resolve),
    }


def scan_python_licenses(files, *, policy=DEFAULT_ALLOWED, resolve=None):
    """Analyze all supported lockfiles; disclose incomplete coverage explicitly."""
    unsupported = sorted(
        path
        for path in files
        if path.rsplit("/", 1)[-1] in {"poetry.lock", "Pipfile.lock", "pdm.lock"}
        or re.fullmatch(r"pylock(?:\.[^.]+)?\.toml", path.rsplit("/", 1)[-1])
        or path.endswith(".py.uv.lock")
    )
    try:
        locks = find_uv_locks(files)
    except ValueError:
        return {
            "coverage": "UNKNOWN",
            "sourceCoverage": "UNKNOWN",
            "reason": "invalid or unsupported uv.lock",
            "files": [],
            "unsupportedFiles": unsupported,
            "packages": [],
        }
    if not locks:
        return {
            "coverage": "UNKNOWN",
            "sourceCoverage": "UNKNOWN",
            "reason": "no supported lockfile",
            "files": [],
            "unsupportedFiles": unsupported,
            "packages": [],
        }
    total = sum(len(items) for items in locks.values())
    if total > MAX_TOTAL_PACKAGES:
        return {
            "coverage": "UNKNOWN",
            "sourceCoverage": "UNKNOWN",
            "reason": "package limit exceeded",
            "files": sorted(locks),
            "unsupportedFiles": unsupported,
            "packages": [],
        }
    if total == 0:
        return {
            "coverage": "UNKNOWN",
            "sourceCoverage": "UNKNOWN",
            "reason": "no locked packages",
            "files": sorted(locks),
            "unsupportedFiles": unsupported,
            "packages": [],
        }
    observations = {}
    if resolve is None:
        artifacts = {
            _artifact_key(package): package
            for entries in locks.values()
            for package in entries
        }
        # Shared artifacts need one lookup per run. Each lockfile still has
        # its own package entries and evidence provenance.
        with ThreadPoolExecutor(max_workers=METADATA_WORKERS) as executor:
            observations = dict(
                zip(
                    artifacts,
                    executor.map(read_pypi_license, artifacts.values()),
                    strict=True,
                )
            )
    packages = []
    for path, entries in locks.items():
        for package in entries:
            metadata = (
                resolve(package)
                if resolve is not None
                else observations[_artifact_key(package)]
            )
            observed = metadata.get("status") == "OBSERVED"
            expression = metadata.get("expression") if observed else None
            result = evaluate_license(expression, policy) if observed else "UNKNOWN"
            packages.append(
                {
                    "path": path,
                    "name": package.name,
                    "version": package.version,
                    "source": package.source,
                    "markers": list(package.markers),
                    "artifactHashes": []
                    if package.has_unhashed_artifacts
                    else list(package.artifact_hashes),
                    "licenseExpression": expression,
                    "status": result,
                    "metadata": metadata,
                }
            )
    return {
        "coverage": "partial"
        if unsupported or any(item["status"] == "UNKNOWN" for item in packages)
        else "covered",
        "sourceCoverage": "partial"
        if unsupported or any(not entries for entries in locks.values())
        else "covered",
        "reason": "Lockfile entries may include dependencies for other environments; this is not an installed inventory.",
        "files": sorted(locks),
        "unsupportedFiles": unsupported,
        "packages": packages,
    }

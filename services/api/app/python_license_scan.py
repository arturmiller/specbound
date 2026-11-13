"""Scan versioned uv lockfile data without installing or executing packages.

This standalone analysis is not yet an Assessment or an Evidence producer.
"""

import re

from app.license_policy import DEFAULT_ALLOWED, evaluate_license
from app.pypi_license_metadata import read_pypi_license
from app.python_lockfiles import find_uv_locks

MAX_TOTAL_PACKAGES = 200


def scan_python_repository(
    source, ref, *, policy=DEFAULT_ALLOWED, resolve=read_pypi_license
):
    """Resolve a Git reference once and scan only the resulting pinned snapshot."""
    fetch = getattr(source, "fetch_python_lockfiles", source.fetch)
    snapshot = fetch(ref)
    return {
        "requestedRef": ref,
        "sourceRevision": snapshot.commit,
        **scan_python_licenses(snapshot.files, policy=policy, resolve=resolve),
    }


def scan_python_licenses(files, *, policy=DEFAULT_ALLOWED, resolve=read_pypi_license):
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
            "reason": "invalid or unsupported uv.lock",
            "files": [],
            "unsupportedFiles": unsupported,
            "packages": [],
        }
    if not locks:
        return {
            "coverage": "UNKNOWN",
            "reason": "no supported lockfile",
            "files": [],
            "unsupportedFiles": unsupported,
            "packages": [],
        }
    total = sum(len(items) for items in locks.values())
    if total > MAX_TOTAL_PACKAGES:
        return {
            "coverage": "UNKNOWN",
            "reason": "package limit exceeded",
            "files": sorted(locks),
            "unsupportedFiles": unsupported,
            "packages": [],
        }
    if total == 0:
        return {
            "coverage": "UNKNOWN",
            "reason": "no locked packages",
            "files": sorted(locks),
            "unsupportedFiles": unsupported,
            "packages": [],
        }
    packages = []
    for path, entries in locks.items():
        for package in entries:
            metadata = resolve(package)
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
                    "licenseExpression": expression,
                    "status": result,
                    "metadata": metadata,
                }
            )
    return {
        "coverage": "partial"
        if unsupported or any(item["status"] == "UNKNOWN" for item in packages)
        else "covered",
        "reason": "Lockfile entries may include dependencies for other environments; this is not an installed inventory.",
        "files": sorted(locks),
        "unsupportedFiles": unsupported,
        "packages": packages,
    }

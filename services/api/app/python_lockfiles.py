"""Read pinned Python dependencies without executing repository code."""

import re
import tomllib
from dataclasses import dataclass

MAX_LOCK_BYTES = 2 * 1024 * 1024
MAX_PACKAGES = 1000
NAME = re.compile(r"[A-Za-z0-9]+(?:[-_.][A-Za-z0-9]+)*")
HASH = re.compile(r"sha256:[0-9a-f]{64}")


@dataclass(frozen=True)
class LockedPackage:
    path: str
    name: str
    version: str
    source: str
    artifact_hashes: tuple[str, ...]
    # Universal lockfiles include packages for different environments. Nothing
    # here claims a given dependency is actually installed or deployed.
    markers: tuple[str, ...]
    has_unhashed_artifacts: bool = False


def parse_uv_lock(path: str, data: bytes) -> tuple[LockedPackage, ...]:
    if not isinstance(data, bytes) or len(data) > MAX_LOCK_BYTES:
        raise ValueError("lockfile too large or invalid")
    try:
        document = tomllib.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, tomllib.TOMLDecodeError) as exc:
        raise ValueError("invalid uv.lock") from exc
    version = document.get("version")
    revision = document.get("revision", 0)
    if (
        type(version) is not int
        or version != 1
        or type(revision) is not int
        or not 0 <= revision <= 3
    ):
        raise ValueError("unsupported uv.lock version")
    packages = document.get("package", [])
    if not isinstance(packages, list) or len(packages) > MAX_PACKAGES:
        raise ValueError("invalid or too many packages")
    result = []
    identities = set()
    for entry in packages:
        if not isinstance(entry, dict):
            raise ValueError("invalid package entry")
        name, version, source = (
            entry.get("name"),
            entry.get("version"),
            entry.get("source"),
        )
        if not isinstance(name, str) or not NAME.fullmatch(name) or len(name) > 200:
            raise ValueError("invalid package name")
        if not isinstance(version, str) or not version or len(version) > 200:
            raise ValueError("missing package version")
        if not isinstance(source, dict) or len(source) != 1:
            raise ValueError("invalid package source")
        source_type, source_value = next(iter(source.items()))
        if not isinstance(source_type, str) or not isinstance(source_value, str):
            raise ValueError("invalid package source")
        # Only the canonical public PyPI registry may be queried. Other sources
        # are retained as unknown; their URLs are never fetched by this parser.
        registry = (
            source_type == "registry"
            and source_value.rstrip("/") == "https://pypi.org/simple"
        )
        hashes = []
        has_unhashed_artifacts = False
        artifacts = entry.get("wheels", [])
        if not isinstance(artifacts, list):
            raise ValueError("invalid wheel list")
        if "sdist" in entry:
            artifacts = [*artifacts, entry["sdist"]]
        for artifact in artifacts:
            if not isinstance(artifact, dict):
                raise ValueError("invalid artifact")
            digest = artifact.get("hash")
            if digest is not None and (
                not isinstance(digest, str) or not HASH.fullmatch(digest)
            ):
                raise ValueError("invalid artifact hash")
            if digest:
                hashes.append(digest.removeprefix("sha256:"))
            else:
                has_unhashed_artifacts = True
        markers = entry.get("resolution-markers", [])
        if not isinstance(markers, list) or any(
            not isinstance(m, str) for m in markers
        ):
            raise ValueError("invalid resolution markers")
        name = re.sub(r"[-_.]+", "-", name).lower()
        identity = (name, version, source_type, source_value, tuple(markers))
        if identity in identities:
            raise ValueError("duplicate package entry")
        identities.add(identity)
        result.append(
            LockedPackage(
                path,
                name,
                version,
                "pypi" if registry else f"unsupported:{source_type}",
                tuple(sorted(set(hashes))),
                tuple(markers),
                has_unhashed_artifacts,
            )
        )
    return tuple(result)


def find_uv_locks(files: dict[str, bytes]) -> dict[str, tuple[LockedPackage, ...]]:
    """Find exact uv.lock paths; failure in any file fails the whole scan."""
    return {
        path: parse_uv_lock(path, content)
        for path, content in sorted(files.items())
        if path == "uv.lock" or path.endswith("/uv.lock")
    }

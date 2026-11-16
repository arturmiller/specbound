"""Load a pack at a safe manifest path from one immutable Git snapshot."""

import hashlib
import re
from pathlib import PurePosixPath

from app.git_source import GitSnapshot
from app.governance_pack import load_governance_pack
from app.manifest_io import ManifestError
from app.provider_pack import load_provider_pack

MANIFEST_PATH = re.compile(r"(?:[A-Za-z0-9_.-]+/)*[A-Za-z0-9_.-]+\.(?:json|yaml|yml)")


def checked_manifest_path(path):
    if (
        not isinstance(path, str)
        or len(path) > 500
        or not MANIFEST_PATH.fullmatch(path)
        or any(part in (".", "..") for part in path.split("/"))
    ):
        raise ManifestError("Manifest path must be a safe relative repository path")
    return path


def snapshot_for_ref(source, repository, ref, ref_kind):
    """Resolve an explicit GitHub ref kind once, without ambiguous tag/branch names."""
    if getattr(source, "repository", repository) != repository:
        raise ValueError("Source repository does not match request")
    if ref_kind not in ("tag", "branch", "commit"):
        raise ValueError("Unsupported Git ref kind")
    commit = source.resolve_tag(ref) if ref_kind == "tag" else ref
    if ref_kind != "branch" and not re.fullmatch(
        r"(?:[0-9a-f]{40}|[0-9a-f]{64})", commit
    ):
        raise ValueError("A full commit is required")
    snapshot = source.fetch("heads/" + ref if ref_kind == "branch" else commit)
    if ref_kind != "branch" and snapshot.commit != commit:
        raise ValueError("Snapshot did not match resolved commit")
    return snapshot


def content_digest(files):
    digest = hashlib.sha256()
    for path in sorted(files):
        name, content = path.encode(), files[path]
        digest.update(len(name).to_bytes(8, "big") + name)
        digest.update(len(content).to_bytes(8, "big") + content)
    return digest.hexdigest()


def load_pack_at(snapshot: GitSnapshot, manifest_path, kind):
    checked_manifest_path(manifest_path)
    if manifest_path not in snapshot.files:
        raise ManifestError("Manifest file was not found in this revision")
    if kind not in ("governance", "provider"):
        raise ManifestError("Unsupported pack kind")
    directory = str(PurePosixPath(manifest_path).parent)
    prefix = "" if directory == "." else directory + "/"
    local = {
        name[len(prefix) :]: content
        for name, content in snapshot.files.items()
        if name.startswith(prefix)
    }
    canonical = "pack.yaml" if kind == "governance" else "provider.yaml"
    local[canonical] = snapshot.files[manifest_path]
    loaded = (load_governance_pack if kind == "governance" else load_provider_pack)(
        GitSnapshot(snapshot.commit, local)
    )
    manifest = loaded["manifest"]
    paths = {canonical}
    if kind == "governance":
        paths.update(manifest["controls"])
    else:
        paths.update(loaded["schemas"])
        paths.update(manifest.get("tests", []))
    return {
        **loaded,
        "contentDigest": content_digest({path: local[path] for path in paths}),
    }

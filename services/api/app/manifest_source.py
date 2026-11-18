"""Load a pack at a safe manifest path from one immutable Git snapshot."""

import hashlib
import re
from collections.abc import Mapping
from pathlib import PurePosixPath
from types import SimpleNamespace

from app.git_source import GitSnapshot, SourceRevisionChanged
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


def load_resource_for_ref(
    source, repository, ref, ref_kind, manifest_path, loader, *, expected_commit=None
):
    """Read only the parser's declared files when the source supports scoped reads."""
    checked_manifest_path(manifest_path)
    if getattr(source, "repository", repository) != repository:
        raise ValueError("Source repository does not match request")

    def checked_load(snapshot, path):
        if expected_commit is not None and snapshot.commit != expected_commit:
            raise SourceRevisionChanged(
                "Source changed after preview; check the new revision first"
            )
        return loader(snapshot, path)

    read = getattr(source, "load_resource", None)
    if callable(read):
        return read(ref, manifest_path, checked_load, ref_kind=ref_kind)
    snapshot = snapshot_for_ref(source, repository, ref, ref_kind)
    return snapshot, checked_load(snapshot, manifest_path)


class _PackFiles(Mapping):
    """A read-through view, preserving the pack parser's canonical manifest name."""

    def __init__(self, files, prefix, manifest_path, canonical):
        self.files, self.prefix = files, prefix
        self.manifest_path, self.canonical = manifest_path, canonical

    def __getitem__(self, path):
        return self.files[
            self.manifest_path if path == self.canonical else self.prefix + path
        ]

    def __iter__(self):
        names = {
            name[len(self.prefix) :]
            for name in self.files
            if name.startswith(self.prefix)
        }
        return iter(sorted(names | {self.canonical}))

    def __len__(self):
        return sum(1 for _ in self)


def load_pack_at(snapshot: GitSnapshot, manifest_path, kind):
    checked_manifest_path(manifest_path)
    if manifest_path not in snapshot.files:
        raise ManifestError("Manifest file was not found in this revision")
    if kind not in ("governance", "provider"):
        raise ManifestError("Unsupported pack kind")
    directory = str(PurePosixPath(manifest_path).parent)
    prefix = "" if directory == "." else directory + "/"
    canonical = "pack.yaml" if kind == "governance" else "provider.yaml"
    local = _PackFiles(snapshot.files, prefix, manifest_path, canonical)
    loaded = (load_governance_pack if kind == "governance" else load_provider_pack)(
        SimpleNamespace(commit=snapshot.commit, files=local)
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

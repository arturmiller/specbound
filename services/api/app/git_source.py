"""Hosting-independent Git source boundary; implementations are adapters."""

import re
from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping, Protocol


class GitSourceError(Exception):
    """Base class for expected source failures."""


class InvalidGitReference(GitSourceError):
    """The supplied ref or tag is malformed."""


class SourceNotFound(GitSourceError):
    """The repository, ref, or tag was not found or is not accessible."""


class SourceUnavailable(GitSourceError):
    """The source could not be reached or its contents could not be read."""


@dataclass(frozen=True)
class GitSnapshot:
    """Files observed at a resolved Git commit, never a mutable tag or branch."""

    commit: str
    files: Mapping[str, bytes]

    def __post_init__(self):
        if not isinstance(self.commit, str) or not re.fullmatch(
            r"(?:[0-9a-f]{40}|[0-9a-f]{64})", self.commit
        ):
            raise ValueError("commit must be a full lowercase Git object ID")
        if not isinstance(self.files, Mapping):
            raise ValueError("files must be a mapping")
        for path, content in self.files.items():
            if (
                not isinstance(path, str)
                or not path
                or "\\" in path
                or "\0" in path
                or any(part in ("", ".", "..") for part in path.split("/"))
                or not isinstance(content, bytes)
            ):
                raise ValueError("files require safe relative paths and byte contents")
        object.__setattr__(self, "files", MappingProxyType(dict(sorted(self.files.items()))))


class GitSource(Protocol):
    """One adapter instance addresses one configured repository."""

    def fetch(self, ref: str) -> GitSnapshot:
        """Resolve a ref and return its files and immutable commit ID."""
        ...

    def resolve_tag(self, tag: str) -> str:
        """Resolve a tag, including annotated tags, to its full commit ID."""
        ...

    def verify_webhook(self, headers: Mapping[str, str], payload: bytes) -> bool:
        """Verify raw bytes using this adapter's configured provider credentials."""
        ...

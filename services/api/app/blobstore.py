"""Provider-neutral interface for binary objects."""

from typing import Protocol


class BlobStoreError(Exception):
    """The object store could not complete the requested operation."""


class BlobNotFound(BlobStoreError):
    """No object exists at the requested key."""


class InvalidBlobKey(ValueError):
    """An object key is outside the portable key contract."""


def validate_key(key: str) -> None:
    if (
        not isinstance(key, str)
        or not key.strip()
        or len(key.encode("utf-8")) > 1024
        or "\0" in key
        or "\\" in key
        or any(part in ("", ".", "..") for part in key.split("/"))
    ):
        raise InvalidBlobKey("key must be a safe relative object key")


class BlobStore(Protocol):
    def put(self, key: str, data: bytes) -> None:
        """Create or replace an object at key."""
        ...

    def get(self, key: str) -> bytes:
        """Return exact bytes, or raise BlobNotFound."""
        ...

    def delete(self, key: str) -> None:
        """Delete an object; deleting a missing key is idempotent."""
        ...

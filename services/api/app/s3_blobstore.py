"""S3-compatible object-store adapter with explicit endpoint and credentials."""

import os
from contextlib import closing
from urllib.parse import urlsplit

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError

from app.blobstore import BlobNotFound, BlobStoreError, validate_key


class S3BlobStore:
    def __init__(
        self,
        *,
        endpoint: str,
        bucket: str,
        access_key: str,
        secret_key: str,
        connect_timeout: int = 5,
        read_timeout: int = 30,
        retries: int = 2,
    ):
        parsed = urlsplit(endpoint)
        if (
            parsed.scheme not in ("http", "https")
            or not parsed.hostname
            or parsed.username
            or parsed.password
            or parsed.query
            or parsed.fragment
            or parsed.path not in ("", "/")
            or not all((bucket, access_key, secret_key))
        ):
            raise ValueError(
                "S3 endpoint, bucket and explicit credentials are required"
            )
        self._bucket = bucket
        self._client = boto3.client(
            "s3",
            endpoint_url=endpoint,
            region_name="us-east-1",
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            config=Config(
                signature_version="s3v4",
                s3={"addressing_style": "path"},
                connect_timeout=connect_timeout,
                read_timeout=read_timeout,
                retries={"max_attempts": retries},
            ),
        )

    def check_ready(self) -> None:
        """Check bucket availability without creating or modifying objects."""
        try:
            self._client.head_bucket(Bucket=self._bucket)
        except (BotoCoreError, ClientError, OSError) as exc:
            raise BlobStoreError("object store unavailable") from exc

    def put(self, key: str, data: bytes) -> None:
        validate_key(key)
        if not isinstance(data, bytes):
            raise TypeError("data must be bytes")
        try:
            self._client.put_object(Bucket=self._bucket, Key=key, Body=data)
        except (BotoCoreError, ClientError) as exc:
            raise BlobStoreError("object write failed") from exc

    def get(self, key: str) -> bytes:
        validate_key(key)
        try:
            response = self._client.get_object(Bucket=self._bucket, Key=key)
            with closing(response["Body"]) as body:
                return body.read()
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") in (
                "NoSuchKey",
                "NotFound",
                "404",
            ):
                raise BlobNotFound("object not found") from exc
            raise BlobStoreError("object read failed") from exc
        except (BotoCoreError, OSError) as exc:
            raise BlobStoreError("object read failed") from exc

    def delete(self, key: str) -> None:
        validate_key(key)
        try:
            self._client.delete_object(Bucket=self._bucket, Key=key)
        except (BotoCoreError, ClientError) as exc:
            raise BlobStoreError("object deletion failed") from exc


def configured_blobstore(
    *, connect_timeout: int = 5, read_timeout: int = 30, retries: int = 2
) -> S3BlobStore:
    """Build the adapter only from explicit configuration, never instance credentials."""
    return S3BlobStore(
        endpoint=os.environ.get("BLOBSTORE_ENDPOINT", ""),
        bucket=os.environ.get("BLOBSTORE_BUCKET", ""),
        access_key=os.environ.get("BLOBSTORE_ACCESS_KEY", ""),
        secret_key=os.environ.get("BLOBSTORE_SECRET_KEY", ""),
        connect_timeout=connect_timeout,
        read_timeout=read_timeout,
        retries=retries,
    )

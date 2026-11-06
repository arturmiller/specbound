"""BlobStore contract against the MinIO service started by Docker Compose."""

import os
import unittest
from uuid import uuid4

from app.blobstore import BlobNotFound, BlobStoreError, InvalidBlobKey
from app.s3_blobstore import S3BlobStore


class MinioBlobStoreContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        names = (
            "BLOBSTORE_ENDPOINT",
            "BLOBSTORE_BUCKET",
            "BLOBSTORE_ACCESS_KEY",
            "BLOBSTORE_SECRET_KEY",
        )
        if any(not os.environ.get(name) for name in names):
            raise RuntimeError(
                "A disposable Compose MinIO endpoint and credentials are required"
            )
        cls.store = S3BlobStore(
            endpoint=os.environ[names[0]],
            bucket=os.environ[names[1]],
            access_key=os.environ[names[2]],
            secret_key=os.environ[names[3]],
        )

    def setUp(self):
        self.prefix = f"test/{uuid4()}"

    def test_put_get_overwrite_delete_and_missing(self):
        key = f"{self.prefix}/résumé binary.bin"
        try:
            self.store.put(key, b"\x00hello\xff")
            self.assertEqual(self.store.get(key), b"\x00hello\xff")
            self.store.put(key, b"replacement")
            self.assertEqual(self.store.get(key), b"replacement")
            self.store.delete(key)
            with self.assertRaises(BlobNotFound):
                self.store.get(key)
            self.store.delete(key)
        finally:
            self.store.delete(key)

    def test_empty_content_and_independent_keys(self):
        first, second = self.prefix + "/one", self.prefix + "/two"
        try:
            self.store.put(first, b"")
            self.store.put(second, b"other")
            self.assertEqual(self.store.get(first), b"")
            self.assertEqual(self.store.get(second), b"other")
            self.store.delete(first)
            self.assertEqual(self.store.get(second), b"other")
        finally:
            self.store.delete(first)
            self.store.delete(second)

    def test_invalid_keys_and_content_are_rejected(self):
        for key in ("", "/absolute", "a/../b", "a//b", "null\0byte", "a\\b"):
            with self.subTest(key=key), self.assertRaises(InvalidBlobKey):
                self.store.put(key, b"data")
        with self.assertRaises(TypeError):
            self.store.put(self.prefix, "not bytes")

    def test_access_failure_is_not_treated_as_a_missing_object(self):
        denied = S3BlobStore(
            endpoint=os.environ["BLOBSTORE_ENDPOINT"],
            bucket=os.environ["BLOBSTORE_BUCKET"],
            access_key=os.environ["BLOBSTORE_ACCESS_KEY"],
            secret_key="intentionally-incorrect-secret",
        )
        with self.assertRaises(BlobStoreError) as caught:
            denied.get(self.prefix + "/missing")
        self.assertNotIsInstance(caught.exception, BlobNotFound)


if __name__ == "__main__":
    unittest.main()

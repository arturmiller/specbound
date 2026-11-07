"""Backups preserve object keys and bytes and never overwrite a nonempty bucket."""

import io
import json
import unittest
import zipfile

from app.object_archive import (
    ArchiveError,
    export_objects,
    restore_objects,
    verify_archive,
)


class FakePaginator:
    def __init__(self, client):
        self.client = client

    def paginate(self, *, Bucket):
        yield {"Contents": [{"Key": key} for key in self.client.objects]}


class FakeS3:
    def __init__(self, objects=None):
        self.objects = dict(objects or {})

    def get_paginator(self, _name):
        return FakePaginator(self)

    def get_object(self, *, Bucket, Key):
        data = self.objects[Key]
        return {"Body": io.BytesIO(data), "ContentLength": len(data)}

    def list_objects_v2(self, *, Bucket, MaxKeys):
        return {"Contents": [{"Key": key} for key in list(self.objects)[:MaxKeys]]}

    def put_object(self, *, Bucket, Key, Body, ContentLength):
        data = Body.read()
        if len(data) != ContentLength:
            raise AssertionError("Unexpected content length")
        self.objects[Key] = data


class ObjectArchiveTest(unittest.TestCase):
    def test_round_trip_preserves_exact_keys_and_bytes(self):
        source = FakeS3(
            {"evidence/a": b"\0\xff", "ü/nested": b"", "../not-a-path": b"data"}
        )
        output = io.BytesIO()
        export_objects(source, "source", output)
        target = FakeS3()
        output.seek(0)
        self.assertEqual(verify_archive(output), 3)
        output.seek(0)
        self.assertEqual(restore_objects(target, "target", output), 3)
        self.assertEqual(target.objects, source.objects)

    def test_nonempty_destination_and_corrupt_archive_never_write(self):
        output = io.BytesIO()
        export_objects(FakeS3({"one": b"original"}), "source", output)
        target = FakeS3({"existing": b"keep"})
        output.seek(0)
        with self.assertRaises(ArchiveError):
            restore_objects(target, "target", output)
        self.assertEqual(target.objects, {"existing": b"keep"})
        bad = io.BytesIO()
        with zipfile.ZipFile(bad, "w") as archive:
            archive.writestr("objects/00000000", b"modified")
            archive.writestr(
                "manifest.json",
                json.dumps(
                    {
                        "version": 1,
                        "objects": [
                            {
                                "key": "one",
                                "entry": "objects/00000000",
                                "size": 8,
                                "sha256": "0" * 64,
                            }
                        ],
                    }
                ),
            )
        target = FakeS3()
        bad.seek(0)
        with self.assertRaises(ArchiveError):
            restore_objects(target, "target", bad)
        self.assertEqual(target.objects, {})

"""Stream local object backups without treating object keys as file paths."""

import hashlib
import json
import re
import shutil
import tempfile
import zipfile
from contextlib import closing, contextmanager

CHUNK = 1024 * 1024
MAX_OBJECTS = 10_000
MAX_OBJECT_BYTES = 5 * 1024**3
MAX_ARCHIVE_BYTES = 8 * 1024**3
MAX_MANIFEST_BYTES = 8 * 1024**2


class ArchiveError(ValueError):
    """An archive is invalid, too large, or cannot be restored safely."""


def _key_valid(key):
    return isinstance(key, str) and bool(key) and len(key.encode("utf-8")) <= 1024


def export_objects(client, bucket, output):
    """Back up current object bytes to a ZIP stream with a checksummed manifest."""
    objects, seen, total = [], set(), 0
    with tempfile.TemporaryFile(mode="w+b") as temp:
        with zipfile.ZipFile(
            temp, "w", compression=zipfile.ZIP_STORED, allowZip64=True
        ) as archive:
            for page in client.get_paginator("list_objects_v2").paginate(Bucket=bucket):
                for item in page.get("Contents", []):
                    key = item["Key"]
                    if (
                        not _key_valid(key)
                        or key in seen
                        or len(objects) >= MAX_OBJECTS
                    ):
                        raise ArchiveError("Invalid or excessive object keys")
                    seen.add(key)
                    response = client.get_object(Bucket=bucket, Key=key)
                    size = response["ContentLength"]
                    if type(size) is not int or not 0 <= size <= MAX_OBJECT_BYTES:
                        raise ArchiveError("Object exceeds backup size limit")
                    total += size
                    if total > MAX_ARCHIVE_BYTES:
                        raise ArchiveError("Archive exceeds backup size limit")
                    entry = f"objects/{len(objects):08d}"
                    digest, actual = hashlib.sha256(), 0
                    with (
                        closing(response["Body"]) as body,
                        archive.open(entry, "w", force_zip64=True) as target,
                    ):
                        while data := body.read(CHUNK):
                            actual += len(data)
                            if actual > size:
                                raise ArchiveError("Object changed during backup")
                            digest.update(data)
                            target.write(data)
                    if actual != size:
                        raise ArchiveError("Object changed during backup")
                    objects.append(
                        {
                            "key": key,
                            "entry": entry,
                            "size": size,
                            "sha256": digest.hexdigest(),
                        }
                    )
            manifest = json.dumps(
                {"version": 1, "objects": objects},
                ensure_ascii=False,
                separators=(",", ":"),
            ).encode("utf-8")
            if len(manifest) > MAX_MANIFEST_BYTES:
                raise ArchiveError("Manifest exceeds backup size limit")
            archive.writestr("manifest.json", manifest)
        if temp.tell() > MAX_ARCHIVE_BYTES:
            raise ArchiveError("Archive exceeds backup size limit")
        temp.seek(0)
        shutil.copyfileobj(temp, output, CHUNK)
    return len(objects)


def _pairs(items):
    result = {}
    for key, value in items:
        if key in result:
            raise ArchiveError("Duplicate manifest key")
        result[key] = value
    return result


@contextmanager
def _verified(stream):
    with tempfile.TemporaryFile(mode="w+b") as temp:
        total = 0
        while data := stream.read(CHUNK):
            total += len(data)
            if total > MAX_ARCHIVE_BYTES:
                raise ArchiveError("Archive exceeds backup size limit")
            temp.write(data)
        temp.seek(0)
        try:
            with zipfile.ZipFile(temp, "r") as archive:
                infos = archive.infolist()
                names = [info.filename for info in infos]
                if len(names) != len(set(names)) or "manifest.json" not in names:
                    raise ArchiveError("Archive entries are invalid")
                manifest_info = archive.getinfo("manifest.json")
                if manifest_info.file_size > MAX_MANIFEST_BYTES:
                    raise ArchiveError("Manifest exceeds backup size limit")
                if any(
                    info.is_dir()
                    or info.compress_type != zipfile.ZIP_STORED
                    or info.flag_bits & 1
                    for info in infos
                ):
                    raise ArchiveError(
                        "Compressed, encrypted or directory entries are unsupported"
                    )
                manifest = json.loads(
                    archive.read(manifest_info).decode("utf-8"),
                    object_pairs_hook=_pairs,
                )
                if (
                    not isinstance(manifest, dict)
                    or set(manifest) != {"version", "objects"}
                    or type(manifest["version"]) is not int
                    or manifest["version"] != 1
                    or not isinstance(manifest["objects"], list)
                    or len(manifest["objects"]) > MAX_OBJECTS
                ):
                    raise ArchiveError("Invalid backup manifest")
                objects, keys = manifest["objects"], set()
                expected_names = {"manifest.json"}
                for index, item in enumerate(objects):
                    if not isinstance(item, dict) or set(item) != {
                        "key",
                        "entry",
                        "size",
                        "sha256",
                    }:
                        raise ArchiveError("Invalid object entry")
                    key, entry, size, checksum = (
                        item["key"],
                        item["entry"],
                        item["size"],
                        item["sha256"],
                    )
                    if (
                        not _key_valid(key)
                        or key in keys
                        or entry != f"objects/{index:08d}"
                        or type(size) is not int
                        or not 0 <= size <= MAX_OBJECT_BYTES
                        or not isinstance(checksum, str)
                        or not re.fullmatch(r"[0-9a-f]{64}", checksum)
                    ):
                        raise ArchiveError("Invalid object metadata")
                    keys.add(key)
                    expected_names.add(entry)
                    info = archive.getinfo(entry)
                    if info.file_size != size or info.compress_size != size:
                        raise ArchiveError("Object size does not match manifest")
                    digest = hashlib.sha256()
                    with archive.open(info) as body:
                        while data := body.read(CHUNK):
                            digest.update(data)
                    if digest.hexdigest() != checksum:
                        raise ArchiveError("Object checksum does not match manifest")
                if set(names) != expected_names:
                    raise ArchiveError("Archive has unexpected entries")
                yield archive, objects
        except (
            zipfile.BadZipFile,
            KeyError,
            UnicodeError,
            json.JSONDecodeError,
            RuntimeError,
        ) as exc:
            raise ArchiveError("Invalid object backup archive") from exc


def verify_archive(stream):
    with _verified(stream) as (_archive, objects):
        return len(objects)


def ensure_empty(client, bucket):
    if client.list_objects_v2(Bucket=bucket, MaxKeys=1).get("Contents"):
        raise ArchiveError("Destination bucket is not empty")


def restore_objects(client, bucket, stream):
    """Validate the whole archive before writing into an empty bucket."""
    with _verified(stream) as (archive, objects):
        ensure_empty(client, bucket)
        for item in objects:
            with archive.open(item["entry"]) as body:
                client.put_object(
                    Bucket=bucket,
                    Key=item["key"],
                    Body=body,
                    ContentLength=item["size"],
                )
        return len(objects)

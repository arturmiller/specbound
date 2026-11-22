"""Read bounded, hash-checked distribution metadata from public PyPI only."""

import gzip
import hashlib
import io
import json
import re
import tarfile
import zlib
from email import policy
from email.parser import BytesParser
from functools import partial
from tempfile import SpooledTemporaryFile
from urllib.parse import quote, urlsplit

import httpx

from app.license_policy import canonical_license_id

MAX_INDEX_BYTES = 32 * 1024 * 1024
MAX_METADATA_BYTES = 1024 * 1024
MAX_SDIST_BYTES = 20 * 1024 * 1024
MAX_SDIST_UNPACKED = 96 * 1024 * 1024
MAX_SDIST_ENTRIES = 10000
MAX_ARTIFACTS = 160
SHA256 = re.compile(r"[0-9a-f]{64}")

LEGACY_LICENSE_NAMES = {
    "mit license": "MIT",
    "apache license 2.0": "Apache-2.0",
}

LICENSE_CLASSIFIERS = {
    "MIT License": {"MIT"},
    "BSD License": {"BSD-2-Clause", "BSD-3-Clause", "BSD-4-Clause"},
    "Apache Software License": {"Apache-2.0"},
    "Mozilla Public License 2.0 (MPL 2.0)": {"MPL-2.0"},
}


class _UnresolvedLicense(ValueError):
    """A known reason why an artifact's license could not be resolved."""


def _fetch(client, url, *, accept, limit):
    data = bytearray()
    with client.stream(
        "GET",
        url,
        headers={
            "Accept": accept,
            "Accept-Encoding": "identity",
            "User-Agent": "Specbound-License-Scanner/1",
        },
    ) as response:
        response.raise_for_status()
        if response.headers.get("content-encoding", "identity").lower() != "identity":
            raise ValueError("unexpected metadata content encoding")
        for chunk in response.iter_raw(chunk_size=65536):
            if len(data) + len(chunk) > limit:
                raise ValueError("response too large")
            data.extend(chunk)
    return bytes(data)


def _artifact_url(url):
    if not isinstance(url, str) or len(url) > 4096:
        raise ValueError("invalid artifact URL")
    parsed = urlsplit(url)
    if (
        parsed.scheme != "https"
        or parsed.netloc != "files.pythonhosted.org"
        or not parsed.path.startswith("/packages/")
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("untrusted artifact URL")
    return url


def _metadata_url(url):
    return _artifact_url(url) + ".metadata"


def _sdist_metadata(artifact):
    """Read root PKG-INFO from bounded bytes without extracting archive paths."""
    with (
        gzip.GzipFile(fileobj=io.BytesIO(artifact)) as stream,
        SpooledTemporaryFile(max_size=MAX_METADATA_BYTES) as unpacked,
    ):
        remaining = MAX_SDIST_UNPACKED
        while chunk := stream.read(min(65536, remaining + 1)):
            remaining -= len(chunk)
            if remaining < 0:
                raise _UnresolvedLicense("source archive exceeds size limit")
            unpacked.write(chunk)
        unpacked.seek(0)
        return _read_pkg_info(unpacked)


def _read_pkg_info(unpacked):
    found = None
    with tarfile.open(fileobj=unpacked, mode="r:") as archive:
        for index, member in enumerate(archive):
            if index >= MAX_SDIST_ENTRIES:
                raise ValueError("source archive has too many entries")
            parts = member.name.split("/")
            if len(parts) != 2 or parts[1] != "PKG-INFO":
                continue
            if (
                found is not None
                or not member.isfile()
                or member.size > MAX_METADATA_BYTES
            ):
                raise ValueError("ambiguous or invalid source metadata")
            stream = archive.extractfile(member)
            if stream is None:
                raise ValueError("source metadata unavailable")
            found = stream.read(MAX_METADATA_BYTES + 1)
    if found is None or len(found) > MAX_METADATA_BYTES:
        raise ValueError("source metadata unavailable")
    return found


def _metadata(content, name, version):
    message = BytesParser(policy=policy.compat32).parsebytes(content, headersonly=True)
    if message.defects:
        raise ValueError("invalid metadata")
    names = message.get_all("Name", [])
    versions = message.get_all("Version", [])
    expressions = message.get_all("License-Expression", [])
    dynamic = {str(item).strip().lower() for item in message.get_all("Dynamic", [])}
    normalized_name = (
        re.sub(r"[-_.]+", "-", str(names[0])).lower() if len(names) == 1 else None
    )
    if normalized_name != name or versions != [version]:
        raise ValueError("metadata package mismatch")
    if "license-expression" in dynamic:
        raise _UnresolvedLicense("dynamic license declaration")
    if expressions:
        if len(expressions) != 1 or not str(expressions[0]).strip():
            raise _UnresolvedLicense("ambiguous license expression")
        return {
            "licenseExpression": str(expressions[0]).strip(),
            "licenseField": "License-Expression",
        }
    legacy = message.get_all("License", [])
    if "license" in dynamic or len(legacy) != 1:
        raise _UnresolvedLicense("no static license declaration")
    declared = str(legacy[0]).strip()
    expression = LEGACY_LICENSE_NAMES.get(declared.casefold()) or canonical_license_id(
        declared
    )
    if not expression:
        raise _UnresolvedLicense("ambiguous legacy license declaration")
    classifiers = {
        str(item).strip()
        for item in message.get_all("Classifier", [])
        if str(item).strip().startswith("License :: ")
    }
    classifiers.discard("License :: OSI Approved")
    if len(classifiers) > 1 or any(
        expression
        not in LICENSE_CLASSIFIERS.get(
            classifier.removeprefix("License :: OSI Approved :: "), ()
        )
        for classifier in classifiers
    ):
        raise _UnresolvedLicense("ambiguous legacy license classifiers")
    return {
        "licenseExpression": expression,
        "licenseField": "License",
        "declaredLicense": declared,
    }


def read_pypi_license(package, fetch=None):
    """Return exact-artifact declarations or an explicit unresolved reason.

    We do not infer a distribution's license from project classifiers or
    another distribution. Every hashed artifact in the lock must be resolved.
    """
    if package.source != "pypi":
        return {"status": "UNKNOWN", "reason": "unsupported package source"}
    hashes = set(package.artifact_hashes)
    if package.has_unhashed_artifacts or not hashes:
        return {
            "status": "UNKNOWN",
            "reason": "artifact hashes missing",
        }
    if len(hashes) > MAX_ARTIFACTS:
        return {"status": "UNKNOWN", "reason": "too many locked artifacts"}
    if fetch is not None:
        return _read_pypi_license(package, hashes, fetch)
    # Keep connections scoped to this release and never use ambient credentials,
    # proxies or redirects.
    with httpx.Client(timeout=10, follow_redirects=False, trust_env=False) as client:
        return _read_pypi_license(package, hashes, partial(_fetch, client))


def _read_pypi_license(package, hashes, fetch):
    index_url = f"https://pypi.org/simple/{quote(package.name, safe='')}/"
    try:
        body = fetch(
            index_url,
            accept="application/vnd.pypi.simple.v1+json",
            limit=MAX_INDEX_BYTES,
        )
        index = json.loads(body)
        files = index.get("files")
        if not isinstance(files, list):
            raise ValueError("invalid index")
        matches = {}
        for item in files:
            if not isinstance(item, dict) or not isinstance(item.get("hashes"), dict):
                continue
            digest = item["hashes"].get("sha256")
            if digest in hashes:
                if digest in matches:
                    raise ValueError("ambiguous artifact hash")
                matches[digest] = item
        if set(matches) != hashes:
            raise ValueError("locked artifacts missing in index")
        declarations = []
        for digest, item in sorted(matches.items()):
            metadata_hashes = item.get("core-metadata", item.get("dist-info-metadata"))
            metadata_hash = (
                metadata_hashes.get("sha256")
                if isinstance(metadata_hashes, dict)
                else None
            )
            if isinstance(metadata_hash, str) and SHA256.fullmatch(metadata_hash):
                url = _metadata_url(item.get("url"))
                source_kind = "distribution-metadata"
                data = fetch(url, accept="text/plain", limit=MAX_METADATA_BYTES)
                if hashlib.sha256(data).hexdigest() != metadata_hash:
                    raise ValueError("metadata hash mismatch")
            else:
                url = _artifact_url(item.get("url"))
                source_kind = "source-archive-pkg-info"
                if not url.endswith(".tar.gz"):
                    raise ValueError("verified distribution metadata unavailable")
                artifact = fetch(
                    url, accept="application/octet-stream", limit=MAX_SDIST_BYTES
                )
                if hashlib.sha256(artifact).hexdigest() != digest:
                    raise ValueError("source archive hash mismatch")
                data = _sdist_metadata(artifact)
                metadata_hash = hashlib.sha256(data).hexdigest()
            declarations.append(
                {
                    "artifactSha256": digest,
                    "metadataSha256": metadata_hash,
                    "sourceUrl": url,
                    "sourceKind": source_kind,
                    **_metadata(data, package.name, package.version),
                }
            )
        expressions = {item["licenseExpression"] for item in declarations}
        if len(expressions) != 1:
            return {
                "status": "UNKNOWN",
                "reason": "artifact license expressions differ",
                "artifacts": declarations,
            }
        return {
            "status": "OBSERVED",
            "expression": expressions.pop(),
            "artifacts": declarations,
        }
    except _UnresolvedLicense as exc:
        return {"status": "UNKNOWN", "reason": str(exc)}
    except (
        ValueError,
        TypeError,
        AttributeError,
        KeyError,
        json.JSONDecodeError,
        httpx.HTTPError,
        TimeoutError,
        OSError,
        EOFError,
        tarfile.TarError,
        zlib.error,
    ):
        return {
            "status": "UNKNOWN",
            "reason": "artifact license metadata unavailable or invalid",
        }

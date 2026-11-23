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

from app.license_policy import (
    LEGACY_LICENSE_NAMES,
    MAX_EXPRESSION,
    canonical_license_id,
)

MAX_INDEX_BYTES = 32 * 1024 * 1024
MAX_METADATA_BYTES = 1024 * 1024
MAX_SDIST_BYTES = 20 * 1024 * 1024
MAX_SDIST_UNPACKED = 160 * 1024 * 1024
MAX_SDIST_ENTRIES = 10000
MAX_ARTIFACTS = 160
SHA256 = re.compile(r"[0-9a-f]{64}")

SOURCE_LICENSE_FILES = frozenset(
    {"LICENSE", "LICENSE.txt", "LICENSE.md", "COPYING", "COPYING.txt"}
)
SOURCE_NOTICE_FILES = frozenset({"NOTICE", "NOTICE.txt", "NOTICE.md"})
# SHA-256 of the whitespace-normalized Apache License text, with and without
# the appendix. https://www.apache.org/licenses/LICENSE-2.0.txt
SOURCE_LICENSE_TEXTS = {
    "0ffddef9e48f8a09aed5caf2d44f7ba1c1be2d9b8e0a6f693b1635b2d5566645": "Apache-2.0",
    "59d8f0ba87ad9a2f1a431123c8d16646e5b89ba53653e818f16d136d77263c99": "Apache-2.0",
}

LICENSE_CLASSIFIERS = {
    "MIT License": {"MIT"},
    "BSD License": {"BSD-2-Clause", "BSD-3-Clause", "BSD-4-Clause"},
    "Apache Software License": {"Apache-2.0"},
    "Mozilla Public License 2.0 (MPL 2.0)": {"MPL-2.0"},
}


class _UnresolvedLicense(ValueError):
    """A known reason why an artifact's license could not be resolved."""


class _SourceLicenseFileRequired(_UnresolvedLicense):
    """PKG-INFO requires corroboration by a license file in the source archive."""


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


def _sdist_files(artifact):
    """Read root evidence files from bounded bytes without extracting archive paths."""
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
        return _read_source_files(unpacked)


def _read_source_files(unpacked):
    metadata = None
    license_members = []
    with tarfile.open(fileobj=unpacked, mode="r:") as archive:
        for index, member in enumerate(archive):
            if index >= MAX_SDIST_ENTRIES:
                raise ValueError("source archive has too many entries")
            parts = member.name.split("/")
            if len(parts) != 2 or parts[0] in ("", ".", ".."):
                continue
            if parts[1] == "PKG-INFO":
                if metadata is not None:
                    raise ValueError("ambiguous source metadata")
                metadata = member
            elif re.fullmatch(r"(LICENSE|COPYING)([._-].*)?", parts[1], re.IGNORECASE):
                license_members.append((parts[0], parts[1], member))
        if metadata is None:
            raise ValueError("source metadata unavailable")
        root = metadata.name.split("/", 1)[0]
        licenses = [
            (name, member) for parent, name, member in license_members if parent == root
        ]
        license_file = None
        if len(licenses) == 1:
            name, member = licenses[0]
            if (
                name in SOURCE_LICENSE_FILES
                and member.isfile()
                and member.size <= MAX_METADATA_BYTES
            ):
                license_file = (name, _read_source_member(archive, member))
        return _read_source_member(archive, metadata), license_file


def _read_source_member(archive, member):
    if not member.isfile() or member.size > MAX_METADATA_BYTES:
        raise ValueError("invalid source evidence file")
    stream = archive.extractfile(member)
    if stream is None:
        raise ValueError("source evidence file unavailable")
    with stream:
        return stream.read(MAX_METADATA_BYTES + 1)


def _metadata(content, name, version, *, wheel, license_file=None):
    message = BytesParser(policy=policy.compat32).parsebytes(content, headersonly=True)
    if message.defects:
        raise ValueError("invalid metadata")
    names = message.get_all("Name", [])
    versions = message.get_all("Version", [])
    normalized_name = (
        re.sub(r"[-_.]+", "-", str(names[0])).lower() if len(names) == 1 else None
    )
    if normalized_name != name or versions != [version]:
        raise ValueError("metadata package mismatch")
    metadata_version = re.fullmatch(
        r"(1|2)\.([0-9]{1,2})", str(message.get("Metadata-Version", ""))
    )
    if len(message.get_all("Metadata-Version", [])) != 1 or not metadata_version:
        raise ValueError("invalid metadata version")
    if not wheel:
        dynamic = {str(item).strip().lower() for item in message.get_all("Dynamic", [])}
        if tuple(map(int, metadata_version.groups())) < (2, 2):
            reason = "source metadata predates static license declarations"
        elif "license-expression" in dynamic or (
            "license" in dynamic and not message.get_all("License-Expression")
        ):
            reason = "dynamic license declaration"
        else:
            reason = None
        if reason:
            return _source_license_declaration(message, license_file, reason)
    return _declared_license(message)


def _source_license_declaration(message, license_file, reason):
    # Old or dynamic PKG-INFO cannot establish the license of a future wheel.
    # The license shipped in the archive can establish the archive's license.
    if license_file is None:
        raise _SourceLicenseFileRequired(reason)
    filename, content = license_file
    expression = SOURCE_LICENSE_TEXTS.get(
        hashlib.sha256(b" ".join(content.split())).hexdigest()
    )
    license_files = set(message.get_all("License-File", []))
    if not expression or license_files - {filename} - SOURCE_NOTICE_FILES:
        raise _UnresolvedLicense(reason)
    declaration = _declared_license(message)
    if declaration["licenseExpression"] != expression:
        raise _UnresolvedLicense("source license file conflicts with metadata")
    return {
        **declaration,
        "sourceKind": "source-archive-license-file",
        "licenseFile": filename,
        "licenseFileSha256": hashlib.sha256(content).hexdigest(),
    }


def _declared_license(message):
    expressions = message.get_all("License-Expression", [])
    if expressions:
        if (
            len(expressions) != 1
            or not 0 < len(str(expressions[0]).strip()) <= MAX_EXPRESSION
        ):
            raise _UnresolvedLicense("ambiguous license expression")
        return {
            "licenseExpression": str(expressions[0]).strip(),
            "licenseField": "License-Expression",
        }
    legacy = message.get_all("License", [])
    if len(legacy) != 1:
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


_METADATA_ERRORS = (
    ValueError,
    TypeError,
    AttributeError,
    KeyError,
    httpx.HTTPError,
    TimeoutError,
    OSError,
    EOFError,
    tarfile.TarError,
    zlib.error,
)
_ARTIFACT_UNAVAILABLE = "artifact license metadata unavailable or invalid"


def _read_artifact(package, item, digest, fetch):
    result = {"artifactSha256": digest, "status": "UNKNOWN"}
    if item is None:
        return {**result, "reason": "locked artifact missing in index"}
    try:
        url = _artifact_url(item.get("url"))
        filename = urlsplit(url).path.rsplit("/", 1)[-1]
        wheel = filename.endswith(".whl")
        source_archive = filename.endswith(".tar.gz")
        result.update(filename=filename, sourceUrl=url)
        metadata_hashes = item.get("core-metadata", item.get("dist-info-metadata"))
        metadata_hash = (
            metadata_hashes.get("sha256") if isinstance(metadata_hashes, dict) else None
        )
        if isinstance(metadata_hash, str) and SHA256.fullmatch(metadata_hash):
            metadata_url = url + ".metadata"
            data = fetch(metadata_url, accept="text/plain", limit=MAX_METADATA_BYTES)
            if hashlib.sha256(data).hexdigest() != metadata_hash:
                raise ValueError("metadata hash mismatch")
            try:
                declaration = _metadata(
                    data, package.name, package.version, wheel=wheel
                )
            except _SourceLicenseFileRequired:
                if not source_archive:
                    raise
            else:
                return {
                    **result,
                    **declaration,
                    "sourceUrl": metadata_url,
                    "metadataSha256": metadata_hash,
                    "sourceKind": "distribution-metadata",
                    "status": "OBSERVED",
                }
        if not source_archive:
            raise _UnresolvedLicense("verified distribution metadata unavailable")
        artifact = fetch(url, accept="application/octet-stream", limit=MAX_SDIST_BYTES)
        if hashlib.sha256(artifact).hexdigest() != digest:
            raise ValueError("source archive hash mismatch")
        data, license_file = _sdist_files(artifact)
        result.update(
            metadataSha256=hashlib.sha256(data).hexdigest(),
            sourceKind="source-archive-pkg-info",
        )
        declaration = _metadata(
            data, package.name, package.version, wheel=wheel, license_file=license_file
        )
        return {**result, **declaration, "status": "OBSERVED"}
    except _UnresolvedLicense as exc:
        return {**result, "reason": str(exc)}
    except _METADATA_ERRORS:
        return {**result, "reason": _ARTIFACT_UNAVAILABLE}


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
    except _METADATA_ERRORS:
        return {"status": "UNKNOWN", "reason": _ARTIFACT_UNAVAILABLE}
    artifacts = [
        _read_artifact(package, matches.get(digest), digest, fetch)
        for digest in sorted(hashes)
    ]
    unresolved = next((item for item in artifacts if item["status"] == "UNKNOWN"), None)
    if unresolved:
        return {
            "status": "UNKNOWN",
            "reason": unresolved["reason"],
            "artifacts": artifacts,
        }
    expressions = {item["licenseExpression"] for item in artifacts}
    return {
        "status": "OBSERVED",
        "expression": next(iter(expressions)) if len(expressions) == 1 else None,
        "artifacts": artifacts,
    }

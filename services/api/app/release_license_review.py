"""Check the customer distribution artifacts and record their license review."""

import argparse
import hashlib
import json
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

from app.license_policy import evaluate_license

MAX_JSON_BYTES = 64 * 1024 * 1024
ARTIFACTS = ("portal", "api-image", "worker-image")


def _json_bytes(path):
    with path.open("rb") as stream:
        document = stream.read(MAX_JSON_BYTES + 1)
    if len(document) > MAX_JSON_BYTES:
        raise ValueError(f"JSON exceeds size limit: {path.name}")
    return document


def _hash(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def browser_inventory(root):
    files = sorted(root.rglob("*"))
    if any(path.is_symlink() for path in files):
        raise ValueError("Portal build contains a symbolic link")
    digests = {
        path.relative_to(root).as_posix(): _hash(path)
        for path in files
        if path.is_file()
    }
    manifest = _json_bytes(root / "bundled-licenses.json")
    if digests.get("bundled-licenses.json") != hashlib.sha256(manifest).hexdigest():
        raise ValueError("Portal inventory changed during the scan")
    inventory = json.loads(manifest)
    chunks = inventory["chunks"]
    if not chunks or chunks != {
        path: digest
        for path, digest in digests.items()
        if path.endswith((".js", ".mjs"))
    }:
        raise ValueError("Portal JavaScript files do not match the build inventory")
    return hashlib.sha256(
        json.dumps(digests, sort_keys=True).encode()
    ).hexdigest(), inventory["dependencies"]


def image_inventory(path, syft):
    digest = _hash(path)
    with tarfile.open(path, "r:") as archive:
        members = [
            entry for entry in archive.getmembers() if entry.name == "manifest.json"
        ]
        if (
            len(members) != 1
            or not members[0].isfile()
            or members[0].size > 1024 * 1024
        ):
            raise ValueError("Expected a Docker image archive with one manifest")
        stream = archive.extractfile(members[0])
        if stream is None or len(json.load(stream)) != 1:
            raise ValueError("Expected exactly one image in the archive")
    with tempfile.TemporaryDirectory() as directory:
        output = Path(directory) / "image.json"
        subprocess.run(
            [
                syft,
                "scan",
                f"docker-archive:{path.resolve()}",
                "-o",
                f"spdx-json={output}",
            ],
            check=True,
            timeout=300,
        )
        packages = json.loads(_json_bytes(output))["packages"]
    if _hash(path) != digest:
        raise ValueError("Image archive changed during the scan")
    components = []
    for package in packages:
        if package.get("primaryPackagePurpose") == "CONTAINER":
            continue
        declared = package.get("licenseDeclared")
        concluded = package.get("licenseConcluded")
        candidates = {
            item
            for item in (declared, concluded)
            if item not in (None, "NONE", "NOASSERTION")
        }
        components.append(
            {
                "name": package["name"],
                "version": package.get("versionInfo"),
                "license": candidates.pop() if len(candidates) == 1 else None,
                "declaredLicense": declared,
                "concludedLicense": concluded,
                "id": package["SPDXID"],
            }
        )
    return digest, components


def review_artifact(name, digest, components, allowed, reviewed):
    """Only the approving release process may supply its digest-bound review."""
    record = reviewed.get(name, {})
    approved_artifact = record.get("sha256") == digest

    def reference(value):
        return isinstance(value, str) and bool(value.strip())

    coverage_verified = approved_artifact and reference(record.get("inventoryEvidence"))
    notices_verified = approved_artifact and reference(record.get("noticeEvidence"))
    decisions = []
    for component in components:
        status = evaluate_license(component["license"], allowed)
        key = component.get("id") or f"{component['name']}@{component['version']}"
        clearance = record.get("componentApprovals", {}).get(key)
        if status != "PASS" and approved_artifact and reference(clearance):
            status = "APPROVED"
        decisions.append(
            {
                **component,
                "status": status,
                **({"approvalEvidence": clearance} if status == "APPROVED" else {}),
            }
        )
    ready = bool(
        decisions
        and coverage_verified
        and notices_verified
        and all(item["status"] in ("PASS", "APPROVED") for item in decisions)
    )
    return {
        "sha256": digest,
        "inventoryReviewed": bool(coverage_verified),
        "noticesReviewed": bool(notices_verified),
        "ready": ready,
        "components": decisions,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--portal", type=Path, required=True)
    parser.add_argument(
        "--api-image", type=Path, required=True, help="Docker image archive"
    )
    parser.add_argument(
        "--worker-image", type=Path, required=True, help="Docker image archive"
    )
    parser.add_argument("--syft", default="syft")
    parser.add_argument(
        "--policy", type=Path, required=True, help="Approved release review input"
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        policy_bytes = _json_bytes(args.policy)
        policy = json.loads(policy_bytes)
        if policy["use"] != "customer-distribution" or not isinstance(
            policy["allowed"], list
        ):
            raise ValueError("An explicit customer-distribution policy is required")
        if not policy["allowed"] or any(
            not isinstance(item, str) for item in policy["allowed"]
        ):
            raise ValueError("A non-empty SPDX allowlist is required")
        reviewed = policy.get("reviewedArtifacts", {})
        if args.output.resolve().is_relative_to(
            args.portal.resolve()
        ) or args.output.resolve() in {
            item.resolve() for item in (args.policy, args.api_image, args.worker_image)
        }:
            raise ValueError("The report must be outside its inputs")
        inventory = (
            browser_inventory(args.portal),
            image_inventory(args.api_image, args.syft),
            image_inventory(args.worker_image, args.syft),
        )
        results = {
            name: review_artifact(name, digest, components, policy["allowed"], reviewed)
            for name, (digest, components) in zip(ARTIFACTS, inventory, strict=True)
        }
        source_license = policy.get("projectLicenseEvidence")
        source_license_reviewed = isinstance(source_license, str) and bool(
            source_license.strip()
        )
        ready = source_license_reviewed and all(
            item["ready"] for item in results.values()
        )
        args.output.write_text(
            json.dumps(
                {
                    "use": policy["use"],
                    "policySha256": hashlib.sha256(policy_bytes).hexdigest(),
                    "projectLicenseReviewed": source_license_reviewed,
                    "ready": ready,
                    "artifacts": results,
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        return 0 if ready else 1
    except (
        OSError,
        ValueError,
        KeyError,
        AttributeError,
        TypeError,
        tarfile.TarError,
        subprocess.SubprocessError,
    ) as exc:
        print(f"Release license review unavailable: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

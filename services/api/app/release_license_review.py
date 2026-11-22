"""Check the customer distribution artifacts and record their license review."""

import argparse
import hashlib
import json
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

from app.license_policy import LEGACY_LICENSE_NAMES, evaluate_license
from app.release_license_summary import markdown_summary

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
    return hashlib.sha256(json.dumps(digests, sort_keys=True).encode()).hexdigest(), [
        {**component, "ecosystem": "npm"} for component in inventory["dependencies"]
    ]


def _component(package, native):
    declared = package.get("licenseDeclared")
    concluded = package.get("licenseConcluded")
    declarations = {
        item
        for item in (declared, concluded)
        if item not in (None, "NONE", "NOASSERTION")
    }
    expression = next(iter(declarations)) if len(declarations) == 1 else None
    licenses = native.get("licenses", [])
    if native.get("type") == "python" and expression and len(licenses) == 1:
        license_entry = licenses[0]
        raw = license_entry.get("value") or ""
        # Compare Syft's SPDX export with the sole declaration in the image.
        if license_entry.get("type") == "declared" and expression == (
            "LicenseRef-" + raw.strip().replace(" ", "-")
        ):
            expression = LEGACY_LICENSE_NAMES.get(raw.strip().casefold(), expression)
    paths = {location["path"] for location in native.get("locations", [])}
    license_paths = {
        location["path"]
        for license_entry in licenses
        for location in license_entry.get("locations", [])
    }
    return {
        "name": package["name"],
        "version": package.get("versionInfo"),
        "license": expression,
        "declaredLicense": declared,
        "concludedLicense": concluded,
        "id": package["SPDXID"],
        "purl": native.get("purl"),
        "ecosystem": native.get("type"),
        "locations": sorted(paths),
        "licenseSources": sorted(license_paths),
    }


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
        native_output = Path(directory) / "syft.json"
        subprocess.run(
            [
                syft,
                "scan",
                f"docker-archive:{path.resolve()}",
                "--scope",
                "all-layers",
                "-o",
                f"spdx-json={output}",
                "-o",
                f"syft-json={native_output}",
            ],
            check=True,
            timeout=300,
        )
        packages = json.loads(_json_bytes(output))["packages"]
        native_artifacts = json.loads(_json_bytes(native_output))["artifacts"]
    native_by_id = {item["id"]: item for item in native_artifacts}
    if len(native_by_id) != len(native_artifacts):
        raise ValueError("Ambiguous Syft package identifiers")
    if _hash(path) != digest:
        raise ValueError("Image archive changed during the scan")
    components = []
    for package in packages:
        if package.get("primaryPackagePurpose") == "CONTAINER":
            continue
        # Syft's SPDX encoder places its artifact ID after the final hyphen.
        native = native_by_id.get(package["SPDXID"].rsplit("-", 1)[-1], {})
        if native.get("name") != package["name"] or native.get(
            "version"
        ) != package.get("versionInfo"):
            native = {}
        components.append(_component(package, native))
    return digest, components


def _decision_reason(component, status):
    if status == "APPROVED":
        return "approved"
    if status == "PASS":
        return "allowed"
    if status == "FAIL":
        return "outside-policy"
    if component["license"]:
        return "unresolved-expression"
    declarations = {
        component.get(key) for key in ("declaredLicense", "concludedLicense")
    } - {None, "NOASSERTION", "NONE"}
    return (
        "conflicting-declarations" if len(declarations) > 1 else "missing-declaration"
    )


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
                "reason": _decision_reason(component, status),
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
    parser.add_argument("--summary", type=Path, help="Optional Markdown review summary")
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
        outputs = [
            path.resolve() for path in (args.output, args.summary) if path is not None
        ]
        inputs = {
            item.resolve() for item in (args.policy, args.api_image, args.worker_image)
        }
        if len(set(outputs)) != len(outputs) or any(
            path.is_relative_to(args.portal.resolve()) or path in inputs
            for path in outputs
        ):
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
        report = {
            "use": policy["use"],
            "policySha256": hashlib.sha256(policy_bytes).hexdigest(),
            "projectLicenseReviewed": source_license_reviewed,
            "ready": ready,
            "artifacts": results,
        }
        args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        if args.summary is not None:
            args.summary.write_text(markdown_summary(report), encoding="utf-8")
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

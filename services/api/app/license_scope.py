"""Match authorized license decisions to a frozen use, policy and locked artifacts."""

import hashlib
import json

from sqlalchemy import or_, select

from app.pypi_license_metadata import MAX_ARTIFACTS, SHA256
from app.tables import license_approvals, product_governance


def license_use(context):
    if context and context.get("mode") == "profile":
        return context["product"]["resolved"].get("licenseUse")
    return None


def approval_rule(control):
    rules = control.get("assertions", [])
    if (
        control.get("target", {}).get("kind") == "python.package"
        and control.get("requiredEvidence", {}).get("capability")
        == "python.package-license/v1"
        and len(rules) == 1
        and rules[0].get("operator") == "spdx-allowlist"
        and rules[0].get("path") == "licenseExpression"
        and rules[0].get("allowApprovedUse") is True
    ):
        return rules[0]
    return None


def locked_artifact_digest(package):
    hashes = package.get("artifactHashes")
    if (
        not isinstance(hashes, list)
        or not 0 < len(hashes) <= MAX_ARTIFACTS
        or any(
            not isinstance(item, str) or not SHA256.fullmatch(item) for item in hashes
        )
    ):
        return None
    return hashlib.sha256(json.dumps(sorted(set(hashes))).encode()).hexdigest()


def approval_scope(context, binding_id, subject, control):
    use = license_use(context)
    digest = subject.get("licenseArtifactDigest")
    if not use or not digest or not approval_rule(control):
        return None
    product, profile = context["product"], context["profile"]
    return {
        "organization_id": product["organizationId"],
        "product_id": context["productId"],
        "binding_id": binding_id,
        "subject_id": subject["id"],
        "artifact_digest": digest,
        "control_id": control["id"],
        "policy_digest": profile["contentDigest"],
        "license_use": use,
    }


def live_approvals(scope, now):
    return (
        select(license_approvals)
        .filter_by(**scope)
        .where(
            license_approvals.c.created_at <= now,
            license_approvals.c.revoked_at.is_(None),
            or_(
                license_approvals.c.expires_at.is_(None),
                license_approvals.c.expires_at > now,
            ),
        )
    )


def current_license_configuration(db, context):
    product = context["product"]
    return (
        db.execute(
            select(product_governance.c.revision_id).where(
                product_governance.c.product_id == context["productId"],
                product_governance.c.organization_id == product["organizationId"],
                product_governance.c.revision_id == product["id"],
            )
        ).first()
        is not None
    )


def license_decision(row):
    return {
        "id": row["id"],
        "use": row["license_use"],
        "kind": row["kind"],
        "reason": row["reason"],
        "conditions": row["conditions"],
        "expiresAt": row["expires_at"].isoformat() if row["expires_at"] else None,
    }

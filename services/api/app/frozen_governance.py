"""One execution context owns source closure, selected controls and honest coverage."""

import copy

from sqlalchemy import select

from app.example_license_pack import load_example_license_pack
from app.resource_store import resources_query, serialize_resource
from app.tables import product_governance, resource_documents

CAPABILITY = "python.package-license/v1"


def freeze_product_governance(db, organization_id, product_id):
    current = (
        db.execute(
            select(product_governance).where(
                product_governance.c.organization_id == organization_id,
                product_governance.c.product_id == product_id,
            )
        )
        .mappings()
        .one_or_none()
    )
    producer = {
        "kind": "public-license-scan",
        "capability": CAPABILITY,
        "version": None,
    }
    if current is None:
        policy = load_example_license_pack()
        return {
            "mode": "legacy-example",
            "productId": product_id,
            "producer": producer,
            "policy": policy,
        }

    def resource(revision_id):
        return serialize_resource(
            db.execute(
                resources_query(organization_id).where(
                    resource_documents.c.revision_id == revision_id
                )
            )
            .mappings()
            .one()
        )

    product = resource(current["revision_id"])
    profile = resource(current["profile_revision_id"])
    catalog = resource(profile["resolved"]["catalog"]["revisionId"])
    return {
        "mode": "profile",
        "productId": product_id,
        "producer": producer,
        "product": product,
        "profile": profile,
        "catalog": catalog,
    }


def execution_policy(context):
    """NULL is historical, not a reason to look up today's product profile."""
    if context is None:
        return load_example_license_pack()
    if context["mode"] == "legacy-example":
        return copy.deepcopy(context["policy"])
    if context["mode"] != "profile":
        raise ValueError("Unknown frozen governance context")
    return {
        "revision": context["profile"]["source"]["commit"],
        "controls": [
            copy.deepcopy(control["binding"])
            for control in context["profile"]["resolved"]["controls"]
            if executable_by_public_scanner(control.get("binding"))
        ],
    }


def executable_by_public_scanner(binding):
    return bool(
        binding
        and binding["target"]["kind"] == "python.package"
        and binding["requiredEvidence"]["capability"] == CAPABILITY
    )


def selected_controls(context):
    if context["mode"] == "profile":
        return context["profile"]["resolved"]["controls"]
    return [
        {"id": binding["id"], "title": binding["id"], "binding": binding}
        for binding in context["policy"]["controls"]
    ]


def summarize_controls(context, evaluations, *, organization_id, product_id, pack_sha):
    if context is None:
        return None
    if context["productId"] != product_id:
        raise ValueError("Frozen governance belongs to another product")
    if context["mode"] == "profile":
        product, profile, catalog = (
            context[key] for key in ("product", "profile", "catalog")
        )
        if (
            any(
                resource["organizationId"] != organization_id
                for resource in (product, profile, catalog)
            )
            or product["resolved"]["productId"] != product_id
            or product["resolved"]["profile"]["revisionId"] != profile["id"]
            or product["resolved"]["profile"]["contentDigest"]
            != profile["contentDigest"]
            or profile["source"]["commit"] != pack_sha
            or profile["resolved"]["catalog"]["revisionId"] != catalog["id"]
            or profile["resolved"]["catalog"]["contentDigest"]
            != catalog["contentDigest"]
        ):
            raise ValueError(
                "Frozen governance source closure does not match assessment"
            )
    elif (
        context["mode"] != "legacy-example" or context["policy"]["revision"] != pack_sha
    ):
        raise ValueError("Invalid frozen legacy governance")
    controls = selected_controls(context)
    by_id = {control["id"]: control for control in controls}
    if len(by_id) != len(controls) or not controls:
        raise ValueError("Frozen control selection is empty or ambiguous")
    for evaluation in evaluations:
        control = by_id.get(evaluation["control_id"])
        if control is None or control.get("binding") != evaluation["control"]:
            raise ValueError("Evaluation differs from frozen control binding")
    result = []
    for control in controls:
        rows = [row for row in evaluations if row["control_id"] == control["id"]]
        counts = {
            status: sum(row["status"] == status for row in rows)
            for status in ("PASS", "FAIL", "UNKNOWN", "NOT_APPLICABLE")
        }
        status = (
            "FAIL"
            if counts["FAIL"]
            else "UNKNOWN"
            if counts["UNKNOWN"] or not rows
            else "PASS"
            if counts["PASS"]
            else "NOT_APPLICABLE"
        )
        binding = control.get("binding")
        execution = (
            "evaluated"
            if rows
            else "unsupported"
            if binding and not executable_by_public_scanner(binding)
            else "not_evaluated"
        )
        reason = (
            "individual-evaluations"
            if rows
            else "method-not-configured"
            if not binding
            else "scanner-does-not-support-binding"
            if execution == "unsupported"
            else "no-evaluable-observations"
        )
        result.append(
            {
                "controlId": control["id"],
                "title": control["title"],
                "status": status,
                "executionStatus": execution,
                "reason": reason,
                "evaluationIds": [row["id"] for row in rows],
                "evidenceIds": sorted(
                    {evidence_id for row in rows for evidence_id in row["evidence_ids"]}
                ),
                "counts": counts,
            }
        )
    return result

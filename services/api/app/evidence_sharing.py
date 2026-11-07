"""Persist one collector observation once and reuse it across control evaluations."""

from sqlalchemy.engine import Connection

from app.evidence_records import store_evidence
from app.manifest_io import validate
from app.rule_evaluation import evaluate_and_store


def store_and_evaluate(
    db: Connection,
    organization_id,
    provider,
    request,
    response,
    controls,
    governance_revision,
    *,
    ttl_seconds,
    now,
    scan_id,
    binding_id,
    ref,
):
    """Atomically store one response and evaluate controls for the same capability."""
    if (
        not isinstance(request, dict)
        or not isinstance(request.get("capabilities"), list)
        or len(request["capabilities"]) != 1
    ):
        raise ValueError("Exactly one requested capability is required")
    if (
        not isinstance(response, dict)
        or not isinstance(response.get("observations"), list)
        or len(response["observations"]) != 1
    ):
        raise ValueError("Exactly one collector observation is required")
    if not isinstance(controls, list) or not 0 < len(controls) <= 64:
        raise ValueError("A bounded list of controls is required")
    capability = request["capabilities"][0]
    seen = set()
    for control in controls:
        validate(control, "governance-control.schema.json", "control")
        if (
            control["requiredEvidence"]["capability"] != capability
            or control["id"] in seen
        ):
            raise ValueError(
                "Controls must be distinct and use the requested capability"
            )
        seen.add(control["id"])
    with db.begin_nested():
        records = store_evidence(
            db,
            organization_id,
            provider,
            request,
            response,
            ttl_seconds=ttl_seconds,
            now=now,
        )
        evaluations = [
            evaluate_and_store(
                db,
                organization_id,
                request["scope"],
                request["subject"],
                control,
                governance_revision,
                now=now,
                scan_id=scan_id,
                binding_id=binding_id,
                ref=ref,
            )
            for control in controls
        ]
    return {"evidence": records[0], "evaluations": evaluations}

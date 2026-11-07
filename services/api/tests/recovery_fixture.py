"""Seed and verify isolated Compose recovery fixtures; never use with live data."""

import json
import os
import sys
from pathlib import Path

from app.audit import record_agent_event
from app.database import get_engine
from app.s3_blobstore import configured_blobstore
from app.snapshots import create_snapshot, get_snapshot
from app.tables import audit_events
from sqlalchemy import select

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_rule_evaluation import COMMIT, NOW, RuleEvaluationTest  # noqa: E402


def seed():
    fixture = RuleEvaluationTest(methodName="runTest")
    fixture.setUp()
    fixture.save_evidence()
    evaluation = fixture.evaluate()
    with get_engine().begin() as db:
        snapshot = create_snapshot(
            db,
            fixture.org,
            fixture.product,
            context="baseline",
            binding_id=fixture.binding,
            pull_request_number=None,
            environment="test",
            git_sha=COMMIT,
            pack_sha="a" * 40,
            evaluation_ids=[evaluation["id"]],
            now=NOW,
        )
        record_agent_event(
            db,
            organization_id=fixture.org,
            actor_id="user:recovery-fixture",
            action="fixture.created",
            target_id=snapshot["id"],
        )
        audit_id = db.execute(
            select(audit_events.c.id).where(
                audit_events.c.organization_id == fixture.org,
                audit_events.c.target_id == snapshot["id"],
            )
        ).scalar_one()
    result = {
        "organizationId": fixture.org,
        "snapshotId": snapshot["id"],
        "auditId": audit_id,
        "objectKey": "recovery/" + snapshot["id"],
    }
    configured_blobstore().put(
        result["objectKey"], json.dumps(result, sort_keys=True).encode()
    )
    print(json.dumps(result, sort_keys=True))


def verify():
    expected = json.load(sys.stdin)
    with get_engine().connect() as db:
        snapshot = get_snapshot(db, expected["organizationId"], expected["snapshotId"])
        audit = db.execute(
            select(audit_events.c.id).where(
                audit_events.c.id == expected["auditId"],
                audit_events.c.organization_id == expected["organizationId"],
                audit_events.c.target_id == expected["snapshotId"],
            )
        ).scalar_one_or_none()
    if (
        snapshot is None
        or snapshot["counts"]["PASS"] != 1
        or audit != expected["auditId"]
    ):
        raise RuntimeError("Restored database fixture does not match")
    stored = json.loads(configured_blobstore().get(expected["objectKey"]))
    if stored != expected:
        raise RuntimeError("Restored object fixture does not match")
    print("Assessment, audit ID and object restored.")


def main():
    if (
        os.environ.get("SPECBOUND_RECOVERY_FIXTURE") != "1"
        or len(sys.argv) != 2
        or sys.argv[1] not in ("seed", "verify")
    ):
        raise SystemExit("Explicit isolated recovery fixture configuration is required")
    seed() if sys.argv[1] == "seed" else verify()


if __name__ == "__main__":
    main()

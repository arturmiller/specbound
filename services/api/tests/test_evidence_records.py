"""Evidence persistence and freshness in a disposable migrated database."""

import copy
import json
import os
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

from app.assessment import Applicability, AssessmentStatus, RuleOutcome
from app.database import get_engine
from app.evidence_records import assess_with_evidence, current_evidence, store_evidence
from app.git_source import GitSnapshot
from app.provider_pack import load_provider_pack
from app.tables import evidence_records, organizations, products, teams
from sqlalchemy import insert, select

NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)
CAPABILITY = "net.internet-reachability/v1"
FIXTURES = Path(__file__).parent / "fixtures" / "provider"


def provider_fixture():
    generic = (FIXTURES / "schema.json").read_bytes()
    value_schema = json.dumps(
        {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "type": "object",
            "properties": {"publicly_reachable": {"type": "boolean"}},
            "required": ["publicly_reachable"],
            "additionalProperties": False,
        }
    ).encode()
    return load_provider_pack(
        GitSnapshot(
            "a" * 40,
            {
                "provider.yaml": (FIXTURES / "provider.yaml").read_bytes(),
                "contracts/collect-request.json": generic,
                "contracts/observation.json": generic,
                "schemas/reachability.json": value_schema,
                "tests/reachability.yaml": b"name: fixture\n",
            },
        )
    )


class EvidenceRecordsTest(unittest.TestCase):
    def setUp(self):
        if not os.environ.get("DATABASE_URL"):
            self.fail("DATABASE_URL must point to a disposable migrated database")
        self.org, self.team, self.product, self.other_org = (
            str(uuid4()) for _ in range(4)
        )
        with get_engine().begin() as db:
            db.execute(
                insert(organizations),
                [
                    {"id": self.org, "name": "One", "owner_principal_id": "owner"},
                    {
                        "id": self.other_org,
                        "name": "Other",
                        "owner_principal_id": "other",
                    },
                ],
            )
            db.execute(
                insert(teams).values(
                    id=self.team, organization_id=self.org, name="Team"
                )
            )
            db.execute(
                insert(products).values(
                    id=self.product, owner_team_id=self.team, name="Product"
                )
            )
        self.provider = provider_fixture()
        self.scope = {
            "productId": self.product,
            "environment": "test",
            "targetRevision": "b" * 40,
        }
        self.request = {
            "schemaVersion": 1,
            "scope": self.scope,
            "credentialsRef": None,
            "capabilities": [CAPABILITY],
            "subject": {
                "schemaVersion": 1,
                "id": "db-1",
                "type": "database",
                "scope": self.scope,
                "provenance": {"sourceRef": "repo:fixture"},
                "observedAt": NOW.isoformat(),
            },
        }
        self.response = {
            "schemaVersion": 1,
            "observations": [
                {
                    "subjectId": "db-1",
                    "capability": CAPABILITY,
                    "scope": self.scope,
                    "observedAt": NOW.isoformat(),
                    "provenance": {"sourceRef": "collector:fixture"},
                    "value": {"publicly_reachable": False},
                }
            ],
        }

    def save(self, *, org=None, response=None, ttl=60, now=NOW):
        with get_engine().begin() as db:
            return store_evidence(
                db,
                org or self.org,
                self.provider,
                self.request,
                response or self.response,
                ttl_seconds=ttl,
                now=now,
            )

    def lookup(self, *, org=None, scope=None, subject="db-1", now=NOW):
        with get_engine().begin() as db:
            return current_evidence(
                db, org or self.org, scope or self.scope, subject, CAPABILITY, now=now
            )

    def assess(self, evidence_ids, now):
        with get_engine().begin() as db:
            return assess_with_evidence(
                db,
                self.org,
                self.scope,
                "db-1",
                CAPABILITY,
                evidence_ids=evidence_ids,
                now=now,
                applicability=Applicability.APPLICABLE,
                outcome=RuleOutcome.PASS,
                outcome_reason="Matches expected value",
            )

    def test_expired_record_is_preserved_but_cannot_produce_pass(self):
        row = self.save()[0]
        self.assertEqual(row["collectorRevision"], "a" * 40)
        self.assertEqual(row["targetRevision"], "b" * 40)
        self.assertEqual(row["provenance"]["sourceRef"], "collector:fixture")
        self.assertEqual(row["value"], {"publicly_reachable": False})
        self.assertEqual(
            [item["id"] for item in self.lookup(now=NOW + timedelta(seconds=59))],
            [row["id"]],
        )
        self.assertEqual(
            self.assess((row["id"],), NOW + timedelta(seconds=59)).status,
            AssessmentStatus.PASS,
        )
        self.assertEqual(self.lookup(now=NOW + timedelta(seconds=60)), [])
        with get_engine().begin() as db:
            self.assertIsNotNone(
                db.execute(
                    select(evidence_records.c.id).where(
                        evidence_records.c.id == row["id"]
                    )
                ).first()
            )
        result = self.assess((row["id"],), NOW + timedelta(seconds=60))
        self.assertEqual(result.status, AssessmentStatus.UNKNOWN)
        self.assertEqual(result.evidence_ids, ())

    def test_scope_and_tenant_are_never_crossed(self):
        self.save()
        self.assertEqual(self.lookup(org=self.other_org), [])
        self.assertEqual(self.lookup(subject="other"), [])
        self.assertEqual(
            self.lookup(scope={**self.scope, "targetRevision": "c" * 40}), []
        )
        self.assertEqual(self.lookup(scope={**self.scope, "environment": "prod"}), [])
        with self.assertRaises(LookupError):
            self.save(org=self.other_org)

    def test_invalid_ttl_future_observation_and_invalid_response_are_rejected(self):
        for ttl in (0, -1, True):
            with self.subTest(ttl=ttl), self.assertRaises(ValueError):
                self.save(ttl=ttl)
        future = copy.deepcopy(self.response)
        future["observations"][0]["observedAt"] = (
            NOW + timedelta(seconds=1)
        ).isoformat()
        with self.assertRaises(ValueError):
            self.save(response=future)
        invalid = copy.deepcopy(self.response)
        invalid["observations"][0]["value"]["publicly_reachable"] = "no"
        with self.assertRaises(ValueError):
            self.save(response=invalid)
        self.assertEqual(self.lookup(), [])


if __name__ == "__main__":
    unittest.main()

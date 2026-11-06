"""Agent lifecycle through the public API against a disposable database."""

import os
import unittest
from collections import Counter

from app.identity import get_current_principal
from app.main import app
from fastapi.testclient import TestClient


class AgentIntegrationTest(unittest.TestCase):
    def setUp(self):
        if not os.environ.get("DATABASE_URL"):
            self.fail("DATABASE_URL must point to a disposable migrated database")
        app.dependency_overrides[get_current_principal] = lambda: "user:owner"
        self.client = TestClient(app)
        organization = self.client.post("/organizations", json={"name": "Agent test"})
        self.assertEqual(organization.status_code, 201, organization.text)
        self.org_id = organization.json()["id"]
        self.team_ids = []
        for name in ("Platform", "Billing"):
            team = self.client.post(
                f"/organizations/{self.org_id}/teams", json={"name": name}
            )
            self.assertEqual(team.status_code, 201, team.text)
            self.team_ids.append(team.json()["id"])

    def tearDown(self):
        self.client.close()
        app.dependency_overrides.clear()

    def test_agent_can_join_two_teams_and_all_changes_are_audited(self):
        created = self.client.post(
            f"/organizations/{self.org_id}/agents", json={"name": "Review bot"}
        )
        self.assertEqual(created.status_code, 201, created.text)
        agent_id = created.json()["id"]
        self.assertEqual(created.json()["kind"], "agent")
        self.assertIn(
            agent_id,
            [
                agent["id"]
                for agent in self.client.get(
                    f"/organizations/{self.org_id}/agents"
                ).json()
            ],
        )
        self.assertEqual(
            self.client.get(f"/organizations/{self.org_id}/agents/{agent_id}").json()[
                "name"
            ],
            "Review bot",
        )
        renamed = self.client.patch(
            f"/organizations/{self.org_id}/agents/{agent_id}",
            json={"name": "Review bot 2"},
        )
        self.assertEqual(renamed.status_code, 200)
        self.assertEqual(renamed.json()["name"], "Review bot 2")
        for team_id in self.team_ids:
            response = self.client.post(
                f"/teams/{team_id}/members",
                json={"principalId": agent_id, "role": "viewer"},
            )
            self.assertEqual(response.status_code, 201, response.text)
            listed = self.client.get(f"/teams/{team_id}/members")
            self.assertIn(agent_id, [member["principalId"] for member in listed.json()])
        events = self.client.get(f"/organizations/{self.org_id}/audit-events")
        self.assertEqual(events.status_code, 200)
        relevant = [event for event in events.json() if event["targetId"] == agent_id]
        self.assertEqual(
            Counter(event["action"] for event in relevant),
            Counter(
                {"agent.created": 1, "agent.updated": 1, "agent.membership.created": 2}
            ),
        )

        self.assertTrue(all(event["actorId"] == "user:owner" for event in relevant))
        self.assertEqual(
            self.client.delete(
                f"/organizations/{self.org_id}/agents/{agent_id}"
            ).status_code,
            204,
        )
        self.assertEqual(
            self.client.get(
                f"/organizations/{self.org_id}/agents/{agent_id}"
            ).status_code,
            404,
        )
        for team_id in self.team_ids:
            self.assertNotIn(
                agent_id,
                [
                    member["principalId"]
                    for member in self.client.get(f"/teams/{team_id}/members").json()
                ],
            )
        events = self.client.get(f"/organizations/{self.org_id}/audit-events").json()
        relevant = [event for event in events if event["targetId"] == agent_id]
        self.assertEqual(
            Counter(event["action"] for event in relevant),
            Counter(
                {
                    "agent.created": 1,
                    "agent.updated": 1,
                    "agent.membership.created": 2,
                    "agent.membership.deleted": 2,
                    "agent.deleted": 1,
                }
            ),
        )

    def test_agent_scope_roles_and_deletion_are_guarded(self):
        agent_id = self.client.post(
            f"/organizations/{self.org_id}/agents", json={"name": "Reader"}
        ).json()["id"]
        team_id = self.team_ids[0]
        self.assertEqual(
            self.client.post(
                f"/teams/{team_id}/members",
                json={"principalId": agent_id, "role": "admin"},
            ).status_code,
            403,
        )
        self.assertEqual(
            self.client.post(
                f"/teams/{team_id}/members",
                json={"principalId": "agent:missing", "role": "viewer"},
            ).status_code,
            404,
        )
        member = self.client.post(
            f"/teams/{team_id}/members",
            json={"principalId": agent_id, "role": "viewer"},
        )
        self.assertEqual(member.status_code, 201)
        member_id = member.json()["id"]
        self.assertEqual(
            self.client.post(
                f"/teams/{team_id}/members",
                json={"principalId": agent_id, "role": "viewer"},
            ).status_code,
            409,
        )
        self.assertEqual(
            self.client.patch(
                f"/teams/{team_id}/members/{member_id}", json={"role": "maintainer"}
            ).status_code,
            403,
        )
        self.assertEqual(
            self.client.patch(
                f"/teams/{team_id}/members/{member_id}", json={"role": "viewer"}
            ).status_code,
            200,
        )
        self.assertEqual(self.client.delete(f"/teams/{team_id}").status_code, 409)
        self.assertEqual(
            self.client.delete(f"/organizations/{self.org_id}").status_code, 409
        )
        other_org = self.client.post(
            "/organizations", json={"name": "Other org"}
        ).json()["id"]
        other_team = self.client.post(
            f"/organizations/{other_org}/teams", json={"name": "Other"}
        ).json()["id"]
        self.assertEqual(
            self.client.post(
                f"/teams/{other_team}/members",
                json={"principalId": agent_id, "role": "viewer"},
            ).status_code,
            404,
        )
        app.dependency_overrides[get_current_principal] = lambda: "user:outsider"
        self.assertEqual(
            self.client.get(f"/organizations/{self.org_id}/agents").status_code, 403
        )
        self.assertEqual(
            self.client.get(f"/organizations/{self.org_id}/audit-events").status_code,
            403,
        )
        app.dependency_overrides[get_current_principal] = lambda: "user:owner"
        self.assertEqual(
            self.client.delete(f"/teams/{team_id}/members/{member_id}").status_code, 204
        )
        events = self.client.get(f"/organizations/{self.org_id}/audit-events").json()
        relevant = [
            event["action"] for event in events if event["targetId"] == agent_id
        ]
        self.assertEqual(
            Counter(relevant),
            Counter(
                {
                    "agent.created": 1,
                    "agent.membership.created": 1,
                    "agent.membership.updated": 1,
                    "agent.membership.deleted": 1,
                }
            ),
        )


if __name__ == "__main__":
    unittest.main()

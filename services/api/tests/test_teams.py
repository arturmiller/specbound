"""Exercise real HTTP handlers with a disposable PostgreSQL database."""

import os
import unittest
from uuid import uuid4

from app.identity import get_current_principal
from app.main import app
from fastapi.testclient import TestClient


class TeamIntegrationTest(unittest.TestCase):
    def setUp(self):
        if not os.environ.get("DATABASE_URL"):
            self.fail(
                "DATABASE_URL must point to a disposable migrated PostgreSQL database"
            )
        app.dependency_overrides[get_current_principal] = lambda: "user:test-admin"

    def tearDown(self):
        app.dependency_overrides.clear()

    def test_create_team_and_membership_persists_across_clients(self):
        suffix = uuid4().hex
        with TestClient(app) as client:
            organization = client.post("/organizations", json={"name": f"Org {suffix}"})
            self.assertEqual(organization.status_code, 201, organization.text)
            self.assertEqual(organization.json()["ownerPrincipalId"], "user:test-admin")
            organization_id = organization.json()["id"]
            team = client.post(
                f"/organizations/{organization_id}/teams", json={"name": "Platform"}
            )
            self.assertEqual(team.status_code, 201, team.text)
            team_id = team.json()["id"]
            member = client.post(
                f"/teams/{team_id}/members",
                json={"principalId": "user:alice", "role": "admin"},
            )
            self.assertEqual(member.status_code, 201, member.text)
        with TestClient(app) as client:
            teams = client.get(f"/organizations/{organization_id}/teams")
            self.assertEqual(teams.status_code, 200)
            self.assertEqual([item["id"] for item in teams.json()], [team_id])
            members = client.get(f"/teams/{team_id}/members")
            self.assertEqual(members.status_code, 200)
            self.assertEqual(
                [(m["principalId"], m["role"]) for m in members.json()],
                [("user:alice", "admin")],
            )

    def test_no_identity_is_rejected_without_reading_database(self):
        app.dependency_overrides.clear()
        with TestClient(app) as client:
            self.assertEqual(client.get("/organizations").status_code, 401)
            self.assertEqual(
                client.post("/organizations", json={"name": "example"}).status_code, 401
            )
            self.assertEqual(
                client.get(
                    "/organizations", headers={"X-Principal-Id": "user:admin"}
                ).status_code,
                401,
            )
            self.assertEqual(
                client.get(
                    "/organizations", headers={"Authorization": "Bearer fake"}
                ).status_code,
                401,
            )

    def test_crud_validation_and_duplicate_membership(self):
        with TestClient(app) as client:
            self.assertEqual(
                client.post("/organizations", json={"name": "  "}).status_code, 422
            )
            self.assertEqual(
                client.post(
                    "/organizations/missing/teams", json={"name": "test"}
                ).status_code,
                404,
            )
            org = client.post("/organizations", json={"name": "Original"}).json()
            org_id = org["id"]
            self.assertEqual(
                client.patch(
                    f"/organizations/{org_id}", json={"name": "Renamed"}
                ).json()["name"],
                "Renamed",
            )
            self.assertEqual(
                client.get(f"/organizations/{org_id}").json()["name"], "Renamed"
            )
            team = client.post(
                f"/organizations/{org_id}/teams", json={"name": "Platform"}
            ).json()
            team_id = team["id"]
            self.assertEqual(team["organizationId"], org_id)
            self.assertEqual(
                client.patch(f"/teams/{team_id}", json={"name": "Security"}).json()[
                    "name"
                ],
                "Security",
            )
            self.assertEqual(client.get(f"/teams/{team_id}").json()["name"], "Security")
            self.assertEqual(
                client.post(
                    f"/teams/{team_id}/members",
                    json={"principalId": "user:alice", "role": "owner"},
                ).status_code,
                422,
            )
            member = client.post(
                f"/teams/{team_id}/members",
                json={"principalId": "user:alice", "role": "viewer"},
            ).json()
            member_id = member["id"]
            self.assertEqual(
                client.post(
                    f"/teams/{team_id}/members",
                    json={"principalId": "user:alice", "role": "admin"},
                ).status_code,
                409,
            )
            self.assertEqual(
                client.get(f"/teams/not-this-team/members/{member_id}").status_code, 404
            )
            self.assertEqual(
                client.patch(
                    f"/teams/{team_id}/members/{member_id}", json={"role": "admin"}
                ).json()["role"],
                "admin",
            )
            self.assertEqual(
                client.get(f"/teams/{team_id}/members/{member_id}").json()["role"],
                "admin",
            )
            self.assertEqual(
                client.delete(f"/teams/{team_id}/members/{member_id}").status_code, 204
            )
            self.assertEqual(
                client.get(f"/teams/{team_id}/members/{member_id}").status_code, 404
            )
            self.assertEqual(client.delete(f"/teams/{team_id}").status_code, 204)
            self.assertEqual(client.get(f"/teams/{team_id}").status_code, 404)
            self.assertEqual(client.delete(f"/organizations/{org_id}").status_code, 204)
            self.assertEqual(client.get(f"/organizations/{org_id}").status_code, 404)

    def test_deleting_organization_cascades_to_teams_and_members(self):
        if not os.environ["DATABASE_URL"].startswith("postgresql"):
            self.skipTest("PostgreSQL foreign-key behavior")
        with TestClient(app) as client:
            org_id = client.post("/organizations", json={"name": "Cascade"}).json()[
                "id"
            ]
            team_id = client.post(
                f"/organizations/{org_id}/teams", json={"name": "Platform"}
            ).json()["id"]
            member_id = client.post(
                f"/teams/{team_id}/members",
                json={"principalId": "user:alice", "role": "viewer"},
            ).json()["id"]
            self.assertEqual(client.delete(f"/organizations/{org_id}").status_code, 204)
            self.assertEqual(client.get(f"/teams/{team_id}").status_code, 404)
            self.assertEqual(
                client.get(f"/teams/{team_id}/members/{member_id}").status_code, 404
            )


if __name__ == "__main__":
    unittest.main()

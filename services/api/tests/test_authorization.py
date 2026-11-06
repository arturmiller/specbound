"""Test team authorization at the HTTP boundary with persisted memberships."""

import os
import unittest

from app.identity import get_current_principal
from app.main import app
from fastapi.testclient import TestClient


class TeamAuthorizationTest(unittest.TestCase):
    def setUp(self):
        if not os.environ.get("DATABASE_URL"):
            self.fail("DATABASE_URL must point to a disposable migrated database")
        self.as_principal("user:owner")
        self.client = TestClient(app)
        organization = self.client.post("/organizations", json={"name": "Auth test"})
        self.assertEqual(organization.status_code, 201, organization.text)
        self.org_id = organization.json()["id"]
        team = self.client.post(
            f"/organizations/{self.org_id}/teams", json={"name": "Platform"}
        )
        self.assertEqual(team.status_code, 201, team.text)
        self.team_id = team.json()["id"]
        for role in ("viewer", "maintainer", "admin"):
            member = self.client.post(
                f"/teams/{self.team_id}/members",
                json={"principalId": f"user:{role}", "role": role},
            )
            self.assertEqual(member.status_code, 201, member.text)

    def tearDown(self):
        self.client.close()
        app.dependency_overrides.clear()

    @staticmethod
    def as_principal(principal):
        app.dependency_overrides[get_current_principal] = lambda: principal

    def test_viewer_cannot_change_team_but_admin_can(self):
        self.as_principal("user:viewer")
        self.assertEqual(self.client.get(f"/teams/{self.team_id}").status_code, 200)
        self.assertEqual(
            self.client.patch(
                f"/teams/{self.team_id}", json={"name": "Changed"}
            ).status_code,
            403,
        )
        self.as_principal("user:admin")
        response = self.client.patch(f"/teams/{self.team_id}", json={"name": "Changed"})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["name"], "Changed")

    def test_maintainer_can_update_team_but_cannot_manage_members(self):
        self.as_principal("user:maintainer")
        self.assertEqual(
            self.client.patch(
                f"/teams/{self.team_id}", json={"name": "Edited"}
            ).status_code,
            200,
        )
        response = self.client.post(
            f"/teams/{self.team_id}/members",
            json={"principalId": "user:new", "role": "viewer"},
        )
        self.assertEqual(response.status_code, 403)

    def test_nonmembers_and_other_teams_are_not_exposed(self):
        self.as_principal("user:outsider")
        self.assertEqual(self.client.get(f"/teams/{self.team_id}").status_code, 403)
        self.assertEqual(
            self.client.get(f"/organizations/{self.org_id}").status_code, 403
        )
        self.assertNotIn(
            self.org_id,
            [entry["id"] for entry in self.client.get("/organizations").json()],
        )

    def test_members_cannot_change_organization_or_create_teams(self):
        self.as_principal("user:admin")
        self.assertEqual(
            self.client.patch(
                f"/organizations/{self.org_id}", json={"name": "Other"}
            ).status_code,
            403,
        )
        self.assertEqual(
            self.client.post(
                f"/organizations/{self.org_id}/teams", json={"name": "Other"}
            ).status_code,
            403,
        )

    def test_team_membership_does_not_grant_access_to_other_teams(self):
        other = self.client.post(
            f"/organizations/{self.org_id}/teams", json={"name": "Other"}
        )
        self.assertEqual(other.status_code, 201)
        other_team_id = other.json()["id"]
        self.as_principal("user:admin")
        visible = self.client.get(f"/organizations/{self.org_id}/teams")
        self.assertEqual(visible.status_code, 200)
        self.assertEqual([team["id"] for team in visible.json()], [self.team_id])
        self.assertEqual(self.client.get(f"/teams/{other_team_id}").status_code, 403)
        response = self.client.post(
            f"/teams/{other_team_id}/members",
            json={"principalId": "user:new", "role": "admin"},
        )
        self.assertEqual(response.status_code, 403)


if __name__ == "__main__":
    unittest.main()

"""GitHub metadata respects the owning product's team access."""

import os
import unittest
from unittest.mock import patch

from app.identity import get_current_principal
from app.main import app
from fastapi.testclient import TestClient


class GitHubMetadataTest(unittest.TestCase):
    def setUp(self):
        if not os.environ.get("DATABASE_URL"):
            self.fail("DATABASE_URL must point to a disposable migrated database")
        app.dependency_overrides[get_current_principal] = lambda: "user:owner"
        self.client = TestClient(app)
        org = self.client.post("/organizations", json={"name": "GitHub"}).json()["id"]
        self.org = org
        team = self.client.post(
            f"/organizations/{org}/teams", json={"name": "Team"}
        ).json()["id"]
        product = self.client.post(
            f"/organizations/{org}/products",
            json={"name": "Product", "ownerTeamId": team},
        ).json()["id"]
        binding = self.client.post(
            f"/products/{product}/repositories",
            json={"provider": "github", "repository": "example/repo"},
        ).json()["id"]
        self.url = f"/products/{product}/repositories/{binding}/github"

    def tearDown(self):
        self.client.close()
        app.dependency_overrides.clear()

    def test_metadata_requires_team_read_access(self):
        with (
            patch.dict(os.environ, {"GITHUB_ORGANIZATION_ID": self.org}),
            patch("app.github_repositories.configured_github_source") as source,
        ):
            source.return_value.metadata.return_value = {
                "id": 99,
                "full_name": "example/repo",
                "private": False,
                "default_branch": "main",
            }
            response = self.client.get(self.url)
            self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual(response.json()["full_name"], "example/repo")
            app.dependency_overrides[get_current_principal] = lambda: "user:outsider"
            self.assertEqual(self.client.get(self.url).status_code, 403)
            source.assert_called_once_with("example/repo")

    def test_app_is_not_shared_with_other_organizations(self):
        with (
            patch.dict(os.environ, {"GITHUB_ORGANIZATION_ID": "another-org"}),
            patch("app.github_repositories.configured_github_source") as source,
        ):
            self.assertEqual(self.client.get(self.url).status_code, 403)
            source.assert_not_called()

"""Exercise product ownership and repository bindings through the public API."""

import os
import unittest
from datetime import datetime, timezone

from app.database import get_engine
from app.identity import get_current_principal
from app.main import app
from app.tables import scanner_coverage
from fastapi.testclient import TestClient
from sqlalchemy import insert


class ProductIntegrationTest(unittest.TestCase):
    def setUp(self):
        if not os.environ.get("DATABASE_URL"):
            self.fail("DATABASE_URL must point to a disposable migrated database")
        self.as_principal("user:owner")
        self.client = TestClient(app)
        self.org = self.client.post(
            "/organizations", json={"name": "Product org"}
        ).json()["id"]
        self.other_org = self.client.post(
            "/organizations", json={"name": "Other org"}
        ).json()["id"]
        self.team = self.client.post(
            f"/organizations/{self.org}/teams", json={"name": "Product team"}
        ).json()["id"]
        self.other_team = self.client.post(
            f"/organizations/{self.other_org}/teams", json={"name": "Other team"}
        ).json()["id"]

    def tearDown(self):
        self.client.close()
        app.dependency_overrides.clear()

    @staticmethod
    def as_principal(principal):
        app.dependency_overrides[get_current_principal] = lambda: principal

    def create_product(self, name="Catalog"):
        return self.client.post(
            f"/organizations/{self.org}/products",
            json={"name": name, "ownerTeamId": self.team},
        )

    def test_required_owner_and_organization_filter(self):
        url = f"/organizations/{self.org}/products"
        self.assertEqual(
            self.client.post(url, json={"name": "No owner"}).status_code, 422
        )
        self.assertEqual(
            self.client.post(
                url, json={"name": "Wrong org", "ownerTeamId": self.other_team}
            ).status_code,
            422,
        )
        created = self.create_product()
        self.assertEqual(created.status_code, 201, created.text)
        product = created.json()
        self.assertEqual(product["ownerTeamId"], self.team)
        self.assertEqual(product["organizationId"], self.org)
        self.assertEqual(
            [p["id"] for p in self.client.get(url).json()], [product["id"]]
        )
        self.assertEqual(
            self.client.get(f"/organizations/{self.other_org}/products").json(), []
        )
        self.assertEqual(self.client.delete(f"/teams/{self.team}").status_code, 409)
        self.assertEqual(
            self.client.delete(f"/organizations/{self.org}").status_code, 409
        )

    def test_product_and_binding_crud_and_owner_transfer(self):
        product = self.create_product().json()
        product_url = f"/products/{product['id']}"
        self.assertEqual(self.client.get(product_url).json(), product)
        updated = self.client.patch(product_url, json={"name": "Catalog 2"})
        self.assertEqual(updated.status_code, 200, updated.text)
        self.assertEqual(updated.json()["name"], "Catalog 2")
        self.assertEqual(
            self.client.patch(
                product_url, json={"ownerTeamId": self.other_team}
            ).status_code,
            422,
        )
        replacement_team = self.client.post(
            f"/organizations/{self.org}/teams", json={"name": "Replacement"}
        ).json()["id"]
        transferred = self.client.patch(
            product_url, json={"ownerTeamId": replacement_team}
        )
        self.assertEqual(transferred.status_code, 200, transferred.text)
        self.assertEqual(transferred.json()["ownerTeamId"], replacement_team)
        self.assertEqual(self.client.delete(f"/teams/{self.team}").status_code, 204)
        self.assertEqual(
            self.client.delete(f"/teams/{replacement_team}").status_code, 409
        )
        binding_url = product_url + "/repositories"
        binding = self.client.post(
            binding_url, json={"provider": "github", "repository": "org/repo"}
        )
        self.assertEqual(binding.status_code, 201, binding.text)
        binding_id = binding.json()["id"]
        self.assertEqual(self.client.get(binding_url).json(), [binding.json()])
        self.assertEqual(
            self.client.get(binding_url + "/" + binding_id).json(), binding.json()
        )
        self.assertEqual(
            self.client.post(
                binding_url, json={"provider": "github", "repository": "org/repo"}
            ).status_code,
            409,
        )
        self.assertEqual(
            self.client.patch(
                binding_url + "/" + binding_id,
                json={"provider": "gitlab", "repository": "org/new"},
            ).status_code,
            200,
        )
        self.assertEqual(
            self.client.delete(binding_url + "/" + binding_id).status_code, 204
        )
        self.assertEqual(self.client.delete(product_url).status_code, 204)
        self.assertEqual(self.client.get(product_url).status_code, 404)
        self.assertEqual(
            self.client.delete(f"/teams/{replacement_team}").status_code, 204
        )

    def test_discovery_is_scoped_to_product_and_authorized_team(self):
        product = self.create_product().json()["id"]
        other_product = self.create_product("Other product").json()["id"]

        def binding_for(product_id, repository):
            response = self.client.post(
                f"/products/{product_id}/repositories",
                json={"provider": "github", "repository": repository},
            )
            self.assertEqual(response.status_code, 201)
            return response.json()["id"]

        binding = binding_for(product, "org/catalog")
        other_binding = binding_for(other_product, "org/other")
        url = f"/products/{product}/discovery"
        self.assertEqual(self.client.get(url).json(), [])
        with get_engine().begin() as db:
            for binding_id in (binding, other_binding):
                db.execute(
                    insert(scanner_coverage).values(
                        binding_id=binding_id,
                        scanner="openapi-v1",
                        ref="main",
                        status="partial",
                        source_revision="a" * 40,
                        observed_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
                        files=["openapi.yaml"],
                        errors=[{"path": "broken.yaml", "reason": "invalid"}],
                    )
                )
        result = self.client.get(url)
        self.assertEqual(result.status_code, 200)
        self.assertEqual(len(result.json()), 1)
        scan = result.json()[0]
        self.assertEqual(scan["bindingId"], binding)
        self.assertEqual(scan["repository"], "org/catalog")
        self.assertEqual(scan["status"], "partial")
        self.assertEqual(scan["sourceRevision"], "a" * 40)
        self.assertEqual(scan["files"], ["openapi.yaml"])
        self.assertEqual(scan["errors"][0]["reason"], "invalid")
        self.assertEqual(
            self.client.post(
                f"/teams/{self.team}/members",
                json={"principalId": "user:viewer", "role": "viewer"},
            ).status_code,
            201,
        )
        self.as_principal("user:viewer")
        self.assertEqual(self.client.get(url).status_code, 200)
        self.as_principal("user:outsider")
        self.assertEqual(self.client.get(url).status_code, 403)
        self.assertEqual(self.client.get("/products/missing/discovery").status_code, 404)

    def test_team_role_and_organization_isolation(self):
        product_id = self.create_product().json()["id"]
        for principal, role in (
            ("user:viewer", "viewer"),
            ("user:maintainer", "maintainer"),
        ):
            self.assertEqual(
                self.client.post(
                    f"/teams/{self.team}/members",
                    json={"principalId": principal, "role": role},
                ).status_code,
                201,
            )
        hidden_team = self.client.post(
            f"/organizations/{self.org}/teams", json={"name": "Hidden"}
        ).json()["id"]
        hidden = self.client.post(
            f"/organizations/{self.org}/products",
            json={"name": "Hidden", "ownerTeamId": hidden_team},
        ).json()["id"]
        self.as_principal("user:viewer")
        self.assertEqual(self.client.get(f"/products/{product_id}").status_code, 200)
        self.assertEqual(
            [
                p["id"]
                for p in self.client.get(f"/organizations/{self.org}/products").json()
            ],
            [product_id],
        )
        self.assertEqual(self.client.get(f"/products/{hidden}").status_code, 403)
        self.assertEqual(
            self.client.patch(
                f"/products/{product_id}", json={"name": "Denied"}
            ).status_code,
            403,
        )
        self.assertEqual(self.create_product().status_code, 403)
        self.as_principal("user:maintainer")
        self.assertEqual(
            self.client.patch(
                f"/products/{product_id}", json={"name": "Allowed"}
            ).status_code,
            200,
        )
        self.as_principal("user:outsider")
        self.assertEqual(self.client.get(f"/products/{product_id}").status_code, 403)
        self.assertEqual(
            self.client.get(f"/organizations/{self.org}/products").status_code, 403
        )


if __name__ == "__main__":
    unittest.main()

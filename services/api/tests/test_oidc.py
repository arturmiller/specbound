"""OIDC access-token tests use an isolated local issuer and a disposable database."""

import hashlib
import json
import os
import threading
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import patch
from uuid import uuid4

import jwt
from app.main import app
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text


class OidcIntegrationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not os.environ.get("DATABASE_URL"):
            raise RuntimeError(
                "DATABASE_URL must point to a disposable migrated database"
            )
        cls.private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        jwk = json.loads(
            jwt.algorithms.RSAAlgorithm.to_jwk(cls.private_key.public_key())
        )
        jwk.update({"kid": "test-key", "use": "sig", "alg": "RS256"})
        jwks = json.dumps({"keys": [jwk]}).encode()

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                if self.path != "/jwks":
                    self.send_error(404)
                    return
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(jwks)

            def log_message(self, *_args):
                pass

        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.issuer = f"http://127.0.0.1:{cls.server.server_port}"
        cls.environment = patch.dict(
            os.environ,
            {
                "OIDC_ISSUER": cls.issuer,
                "OIDC_JWKS_URL": f"{cls.issuer}/jwks",
                "OIDC_CLIENT_ID": "specbound-web",
                "OIDC_AUDIENCE": "urn:specbound:api",
            },
        )
        cls.environment.start()

    @classmethod
    def tearDownClass(cls):
        cls.environment.stop()
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=5)

    def token(self, subject, *, claims=None, headers=None, key=None):
        now = int(time.time())
        payload = {
            "iss": self.issuer,
            "sub": subject,
            "aud": "urn:specbound:api",
            "client_id": "specbound-web",
            "scope": "openid profile",
            "iat": now,
            "exp": now + 300,
            "jti": str(uuid4()),
        }
        payload.update(claims or {})
        return jwt.encode(
            payload,
            key or self.private_key,
            algorithm="RS256",
            headers=headers or {"kid": "test-key", "typ": "at+jwt"},
        )

    def test_invalid_tokens_are_rejected(self):
        cases = [
            "malformed",
            self.token("alice", claims={"exp": int(time.time()) - 1}),
            self.token("alice", claims={"iss": "https://untrusted.example"}),
            self.token("alice", claims={"aud": "other-resource"}),
            self.token("alice", claims={"client_id": "another-client"}),
            self.token("alice", claims={"scope": "profile"}),
            self.token("alice", headers={"kid": "test-key", "typ": "JWT"}),
            self.token("alice", claims={"sub": ""}),
            self.token("alice", claims={"sub": "alice\0forged"}),
            self.token("alice", claims={"sub": "x" * 256}),
            self.token("alice", claims={"jti": ""}),
            self.token("alice", claims={"iat": "not-an-integer"}),
            self.token("alice", headers={"kid": "unknown", "typ": "at+jwt"}),
            self.token(
                "alice",
                key=rsa.generate_private_key(public_exponent=65537, key_size=2048),
            ),
        ]
        with TestClient(app) as client:
            self.assertEqual(client.get("/organizations").status_code, 401)
            for token in cases:
                with self.subTest(token=token[:20]):
                    response = client.get(
                        "/organizations", headers={"Authorization": f"Bearer {token}"}
                    )
                    self.assertEqual(response.status_code, 401, response.text)

    def test_verified_users_have_stable_principals_and_isolated_organizations(self):
        alice = self.token("alice")
        bob = self.token("bob")
        with TestClient(app) as client:
            alice_headers = {"Authorization": f"Bearer {alice}"}
            bob_headers = {"Authorization": f"Bearer {bob}"}
            me = client.get("/auth/me", headers=alice_headers)
            self.assertEqual(me.status_code, 200, me.text)
            self.assertEqual(me.json()["kind"], "user")
            self.assertEqual(
                client.get("/auth/me", headers=alice_headers).json()["id"],
                me.json()["id"],
            )
            fresh = {"Authorization": f"Bearer {self.token('alice')}"}
            self.assertEqual(
                client.get("/auth/me", headers=fresh).json()["id"], me.json()["id"]
            )
            org = client.post(
                "/organizations", json={"name": "Alice org"}, headers=alice_headers
            )
            self.assertEqual(org.status_code, 201, org.text)
            org_id = org.json()["id"]
            self.assertEqual(org.json()["ownerPrincipalId"], me.json()["id"])
            self.assertEqual(
                client.get(f"/organizations/{org_id}", headers=bob_headers).status_code,
                403,
            )
            self.assertNotIn(
                org_id,
                [
                    item["id"]
                    for item in client.get("/organizations", headers=bob_headers).json()
                ],
            )
            self.assertIn(
                org_id,
                [
                    item["id"]
                    for item in client.get(
                        "/organizations", headers=alice_headers
                    ).json()
                ],
            )

    def test_registered_agent_is_not_reclassified_as_user(self):
        subject = f"agent-{uuid4()}"
        engine = create_engine(os.environ["DATABASE_URL"])
        try:
            with engine.begin() as connection:
                connection.execute(
                    text(
                        "INSERT INTO principals (id, kind, issuer, subject) VALUES (:id, 'agent', :issuer, :subject)"
                    ),
                    {
                        "id": f"agent:{uuid4()}",
                        "issuer": self.issuer,
                        "subject": subject,
                    },
                )
        finally:
            engine.dispose()
        with TestClient(app) as client:
            response = client.get(
                "/auth/me", headers={"Authorization": f"Bearer {self.token(subject)}"}
            )
            self.assertEqual(response.status_code, 401)

    def test_agent_credentials_cannot_approve_governance_packs(self):
        from app.pack_catalog import github_source_factory
        from test_pack_catalog import FixtureSource

        owner_token = self.token(f"owner-{uuid4()}")
        owner = {"Authorization": f"Bearer {owner_token}"}
        db_engine = create_engine(os.environ["DATABASE_URL"])
        app.dependency_overrides[github_source_factory] = lambda: (
            lambda _repo: FixtureSource("example/packs")
        )
        try:
            with TestClient(app) as client:
                org = client.post(
                    "/organizations",
                    json={"name": "Agent authorization"},
                    headers=owner,
                ).json()["id"]
                team = client.post(
                    f"/organizations/{org}/teams", json={"name": "Team"}, headers=owner
                ).json()["id"]
                agent = client.post(
                    f"/organizations/{org}/agents",
                    json={"name": "Reader"},
                    headers=owner,
                ).json()["id"]
                self.assertEqual(
                    client.post(
                        f"/teams/{team}/members",
                        json={"principalId": agent, "role": "viewer"},
                        headers=owner,
                    ).status_code,
                    201,
                )
                issued = client.post(
                    f"/organizations/{org}/agents/{agent}/credentials", headers=owner
                )
                self.assertEqual(issued.status_code, 201, issued.text)
                self.assertEqual(issued.headers["cache-control"], "no-store")
                credential = issued.json()
                agent_headers = {"Authorization": "Bearer " + credential["token"]}
                listing = client.get(
                    f"/organizations/{org}/agents/{agent}/credentials", headers=owner
                )
                self.assertEqual(listing.status_code, 200)
                self.assertEqual(listing.headers["cache-control"], "no-store")
                self.assertEqual(
                    set(listing.json()[0]), {"id", "expiresAt", "revokedAt"}
                )
                self.assertEqual(listing.json()[0]["id"], credential["id"])
                self.assertNotIn(credential["token"], listing.text)
                self.assertEqual(
                    client.get(
                        f"/organizations/{org}/agents/{agent}/credentials",
                        headers=agent_headers,
                    ).status_code,
                    403,
                )
                with db_engine.begin() as connection:
                    digest = connection.execute(
                        text("SELECT token_hash FROM agent_credentials WHERE id=:id"),
                        {"id": credential["id"]},
                    ).scalar_one()
                    self.assertEqual(
                        digest,
                        hashlib.sha256(credential["token"].encode("ascii")).hexdigest(),
                    )
                    self.assertNotEqual(digest, credential["token"])
                self.assertEqual(
                    client.get("/auth/me", headers=agent_headers).json(),
                    {"id": agent, "kind": "agent"},
                )
                self.assertEqual(
                    client.get(
                        f"/organizations/{org}/teams", headers=agent_headers
                    ).status_code,
                    200,
                )
                other_org = client.post(
                    "/organizations", json={"name": "Separate"}, headers=owner
                ).json()["id"]
                self.assertEqual(
                    client.get(
                        f"/organizations/{other_org}/agents/{agent}/credentials",
                        headers=owner,
                    ).status_code,
                    404,
                )
                self.assertEqual(
                    client.get(
                        f"/organizations/{other_org}/teams", headers=agent_headers
                    ).status_code,
                    403,
                )
                with patch.dict(os.environ, {"OIDC_CLIENT_ID": ""}):
                    self.assertEqual(
                        client.get("/auth/me", headers=agent_headers).status_code, 401
                    )
                self.assertEqual(
                    client.post(
                        "/organizations",
                        json={"name": "Agent org"},
                        headers=agent_headers,
                    ).status_code,
                    403,
                )
                self.assertEqual(
                    client.post(
                        f"/organizations/{org}/agents/{agent}/credentials",
                        headers=agent_headers,
                    ).status_code,
                    403,
                )
                with patch.dict(os.environ, {"GITHUB_ORGANIZATION_ID": org}):
                    created = client.post(
                        f"/organizations/{org}/packs",
                        headers=owner,
                        json={
                            "repository": "example/packs",
                            "tag": "v1",
                            "kind": "governance",
                        },
                    )
                self.assertEqual(created.status_code, 201, created.text)
                approval_url = (
                    f"/organizations/{org}/packs/{created.json()['id']}/approval"
                )
                self.assertEqual(
                    client.put(approval_url, headers=agent_headers).status_code, 403
                )
                self.assertFalse(
                    client.get(approval_url, headers=agent_headers).json()["approved"]
                )
                approved = client.put(approval_url, headers=owner)
                self.assertEqual(approved.status_code, 200, approved.text)
                self.assertTrue(approved.json()["approved"])
                self.assertEqual(
                    client.put(approval_url, headers=owner).status_code, 200
                )
                with db_engine.begin() as connection:
                    self.assertEqual(
                        connection.execute(
                            text(
                                "SELECT count(*) FROM pack_activations WHERE organization_id=:org"
                            ),
                            {"org": org},
                        ).scalar_one(),
                        0,
                    )
                other = {"Authorization": "Bearer " + self.token(f"other-{uuid4()}")}
                self.assertEqual(
                    client.get(
                        f"/organizations/{org}/agents/{agent}/credentials", headers=other
                    ).status_code,
                    403,
                )
                self.assertEqual(
                    client.put(approval_url, headers=other).status_code, 403
                )
                self.assertEqual(
                    client.put(approval_url, headers=agent_headers).status_code, 403
                )
                self.assertEqual(
                    client.delete(approval_url, headers=agent_headers).status_code, 403
                )
                self.assertEqual(
                    client.delete(approval_url, headers=owner).status_code, 204
                )
                events = client.get(
                    f"/organizations/{org}/audit-events", headers=owner
                ).json()
                self.assertNotIn(credential["token"], json.dumps(events))
                self.assertEqual(
                    sum(event["action"] == "governance.approved" for event in events), 1
                )
                self.assertEqual(
                    client.delete(
                        f"/organizations/{org}/agents/{agent}/credentials/{credential['id']}",
                        headers=owner,
                    ).status_code,
                    204,
                )
                self.assertEqual(
                    client.get("/auth/me", headers=agent_headers).status_code, 401
                )
                listed_after_revoke = client.get(
                    f"/organizations/{org}/agents/{agent}/credentials", headers=owner
                ).json()
                self.assertIsNotNone(listed_after_revoke[0]["revokedAt"])
                expired = client.post(
                    f"/organizations/{org}/agents/{agent}/credentials", headers=owner
                ).json()
                with db_engine.begin() as connection:
                    connection.execute(
                        text(
                            "UPDATE agent_credentials SET expires_at=CURRENT_TIMESTAMP - INTERVAL '1 second' WHERE id=:id"
                        ),
                        {"id": expired["id"]},
                    )
                self.assertEqual(
                    client.get(
                        "/auth/me",
                        headers={"Authorization": "Bearer " + expired["token"]},
                    ).status_code,
                    401,
                )
        finally:
            app.dependency_overrides.clear()
            db_engine.dispose()

    def test_parallel_first_requests_resolve_the_same_user(self):
        for _ in range(3):
            token = self.token(f"parallel-{uuid4()}")
            barrier = threading.Barrier(6)

            def request_user():
                with TestClient(app) as client:
                    barrier.wait(timeout=15)
                    response = client.get(
                        "/auth/me", headers={"Authorization": f"Bearer {token}"}
                    )
                    return response.status_code, response.json()

            with ThreadPoolExecutor(max_workers=6) as pool:
                results = list(pool.map(lambda _: request_user(), range(6)))
            self.assertEqual([status for status, _ in results], [200] * 6, results)
            self.assertEqual(len({body["id"] for _, body in results}), 1)

    def test_principal_id_collision_is_rejected(self):
        subject = f"collision-{uuid4()}"
        principal_id = (
            "user:"
            + hashlib.sha256(f"{self.issuer}\0{subject}".encode("utf-8")).hexdigest()
        )
        engine = create_engine(os.environ["DATABASE_URL"])
        try:
            with engine.begin() as connection:
                connection.execute(
                    text(
                        "INSERT INTO principals (id, kind, issuer, subject) VALUES (:id, 'agent', :issuer, :subject)"
                    ),
                    {
                        "id": principal_id,
                        "issuer": self.issuer,
                        "subject": str(uuid4()),
                    },
                )
        finally:
            engine.dispose()
        with TestClient(app) as client:
            response = client.get(
                "/auth/me", headers={"Authorization": f"Bearer {self.token(subject)}"}
            )
            self.assertEqual(response.status_code, 401)

    def test_insecure_or_incomplete_provider_configuration_fails_closed(self):
        with TestClient(app) as client:
            for environment in (
                {"OIDC_JWKS_URL": ""},
                {"OIDC_ISSUER": "http://untrusted.example"},
                {
                    "OIDC_ISSUER": "https://trusted.example",
                    "OIDC_JWKS_URL": "http://127.0.0.1:18764/jwks",
                },
                {"OIDC_AUDIENCE": "specbound-web"},
            ):
                with (
                    self.subTest(environment=environment),
                    patch.dict(os.environ, environment),
                ):
                    self.assertEqual(
                        client.get("/auth/config").json(), {"enabled": False}
                    )
                    response = client.get(
                        "/organizations",
                        headers={"Authorization": f"Bearer {self.token('alice')}"},
                    )
                    self.assertEqual(response.status_code, 401)

    def test_issuer_with_trailing_slash_is_verified_exactly(self):
        issuer = self.issuer + "/"
        with patch.dict(os.environ, {"OIDC_ISSUER": issuer}), TestClient(app) as client:
            token = self.token("alice", claims={"iss": issuer})
            response = client.get(
                "/auth/me", headers={"Authorization": f"Bearer {token}"}
            )
            self.assertEqual(response.status_code, 200, response.text)


if __name__ == "__main__":
    unittest.main()

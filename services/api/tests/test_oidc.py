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
        principal_id = "user:" + hashlib.sha256(
            f"{self.issuer}\0{subject}".encode("utf-8")
        ).hexdigest()
        engine = create_engine(os.environ["DATABASE_URL"])
        try:
            with engine.begin() as connection:
                connection.execute(
                    text(
                        "INSERT INTO principals (id, kind, issuer, subject) VALUES (:id, 'agent', :issuer, :subject)"
                    ),
                    {"id": principal_id, "issuer": self.issuer, "subject": str(uuid4())},
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

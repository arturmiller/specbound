"""Webhook delivery through HTTP and durable event intake."""

import hashlib
import hmac
import json
import os
import unittest
from unittest.mock import patch
from uuid import uuid4

from app.database import get_engine
from app.github_webhook import list_github_events
from app.main import app
from fastapi.testclient import TestClient


class GithubWebhookTest(unittest.TestCase):
    def setUp(self):
        if not os.environ.get("DATABASE_URL"):
            self.fail("DATABASE_URL must point to a disposable migrated database")
        self.settings = patch.dict(
            os.environ,
            {
                "GITHUB_WEBHOOK_SECRET": "fixture-secret",
                "GITHUB_INSTALLATION_ID": "12345",
                "GITHUB_ORGANIZATION_ID": "123e4567-e89b-12d3-a456-426614174000",
            },
        )
        self.settings.start()
        self.client = TestClient(app)
        self.delivery = str(uuid4())
        self.body = json.dumps(
            {
                "installation": {"id": 12345},
                "repository": {"id": 99, "full_name": "example/repo"},
                "ref": "refs/heads/main",
            }
        ).encode()
        self.signature = (
            "sha256="
            + hmac.new(b"fixture-secret", self.body, hashlib.sha256).hexdigest()
        )

    def tearDown(self):
        self.client.close()
        self.settings.stop()

    def send(self, signature, body=None, delivery=None):
        return self.client.post(
            "/webhooks/github",
            content=self.body if body is None else body,
            headers={
                "X-Hub-Signature-256": signature,
                "X-GitHub-Event": "push",
                "X-GitHub-Delivery": delivery or self.delivery,
            },
        )

    def test_invalid_signature_does_not_persist_and_valid_delivery_is_idempotent(self):
        self.assertEqual(self.send("sha256=" + "0" * 64).status_code, 401)
        self.assertEqual(
            self.send(self.signature, body=self.body + b" ").status_code, 401
        )
        with get_engine().begin() as db:
            self.assertEqual(list_github_events(db, self.delivery), [])
        self.assertEqual(self.send(self.signature).status_code, 202)
        self.assertEqual(self.send(self.signature).status_code, 202)
        with get_engine().begin() as db:
            events = list_github_events(db, self.delivery)
        self.assertEqual(len(events), 1)
        self.assertEqual(
            events[0]["payload"]["repository"]["full_name"], "example/repo"
        )
        self.assertEqual(events[0]["event_type"], "push")

    def test_missing_secret_and_wrong_installation_are_rejected(self):
        with patch.dict(os.environ, {"GITHUB_WEBHOOK_SECRET": ""}):
            self.assertEqual(self.send(self.signature).status_code, 401)
        with patch.dict(os.environ, {"GITHUB_INSTALLATION_ID": "67890"}):
            self.assertEqual(self.send(self.signature).status_code, 403)

    def test_signed_malformed_payload_and_large_payload_are_rejected(self):
        body = b"not json"
        signature = (
            "sha256=" + hmac.new(b"fixture-secret", body, hashlib.sha256).hexdigest()
        )
        self.assertEqual(self.send(signature, body=body).status_code, 400)
        self.assertEqual(
            self.send(self.signature, body=b"x" * (2 * 1024 * 1024 + 1)).status_code,
            413,
        )


if __name__ == "__main__":
    unittest.main()

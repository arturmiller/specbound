"""GitHub adapter contract with a deterministic GitHub API transport."""

import base64
import unittest

import httpx
from app.git_source import SourceNotFound, SourceUnavailable
from app.github_source import GitHubSource
from app.pr_check import publish_check
from app.pr_comment import MARKER, upsert_comment
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

COMMIT = "a" * 40
TAG = "b" * 40
BLOB = "c" * 40


class GitHubSourceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        cls.pem = key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )

    def setUp(self):
        self.paths = []

        def handle(request):
            self.paths.append(request.url.path)
            path = request.url.path
            if path == "/repos/example/repo/installation":
                return httpx.Response(200, json={"id": 123})
            if path == "/app/installations/123/access_tokens":
                return httpx.Response(201, json={"token": "fixture-token"})
            if request.headers.get("authorization") != "Bearer fixture-token":
                return httpx.Response(401)
            if path == "/repos/example/repo":
                return httpx.Response(
                    200,
                    json={
                        "id": 99,
                        "full_name": "example/repo",
                        "default_branch": "main",
                        "private": False,
                    },
                )
            if path == "/repos/example/repo/git/ref/tags/v1":
                return httpx.Response(200, json={"object": {"type": "tag", "sha": TAG}})
            if path == "/repos/example/repo/git/tags/" + TAG:
                return httpx.Response(
                    200, json={"object": {"type": "commit", "sha": COMMIT}}
                )
            if path == "/repos/example/repo/commits/main":
                return httpx.Response(
                    200, json={"sha": COMMIT, "commit": {"tree": {"sha": COMMIT}}}
                )
            if path == "/repos/example/repo/git/trees/" + COMMIT:
                return httpx.Response(
                    200,
                    json={
                        "truncated": False,
                        "tree": [
                            {
                                "type": "blob",
                                "mode": "100644",
                                "path": "README.md",
                                "sha": BLOB,
                                "size": 5,
                            }
                        ],
                    },
                )
            if path == "/repos/example/repo/git/blobs/" + BLOB:
                return httpx.Response(
                    200,
                    json={
                        "encoding": "base64",
                        "content": base64.b64encode(b"hello").decode(),
                    },
                )
            return httpx.Response(404)

        self.handler = handle
        self.client = httpx.Client(transport=httpx.MockTransport(handle))
        self.source = GitHubSource(
            "example/repo",
            app_id="1234",
            installation_id=123,
            private_key=self.pem,
            client=self.client,
        )

    def tearDown(self):
        self.client.close()

    def test_metadata_tag_and_snapshot(self):
        self.assertEqual(self.source.metadata()["full_name"], "example/repo")
        self.assertEqual(self.source.resolve_tag("v1"), COMMIT)
        snapshot = self.source.fetch("main")
        self.assertEqual(snapshot.commit, COMMIT)
        self.assertEqual(snapshot.files["README.md"], b"hello")

    def test_missing_refs_and_wrong_installation_are_rejected(self):
        with self.assertRaises(SourceNotFound):
            self.source.resolve_tag("missing")
        wrong = GitHubSource(
            "example/repo",
            app_id="1234",
            installation_id=999,
            private_key=self.pem,
            client=self.client,
        )
        with self.assertRaises(SourceUnavailable):
            wrong.metadata()

    def test_signature_uses_github_published_vector_and_header_is_case_insensitive(
        self,
    ):
        source = GitHubSource(
            "example/repo",
            app_id="1234",
            installation_id=123,
            private_key=self.pem,
            webhook_secret=b"It's a Secret to Everybody",
            client=self.client,
        )
        signature = (
            "sha256=757107ea0eb2509fc211221cce984b8a37570b6d7586c22c46f4379c8b043e17"
        )
        self.assertTrue(
            source.verify_webhook({"X-Hub-Signature-256": signature}, b"Hello, World!")
        )
        self.assertFalse(
            source.verify_webhook({"X-Hub-Signature-256": signature}, b"changed")
        )

    def test_truncated_tree_and_unsafe_repository_are_rejected(self):
        def truncated(request):
            if "/git/trees/" in request.url.path:
                return httpx.Response(200, json={"truncated": True, "tree": []})
            return self.handler(request)

        with httpx.Client(transport=httpx.MockTransport(truncated)) as client:
            source = GitHubSource(
                "example/repo",
                app_id="1234",
                installation_id=123,
                private_key=self.pem,
                client=client,
            )
            with self.assertRaises(SourceUnavailable):
                source.fetch("main")
        with self.assertRaises(ValueError):
            GitHubSource(
                "../repo", app_id="1234", installation_id=123, private_key=self.pem
            )

    def test_comment_upsert_uses_scoped_token_and_bot_identity(self):
        import json

        comments = []
        head = ["a" * 40]
        requests = []

        def handle(request):
            requests.append(request)
            path = request.url.path
            if path.endswith("/installation"):
                return httpx.Response(200, json={"id": 123, "app_slug": "sample-app"})
            if path.endswith("/access_tokens"):
                self.assertEqual(
                    json.loads(request.content)["permissions"],
                    {"pull_requests": "write"},
                )
                return httpx.Response(201, json={"token": "fixture-token"})
            self.assertEqual(request.headers["authorization"], "Bearer fixture-token")
            if path.endswith("/pulls/3"):
                return httpx.Response(200, json={"head": {"sha": head[0]}})
            if path.endswith("/issues/3/comments") and request.method == "GET":
                return httpx.Response(200, json=comments)
            if path.endswith("/issues/3/comments") and request.method == "POST":
                comments.append(
                    {
                        "id": 100,
                        "body": json.loads(request.content)["body"],
                        "user": {"login": "sample-app[bot]", "type": "Bot"},
                        "performed_via_github_app": None,
                    }
                )
                return httpx.Response(201, json=comments[0])
            if path.endswith("/issues/comments/100") and request.method == "PATCH":
                comments[0]["body"] = json.loads(request.content)["body"]
                return httpx.Response(200, json=comments[0])
            return httpx.Response(404)

        with httpx.Client(transport=httpx.MockTransport(handle)) as client:
            source = GitHubSource(
                "example/repo",
                app_id="1234",
                installation_id=123,
                private_key=self.pem,
                client=client,
            )
            for index, letter in enumerate("abc"):
                head[0] = letter * 40
                self.assertTrue(
                    upsert_comment(
                        source,
                        3,
                        head[0],
                        {"PASS": index, "FAIL": 0, "UNKNOWN": 0, "NOT_APPLICABLE": 0},
                        "https://portal.example",
                        "snap-" + letter,
                    )
                )
        self.assertEqual(len(comments), 1)
        self.assertTrue(comments[0]["body"].startswith(MARKER + "\nPassed: 2"))
        self.assertEqual(
            sum(
                r.method == "POST" and r.url.path.endswith("/issues/3/comments")
                for r in requests
            ),
            1,
        )

    def test_checks_api_never_writes_a_newer_sha_for_stale_job(self):
        import json
        from datetime import datetime, timedelta, timezone
        from unittest.mock import patch

        current = ["b" * 40]
        check_runs = []
        sent = []

        def handle(request):
            path = request.url.path
            if path.endswith("/installation"):
                return httpx.Response(200, json={"id": 123, "app_slug": "sample-app"})
            if path.endswith("/access_tokens"):
                self.assertEqual(
                    json.loads(request.content)["permissions"],
                    {"pull_requests": "read", "checks": "write"},
                )
                return httpx.Response(201, json={"token": "fixture-token"})
            if path.endswith("/pulls/3"):
                return httpx.Response(200, json={"head": {"sha": current[0]}})
            if "/commits/" in path:
                return httpx.Response(200, json={"check_runs": check_runs})
            if path.endswith("/check-runs") and request.method == "POST":
                data = json.loads(request.content)
                sent.append(data)
                check_runs.append({**data, "id": 1, "app": {"id": 1234}})
                return httpx.Response(201, json=check_runs[0])
            return httpx.Response(404)

        now = datetime(2026, 1, 1, tzinfo=timezone.utc)
        job = {"id": "job", "pull_request_number": 3, "head_sha": "a" * 40}
        with httpx.Client(transport=httpx.MockTransport(handle)) as client:
            source = GitHubSource(
                "example/repo",
                app_id="1234",
                installation_id=123,
                private_key=self.pem,
                client=client,
            )
            with patch(
                "app.pr_check.assess_snapshot",
                return_value=("success", now + timedelta(seconds=60)),
            ):
                self.assertIsNone(publish_check(None, source, job, {}, "", now))
                self.assertEqual(sent, [])
                current[0] = "a" * 40
                publish_check(None, source, job, {}, "", now)
        self.assertEqual(sent[0]["head_sha"], "a" * 40)
        self.assertEqual(sent[0]["conclusion"], "success")


if __name__ == "__main__":
    unittest.main()

"""GitHub adapter contract with a deterministic GitHub API transport."""

import base64
import unittest

import httpx
from app.git_source import SourceNotFound, SourceUnavailable
from app.github_source import GitHubSource
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


if __name__ == "__main__":
    unittest.main()

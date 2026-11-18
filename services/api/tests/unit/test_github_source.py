"""GitHub adapter contract with a deterministic GitHub API transport."""

import asyncio
import base64
import socket
import time
import unittest

import httpx
from app.git_source import InvalidGitReference, SourceNotFound, SourceUnavailable
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
            if path in (
                "/repos/example/repo/commits/main",
                "/repos/example/repo/commits/heads/main",
            ):
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
            resource_client_factory=lambda: httpx.AsyncClient(
                transport=httpx.MockTransport(self.handler)
            ),
        )

    def tearDown(self):
        self.client.close()

    def test_metadata_tag_and_snapshot(self):
        self.assertEqual(self.source.metadata()["full_name"], "example/repo")
        self.assertEqual(self.source.resolve_tag("v1"), COMMIT)
        snapshot = self.source.fetch("main")
        self.assertEqual(snapshot.commit, COMMIT)
        self.assertEqual(snapshot.files["README.md"], b"hello")

    def test_qualified_branch_preserves_the_raw_ref_length_limit(self):
        branch = "x" * 200

        def handle(request):
            if request.url.path == "/repos/example/repo/commits/heads/" + branch:
                return httpx.Response(
                    200, json={"sha": COMMIT, "commit": {"tree": {"sha": COMMIT}}}
                )
            return self.handler(request)

        with httpx.Client(transport=httpx.MockTransport(handle)) as client:
            source = GitHubSource(
                "example/repo",
                app_id="1234",
                installation_id=123,
                private_key=self.pem,
                client=client,
            )
            self.assertEqual(source.fetch("heads/" + branch).commit, COMMIT)
            with self.assertRaises(InvalidGitReference):
                source.fetch("heads/" + branch + "x")

    def test_python_lockfile_fetch_limits_token_and_downloaded_blobs(self):
        import json

        lock_sha = "d" * 40
        requests = []

        def handle(request):
            requests.append(request)
            if request.url.path.endswith("/access_tokens"):
                token_scope = json.loads(request.content)
                self.assertEqual(token_scope["repositories"], ["repo"])
                self.assertEqual(token_scope["permissions"], {"contents": "read"})
            if "/git/trees/" in request.url.path:
                return httpx.Response(
                    200,
                    json={
                        "truncated": False,
                        "tree": [
                            {
                                "type": "blob",
                                "mode": "100644",
                                "path": "private.txt",
                                "sha": BLOB,
                                "size": 5,
                            },
                            {
                                "type": "blob",
                                "mode": "100644",
                                "path": "src/uv.lock",
                                "sha": lock_sha,
                                "size": 5,
                            },
                        ],
                    },
                )
            if request.url.path.endswith("/git/blobs/" + lock_sha):
                return httpx.Response(
                    200,
                    json={
                        "encoding": "base64",
                        "content": base64.b64encode(b"hello").decode(),
                    },
                )
            return self.handler(request)

        with httpx.Client(transport=httpx.MockTransport(handle)) as client:
            source = GitHubSource(
                "example/repo",
                app_id="1234",
                installation_id=123,
                private_key=self.pem,
                client=client,
            )
            snapshot = source.fetch_python_lockfiles("main")
        self.assertEqual(snapshot.commit, COMMIT)
        self.assertEqual(dict(snapshot.files), {"src/uv.lock": b"hello"})
        self.assertFalse(
            any(request.url.path.endswith("/git/blobs/" + BLOB) for request in requests)
        )

    def test_python_lockfile_fetch_rejects_incomplete_tree(self):
        def handle(request):
            if "/git/trees/" in request.url.path:
                return httpx.Response(200, json={"truncated": True, "tree": []})
            return self.handler(request)

        with httpx.Client(transport=httpx.MockTransport(handle)) as client:
            source = GitHubSource(
                "example/repo",
                app_id="1234",
                installation_id=123,
                private_key=self.pem,
                client=client,
            )
            with self.assertRaises(SourceUnavailable):
                source.fetch_python_lockfiles("main")

    def test_scoped_read_rejects_referenced_symlink_without_downloading_it(self):
        def handle(request):
            if "/git/trees/" in request.url.path:
                return httpx.Response(
                    200,
                    json={
                        "truncated": False,
                        "tree": [
                            {
                                "type": "blob",
                                "mode": "120000",
                                "path": "README.md",
                                "sha": BLOB,
                                "size": 5,
                            }
                        ],
                    },
                )
            return self.handler(request)

        with httpx.Client(transport=httpx.MockTransport(handle)) as client:
            source = GitHubSource(
                "example/repo",
                app_id="1234",
                installation_id=123,
                private_key=self.pem,
                client=client,
                resource_client_factory=lambda: httpx.AsyncClient(
                    transport=httpx.MockTransport(handle)
                ),
            )
            with self.assertRaisesRegex(SourceUnavailable, "Symlinks"):
                source.load_resource(
                    "main", "README.md", lambda snapshot, path: snapshot.files[path]
                )
        self.assertFalse(any("/git/blobs/" in path for path in self.paths))

    def test_scoped_read_keeps_cumulative_byte_limit(self):
        from unittest.mock import patch

        def handle(request):
            if "/git/trees/" in request.url.path:
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
                            },
                            {
                                "type": "blob",
                                "mode": "100644",
                                "path": "other.json",
                                "sha": "d" * 40,
                                "size": 6,
                            },
                        ],
                    },
                )
            return self.handler(request)

        with (
            httpx.Client(transport=httpx.MockTransport(handle)) as client,
            patch("app.github_source.MAX_BYTES", 10),
        ):
            source = GitHubSource(
                "example/repo",
                app_id="1234",
                installation_id=123,
                private_key=self.pem,
                client=client,
                resource_client_factory=lambda: httpx.AsyncClient(
                    transport=httpx.MockTransport(handle)
                ),
            )
            with self.assertRaisesRegex(SourceUnavailable, "size limit"):
                source.load_resource(
                    "main",
                    "README.md",
                    lambda snapshot, path: (
                        snapshot.files[path],
                        snapshot.files["other.json"],
                    ),
                )
        self.assertEqual(sum("/git/blobs/" in path for path in self.paths), 1)

    def test_scoped_read_deadline_also_bounds_tag_resolution(self):
        from unittest.mock import patch

        from app.git_source import SourceReadTimeout

        now = [0.0]

        def handle(request):
            if "/git/ref/tags/" in request.url.path:
                now[0] = 31.0
            return self.handler(request)

        with (
            httpx.Client(transport=httpx.MockTransport(handle)) as client,
            patch("app.github_source.time.monotonic", side_effect=lambda: now[0]),
        ):
            source = GitHubSource(
                "example/repo",
                app_id="1234",
                installation_id=123,
                private_key=self.pem,
                client=client,
                resource_client_factory=lambda: httpx.AsyncClient(
                    transport=httpx.MockTransport(handle)
                ),
            )
            with self.assertRaises(SourceReadTimeout):
                source.load_resource(
                    "v1",
                    "README.md",
                    lambda snapshot, path: snapshot.files[path],
                    ref_kind="tag",
                )
            self.assertIsNone(source._resource_deadline)
        self.assertFalse(any("/git/tags/" in path for path in self.paths))

    def test_scoped_read_checks_reviewed_commit_before_fetching_any_blob(self):
        from app.git_source import SourceRevisionChanged
        from app.manifest_source import load_resource_for_ref

        with self.assertRaises(SourceRevisionChanged):
            load_resource_for_ref(
                self.source,
                "example/repo",
                "main",
                "branch",
                "catalog.json",
                lambda snapshot, path: snapshot.files[path],
                expected_commit="d" * 40,
            )
        self.assertFalse(any("/git/blobs/" in path for path in self.paths))

    def test_scoped_read_interrupts_a_continuously_trickling_response(self):
        from unittest.mock import patch

        from app.git_source import SourceReadTimeout

        class SlowBody(httpx.SyncByteStream, httpx.AsyncByteStream):
            chunks = 0
            closed = False

            def __iter__(self):
                for _ in range(50):
                    time.sleep(0.05)
                    self.chunks += 1
                    yield b" "
                yield b'{"encoding":"base64","content":"aGVsbG8="}'

            async def __aiter__(self):
                for _ in range(50):
                    await asyncio.sleep(0.05)
                    self.chunks += 1
                    yield b" "
                yield b'{"encoding":"base64","content":"aGVsbG8="}'

            def close(self):
                self.closed = True

            async def aclose(self):
                self.closed = True

        stream = SlowBody()

        def handle(request):
            if "/git/blobs/" in request.url.path:
                return httpx.Response(200, stream=stream)
            return self.handler(request)

        with (
            httpx.Client(transport=httpx.MockTransport(handle)) as client,
            patch("app.github_source.RESOURCE_READ_SECONDS", 0.5),
            patch.object(GitHubSource, "_token", return_value="fixture-token"),
        ):
            source = GitHubSource(
                "example/repo",
                app_id="1234",
                installation_id=123,
                private_key=self.pem,
                client=client,
                resource_client_factory=lambda: httpx.AsyncClient(
                    transport=httpx.MockTransport(handle)
                ),
            )
            started = time.monotonic()
            with self.assertRaises(SourceReadTimeout):
                source.load_resource(
                    "main", "README.md", lambda snapshot, path: snapshot.files[path]
                )
            self.assertLess(time.monotonic() - started, 1.5)
        self.assertLess(stream.chunks, 50)
        self.assertTrue(stream.closed)
        self.assertIsNone(source._resource_deadline)

    def test_slow_dns_does_not_delay_the_resource_timeout(self):
        from threading import Event
        from unittest.mock import patch

        from app.git_source import SourceReadTimeout

        resolver_started, resolver_finished, release_resolver = (
            Event(),
            Event(),
            Event(),
        )
        resource_client = httpx.AsyncClient(trust_env=False)

        def slow_resolver(*_args, **_kwargs):
            resolver_started.set()
            try:
                release_resolver.wait(3)
                raise socket.gaierror("Test resolver unavailable")
            finally:
                resolver_finished.set()

        with (
            patch("app.github_source.RESOURCE_READ_SECONDS", 0.5),
            patch("socket.getaddrinfo", side_effect=slow_resolver),
            patch.object(self.source, "_token", return_value="fixture-token"),
            patch.object(
                self.source,
                "_resource_client_factory",
                return_value=resource_client,
            ),
        ):
            try:
                started = time.monotonic()
                with self.assertRaises(SourceReadTimeout):
                    self.source.load_resource(
                        "main", "README.md", lambda snapshot, path: snapshot.files[path]
                    )
                self.assertLess(time.monotonic() - started, 1.5)
                self.assertTrue(resolver_started.is_set())
                self.assertFalse(resolver_finished.is_set())
                self.assertIsNone(self.source._resource_runner)
            finally:
                release_resolver.set()
                self.assertTrue(resolver_finished.wait(3))

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

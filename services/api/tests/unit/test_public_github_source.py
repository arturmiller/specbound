"""Anonymous GitHub scans neither require nor send an access token."""

import base64
import io
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

import httpx
from app.git_source import SourceNotFound, SourceUnavailable
from app.public_github_source import PublicGitHubRateLimit, PublicGitHubSource
from examples.scan_python_licenses import main as scan_cli

COMMIT = "a" * 40
BLOB = "b" * 40
OTHER = "c" * 40


class PublicGitHubSourceTest(unittest.TestCase):
    def test_public_scan_fetches_only_lockfile_without_authentication(self):
        requests = []

        def handle(request):
            requests.append(request)
            self.assertEqual(request.url.host, "api.github.com")
            self.assertNotIn("authorization", request.headers)
            self.assertEqual(request.method, "GET")
            path = request.url.path
            if path.endswith("/commits/main"):
                return httpx.Response(
                    200, json={"sha": COMMIT, "commit": {"tree": {"sha": COMMIT}}}
                )
            if "/git/trees/" in path:
                return httpx.Response(
                    200,
                    json={
                        "truncated": False,
                        "tree": [
                            {
                                "type": "blob",
                                "mode": "100644",
                                "path": "uv.lock",
                                "sha": BLOB,
                                "size": 5,
                            },
                            {
                                "type": "blob",
                                "mode": "100644",
                                "path": "other.txt",
                                "sha": OTHER,
                                "size": 4,
                            },
                        ],
                    },
                )
            if path.endswith("/git/blobs/" + BLOB):
                return httpx.Response(
                    200,
                    json={
                        "encoding": "base64",
                        "content": base64.b64encode(b"hello").decode(),
                    },
                )
            return httpx.Response(404)

        with httpx.Client(transport=httpx.MockTransport(handle)) as client:
            source = PublicGitHubSource("example/repo", client=client)
            snapshot = source.fetch_python_lockfiles("main")
            with self.assertRaises(SourceUnavailable):
                source._request("POST", "/anything", None)
        self.assertEqual(snapshot.commit, COMMIT)
        self.assertEqual(dict(snapshot.files), {"uv.lock": b"hello"})
        self.assertFalse(any(request.url.path.endswith(OTHER) for request in requests))

    def test_rate_limit_and_missing_repository_are_distinct_failures(self):
        for code, headers, error in (
            (403, {"x-ratelimit-remaining": "0"}, PublicGitHubRateLimit),
            (429, {}, PublicGitHubRateLimit),
            (404, {}, SourceNotFound),
            (403, {}, SourceUnavailable),
        ):
            with self.subTest(code=code, headers=headers):
                with httpx.Client(
                    transport=httpx.MockTransport(
                        lambda request: httpx.Response(code, headers=headers)
                    )
                ) as client:
                    with self.assertRaises(error):
                        PublicGitHubSource("example/repo", client=client).fetch("main")

    def test_invalid_repository_and_elevated_permissions_are_rejected(self):
        for repository in ("../repo", "https://github.com/a/b", "a/b/c"):
            with self.subTest(repository=repository), self.assertRaises(ValueError):
                PublicGitHubSource(repository)
        source = PublicGitHubSource("example/repo")
        try:
            with self.assertRaises(SourceUnavailable):
                source._token(permissions={"contents": "write"})
        finally:
            source.close()

    def test_explicit_public_cli_does_not_construct_authenticated_source(self):
        class Source:
            def close(self):
                pass

        result = {"coverage": "covered", "packages": []}
        with (
            patch(
                "examples.scan_python_licenses.PublicGitHubSource",
                return_value=Source(),
            ) as public,
            patch("examples.scan_python_licenses.configured_github_source") as private,
            patch(
                "examples.scan_python_licenses.scan_python_repository",
                return_value=result,
            ),
            redirect_stdout(io.StringIO()),
        ):
            self.assertEqual(scan_cli(["--public", "example/repo", "main"]), 0)
        public.assert_called_once_with("example/repo")
        private.assert_not_called()

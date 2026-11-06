"""Contract exercised with a deterministic, in-memory Git source adapter."""

import hashlib
import hmac
import unittest

from app.git_source import (
    GitSnapshot,
    InvalidGitReference,
    SourceNotFound,
)


class FakeGitSource:
    def __init__(self):
        self.tags = {"v1.0.0": "a" * 40}
        self.commits = {
            "a" * 40: {"openapi.yaml": b"version: 1\n"},
            "b" * 40: {"openapi.yaml": b"version: 2\n"},
        }

    def resolve_tag(self, tag):
        if not isinstance(tag, str) or not tag.strip():
            raise InvalidGitReference("tag must not be empty")
        try:
            return self.tags[tag]
        except KeyError as exc:
            raise SourceNotFound("tag not found") from exc

    def fetch(self, ref):
        if not isinstance(ref, str) or not ref.strip():
            raise InvalidGitReference("ref must not be empty")
        commit = self.tags.get(ref, ref)
        try:
            return GitSnapshot(commit, self.commits[commit])
        except KeyError as exc:
            raise SourceNotFound("ref not found") from exc

    def verify_webhook(self, headers, payload):
        expected = hmac.new(b"test-only", payload, hashlib.sha256).hexdigest()
        signature = headers.get("x-fake-signature", "")
        return hmac.compare_digest(signature, expected)


class GitSourceContractTest(unittest.TestCase):
    def setUp(self):
        self.source = FakeGitSource()

    def test_tag_resolves_to_pinned_commit_and_snapshot_survives_tag_move(self):
        commit = self.source.resolve_tag("v1.0.0")
        snapshot = self.source.fetch(commit)
        self.source.tags["v1.0.0"] = "b" * 40
        self.assertEqual(commit, "a" * 40)
        self.assertEqual(snapshot.commit, commit)
        self.assertEqual(snapshot.files["openapi.yaml"], b"version: 1\n")
        self.assertEqual(self.source.fetch("v1.0.0").commit, "b" * 40)
        self.assertEqual(self.source.fetch(commit), snapshot)
        with self.assertRaises(TypeError):
            snapshot.files["openapi.yaml"] = b"modified"

    def test_missing_and_invalid_refs_are_distinct(self):
        for method in (self.source.fetch, self.source.resolve_tag):
            with self.subTest(method=method.__name__, ref=""):
                with self.assertRaises(InvalidGitReference):
                    method("")
            with self.subTest(method=method.__name__, ref="unknown"):
                with self.assertRaises(SourceNotFound):
                    method("unknown")

    def test_webhook_verification_uses_exact_raw_payload(self):
        body = b'{"action":"push"}'
        signature = hmac.new(b"test-only", body, hashlib.sha256).hexdigest()
        self.assertTrue(self.source.verify_webhook({"x-fake-signature": signature}, body))
        self.assertFalse(self.source.verify_webhook({"x-fake-signature": signature}, body + b" "))
        self.assertFalse(self.source.verify_webhook({}, body))

    def test_snapshot_rejects_mutable_or_unsafe_provenance(self):
        for commit, files in (
            ("main", {"a": b"a"}),
            ("a" * 40, {"../secret": b"a"}),
            ("a" * 40, {"/absolute": b"a"}),
            ("a" * 40, {"file": "not bytes"}),
        ):
            with self.subTest(commit=commit, files=files), self.assertRaises(ValueError):
                GitSnapshot(commit, files)


if __name__ == "__main__":
    unittest.main()

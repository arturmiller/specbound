"""PR summary publication reuses only the configured app's own comment."""

import unittest
from urllib.parse import urlsplit

from app.pr_comment import MARKER, render_comment, upsert_comment


class FakeGitHub:
    repository = "example/repo"
    app_id = "42"
    _installation_slug = "specbound"

    def __init__(self):
        self.head = "a" * 40
        self.comments = []
        self.permissions = None

    def _token(self, *, permissions):
        self.permissions = permissions
        return "fixture"

    def _request(self, method, path, token, **kwargs):
        assert token == "fixture"
        path = urlsplit(path).path
        if method == "GET" and path.endswith("/pulls/3"):
            return {"head": {"sha": self.head}}
        if method == "GET" and path.endswith("/issues/3/comments"):
            return self.comments
        if method == "POST" and path.endswith("/issues/3/comments"):
            comment = {
                "id": 1 + len(self.comments),
                "body": kwargs["json"]["body"],
                "performed_via_github_app": {"id": 42},
                "user": {"login": "specbound[bot]", "type": "Bot"},
            }
            self.comments.append(comment)
            return comment
        if method == "PATCH" and "/issues/comments/" in path:
            comment = next(
                c for c in self.comments if c["id"] == int(path.rsplit("/", 1)[1])
            )
            comment["body"] = kwargs["json"]["body"]
            return comment
        raise AssertionError((method, path))


class PRCommentTest(unittest.TestCase):
    def test_three_revisions_reuse_one_owned_comment(self):
        github = FakeGitHub()
        for index, char in enumerate("abc"):
            github.head = char * 40
            counts = {"PASS": index, "FAIL": 1, "UNKNOWN": 2, "NOT_APPLICABLE": 3}
            self.assertTrue(
                upsert_comment(
                    github,
                    3,
                    github.head,
                    counts,
                    "http://localhost:5173",
                    f"snapshot-{index}",
                )
            )
        self.assertEqual(len(github.comments), 1)
        self.assertEqual(github.permissions, {"pull_requests": "write"})
        self.assertEqual(
            github.comments[0]["body"],
            MARKER + "\nPassed: 2 | Failed: 1 | Unknown: 2 | N/A: 3\n"
            "[Assessment](http://localhost:5173/assessments/snapshot-2)",
        )

    def test_old_revision_cannot_publish_and_other_app_is_not_edited(self):
        github = FakeGitHub()
        github.comments.append(
            {"id": 9, "body": MARKER, "performed_via_github_app": {"id": 99}}
        )
        counts = dict.fromkeys(("PASS", "FAIL", "UNKNOWN", "NOT_APPLICABLE"), 0)
        self.assertFalse(
            upsert_comment(github, 3, "b" * 40, counts, "https://example.com", "x")
        )
        self.assertTrue(
            upsert_comment(github, 3, github.head, counts, "https://example.com", "x")
        )
        self.assertEqual(github.comments[0]["body"], MARKER)
        self.assertEqual(len(github.comments), 2)

    def test_rejects_bad_counts_and_untrusted_portal_url(self):
        counts = dict.fromkeys(("PASS", "FAIL", "UNKNOWN", "NOT_APPLICABLE"), 0)
        with self.assertRaises(ValueError):
            render_comment(counts, "http://example.com", "id")
        with self.assertRaises(ValueError):
            render_comment({**counts, "PASS": True}, "https://example.com", "id")

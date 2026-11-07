"""Publish an assessment summary as an owned, reusable GitHub PR comment."""

import re
from urllib.parse import quote, urlsplit

from app.git_source import SourceUnavailable

MARKER = "<!-- specbound-assessment -->"
STATUSES = (
    ("Passed", "PASS"),
    ("Failed", "FAIL"),
    ("Unknown", "UNKNOWN"),
    ("N/A", "NOT_APPLICABLE"),
)


def render_comment(counts, portal_url, snapshot_id):
    if not isinstance(counts, dict) or set(counts) != {key for _, key in STATUSES}:
        raise ValueError("Invalid assessment counts")
    if any(type(value) is not int or value < 0 for value in counts.values()):
        raise ValueError("Invalid assessment counts")
    if not isinstance(snapshot_id, str) or not re.fullmatch(
        r"[A-Za-z0-9_-]{1,100}", snapshot_id
    ):
        raise ValueError("Invalid assessment ID")
    parsed = urlsplit(portal_url)
    if (
        parsed.scheme not in ("http", "https")
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
        or not parsed.netloc
    ):
        raise ValueError("Invalid portal URL")
    if parsed.scheme == "http" and parsed.hostname not in (
        "localhost",
        "127.0.0.1",
        "::1",
    ):
        raise ValueError("Non-local portal URLs must use HTTPS")
    link = portal_url.rstrip("/") + "/assessments/" + quote(snapshot_id, safe="")
    return (
        MARKER
        + "\n"
        + " | ".join(f"{label}: {counts[key]}" for label, key in STATUSES)
        + f"\n[Assessment]({link})"
    )


def upsert_comment(source, number, head_sha, counts, portal_url, snapshot_id):
    """Update only this app's marked comment, provided the PR head still matches."""
    if (
        type(number) is not int
        or number <= 0
        or not re.fullmatch(r"(?:[0-9a-f]{40}|[0-9a-f]{64})", head_sha or "")
    ):
        raise ValueError("Invalid PR revision")
    body = render_comment(counts, portal_url, snapshot_id)
    token = source._token(permissions={"pull_requests": "write"})
    prefix = f"/repos/{source.repository}"
    pull = source._request("GET", f"{prefix}/pulls/{number}", token)
    if not isinstance(pull.get("head"), dict) or pull["head"].get("sha") != head_sha:
        return False
    matches = []
    for page in range(1, 101):
        comments = source._request(
            "GET",
            f"{prefix}/issues/{number}/comments",
            token,
            response_type=list,
            params={"per_page": 100, "page": page},
        )
        for comment in comments:
            if not isinstance(comment, dict):
                raise SourceUnavailable("Invalid GitHub comment")
            app = comment.get("performed_via_github_app")
            user = comment.get("user")
            is_own_bot = (
                isinstance(user, dict)
                and user.get("type") == "Bot"
                and isinstance(user.get("login"), str)
                and user["login"].lower() == source._installation_slug + "[bot]"
            )
            if (
                is_own_bot
                and (
                    app is None
                    or (isinstance(app, dict) and str(app.get("id")) == source.app_id)
                )
                and isinstance(comment.get("body"), str)
                and comment["body"].startswith(MARKER)
            ):
                if type(comment.get("id")) is not int or comment["id"] <= 0:
                    raise SourceUnavailable("Invalid GitHub comment ID")
                matches.append(comment["id"])
        if len(comments) < 100:
            break
    else:
        raise SourceUnavailable("Too many GitHub comments")
    if len(matches) > 1:
        raise SourceUnavailable("Multiple assessment comments already exist")
    if matches:
        source._request(
            "PATCH",
            f"{prefix}/issues/comments/{matches[0]}",
            token,
            json={"body": body},
        )
    else:
        source._request(
            "POST", f"{prefix}/issues/{number}/comments", token, json={"body": body}
        )
    return True

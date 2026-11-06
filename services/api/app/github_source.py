"""Read a GitHub repository through a scoped GitHub App installation."""

import base64
import binascii
import hashlib
import hmac
import os
import re
import time
from pathlib import Path
from urllib.parse import quote

import httpx
import jwt

from app.git_source import (
    GitSnapshot,
    InvalidGitReference,
    SourceNotFound,
    SourceUnavailable,
)

API = "https://api.github.com"
OBJECT_ID = re.compile(r"[0-9a-f]{40}")
REPOSITORY = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+")
MAX_FILES = 1000
MAX_BYTES = 20 * 1024 * 1024


def verify_github_signature(secret: bytes, payload: bytes, signature: str) -> bool:
    if (
        not secret
        or not isinstance(signature, str)
        or not re.fullmatch(r"sha256=[0-9a-f]{64}", signature)
    ):
        return False
    expected = "sha256=" + hmac.new(secret, payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


class GitHubSource:
    def __init__(
        self,
        repository: str,
        *,
        app_id: str,
        installation_id: int,
        private_key: bytes,
        webhook_secret: bytes = b"",
        client: httpx.Client | None = None,
    ):
        if (
            not isinstance(repository, str)
            or not REPOSITORY.fullmatch(repository)
            or any(part in (".", "..") for part in repository.split("/"))
            or not isinstance(app_id, str)
            or not app_id.isdecimal()
            or not isinstance(installation_id, int)
            or isinstance(installation_id, bool)
            or installation_id <= 0
            or not isinstance(private_key, bytes)
            or not private_key
        ):
            raise ValueError("GitHub App and repository configuration is invalid")
        self.repository = repository
        self.app_id = app_id
        self.installation_id = installation_id
        self.private_key = private_key
        self.webhook_secret = webhook_secret
        self._owns_client = client is None
        self.client = client or httpx.Client(timeout=15, follow_redirects=False)

    def close(self):
        if self._owns_client:
            self.client.close()

    def _request(self, method, path, token, **kwargs):
        try:
            response = self.client.request(
                method,
                API + path,
                headers={
                    "Authorization": "Bearer " + token,
                    "Accept": "application/vnd.github+json",
                    "X-GitHub-Api-Version": "2022-11-28",
                },
                follow_redirects=False,
                **kwargs,
            )
            if response.status_code == 404:
                raise SourceNotFound("GitHub source not found")
            if response.status_code < 200 or response.status_code >= 300:
                raise SourceUnavailable("GitHub API request failed")
            payload = response.json()
            if not isinstance(payload, dict):
                raise SourceUnavailable("Unexpected GitHub API response")
            return payload
        except (httpx.HTTPError, ValueError) as exc:
            raise SourceUnavailable(
                "GitHub API unavailable or returned invalid JSON"
            ) from exc

    def _token(self):
        now = int(time.time())
        try:
            app_token = jwt.encode(
                {"iat": now - 60, "exp": now + 540, "iss": self.app_id},
                self.private_key,
                algorithm="RS256",
            )
        except (ValueError, TypeError, jwt.PyJWTError) as exc:
            raise SourceUnavailable("GitHub App key is invalid") from exc
        installation = self._request(
            "GET", f"/repos/{self.repository}/installation", app_token
        )
        if installation.get("id") != self.installation_id:
            raise SourceUnavailable(
                "Repository is not part of the configured installation"
            )
        payload = self._request(
            "POST",
            f"/app/installations/{self.installation_id}/access_tokens",
            app_token,
            json={
                "repositories": [self.repository.split("/", 1)[1]],
                "permissions": {"contents": "read"},
            },
        )
        token = payload.get("token")
        if not isinstance(token, str) or not token:
            raise SourceUnavailable("GitHub installation token is missing")
        return token

    @staticmethod
    def _ref(ref):
        if not isinstance(ref, str) or not ref.strip() or len(ref) > 200 or "\0" in ref:
            raise InvalidGitReference("A nonempty Git reference is required")
        return quote(ref, safe="")

    @staticmethod
    def _sha(value):
        if not isinstance(value, str) or not OBJECT_ID.fullmatch(value):
            raise SourceUnavailable("GitHub returned an invalid object ID")
        return value

    def metadata(self):
        data = self._request("GET", f"/repos/{self.repository}", self._token())
        if (
            not isinstance(data.get("id"), int)
            or not isinstance(data.get("full_name"), str)
            or data["full_name"].lower() != self.repository.lower()
        ):
            raise SourceUnavailable("Unexpected GitHub repository metadata")
        return {
            key: data.get(key)
            for key in ("id", "full_name", "default_branch", "private")
        }

    def verify_webhook(self, headers, payload: bytes) -> bool:
        normalized = {str(key).lower(): value for key, value in headers.items()}
        return verify_github_signature(
            self.webhook_secret, payload, normalized.get("x-hub-signature-256", "")
        )

    def resolve_tag(self, tag: str) -> str:
        ref = self._ref(tag)
        token = self._token()
        obj = self._request(
            "GET", f"/repos/{self.repository}/git/ref/tags/{ref}", token
        ).get("object")
        for _ in range(8):
            if not isinstance(obj, dict):
                raise SourceUnavailable("Invalid GitHub tag object")
            sha = self._sha(obj.get("sha"))
            if obj.get("type") == "commit":
                return sha
            if obj.get("type") != "tag":
                raise SourceUnavailable("Tag does not resolve to a commit")
            obj = self._request(
                "GET", f"/repos/{self.repository}/git/tags/{sha}", token
            ).get("object")
        raise SourceUnavailable("Tag nesting exceeds the limit")

    def fetch(self, ref: str) -> GitSnapshot:
        ref = self._ref(ref)
        token = self._token()
        details = self._request("GET", f"/repos/{self.repository}/commits/{ref}", token)
        commit = self._sha(details.get("sha"))
        try:
            tree_sha = self._sha(details["commit"]["tree"]["sha"])
        except (KeyError, TypeError) as exc:
            raise SourceUnavailable("GitHub commit tree is missing") from exc
        tree = self._request(
            "GET", f"/repos/{self.repository}/git/trees/{tree_sha}?recursive=1", token
        )
        entries = tree.get("tree")
        if (
            tree.get("truncated") is not False
            or not isinstance(entries, list)
            or len(entries) > MAX_FILES
        ):
            raise SourceUnavailable("GitHub tree is incomplete or too large")
        files = {}
        total = 0
        for item in entries:
            if not isinstance(item, dict):
                raise SourceUnavailable("Invalid GitHub tree entry")
            if item.get("type") == "tree":
                continue
            if item.get("type") != "blob" or item.get("mode") not in (
                "100644",
                "100755",
            ):
                raise SourceUnavailable("Symlinks and submodules are unsupported")
            size = item.get("size")
            if (
                not isinstance(size, int)
                or size < 0
                or size > MAX_BYTES
                or total + size > MAX_BYTES
            ):
                raise SourceUnavailable("GitHub snapshot exceeds size limit")
            blob = self._request(
                "GET",
                f"/repos/{self.repository}/git/blobs/{self._sha(item.get('sha'))}",
                token,
            )
            try:
                if blob.get("encoding") != "base64" or not isinstance(
                    blob.get("content"), str
                ):
                    raise ValueError("invalid blob")
                content = base64.b64decode(
                    "".join(blob["content"].split()), validate=True
                )
                if len(content) != size:
                    raise ValueError("blob size mismatch")
                path = item["path"]
                if path in files:
                    raise ValueError("duplicate path")
                files[path] = content
                total += size
            except (KeyError, ValueError, TypeError, binascii.Error) as exc:
                raise SourceUnavailable("GitHub blob is invalid") from exc
        try:
            return GitSnapshot(commit, files)
        except ValueError as exc:
            raise SourceUnavailable("GitHub snapshot contains unsafe paths") from exc


def configured_github_source(repository: str) -> GitHubSource:
    try:
        app_id = os.environ["GITHUB_APP_ID"]
        installation_id = int(os.environ["GITHUB_INSTALLATION_ID"])
        key = Path(os.environ["GITHUB_APP_PRIVATE_KEY_FILE"]).read_bytes()
        secret = os.environ.get("GITHUB_WEBHOOK_SECRET", "").encode("utf-8")
        return GitHubSource(
            repository,
            app_id=app_id,
            installation_id=installation_id,
            private_key=key,
            webhook_secret=secret,
        )
    except (KeyError, ValueError, OSError) as exc:
        raise SourceUnavailable("GitHub App is not configured") from exc

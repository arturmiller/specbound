"""Read a GitHub repository through a scoped GitHub App installation."""

import asyncio
import base64
import binascii
import hashlib
import hmac
import os
import re
import time
from collections.abc import Mapping
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import quote

import httpx
import jwt

from app.git_source import (
    GitSnapshot,
    InvalidGitReference,
    SourceNotFound,
    SourceReadTimeout,
    SourceUnavailable,
)

API = "https://api.github.com"
OBJECT_ID = re.compile(r"[0-9a-f]{40}")
REPOSITORY = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+")
MAX_FILES = 1000
MAX_BYTES = 20 * 1024 * 1024
RESOURCE_READ_SECONDS = 30


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
        resource_client_factory=None,
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
        self._resource_client_factory = resource_client_factory or httpx.AsyncClient

    def close(self):
        if self._owns_client:
            self.client.close()

    def _request(self, method, path, token, *, response_type=dict, **kwargs):
        try:
            kwargs = self._bounded_request_options(kwargs)
            response = self._send_request(
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
            if not isinstance(payload, response_type):
                raise SourceUnavailable("Unexpected GitHub API response")
            return payload
        except httpx.TimeoutException as exc:
            if getattr(self, "_resource_deadline", None) is not None:
                raise SourceReadTimeout("Git resource read timed out") from exc
            raise SourceUnavailable("GitHub API unavailable") from exc
        except (httpx.HTTPError, ValueError) as exc:
            raise SourceUnavailable(
                "GitHub API unavailable or returned invalid JSON"
            ) from exc

    def _bounded_request_options(self, kwargs):
        deadline = getattr(self, "_resource_deadline", None)
        if deadline is not None:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise SourceReadTimeout("Git resource read timed out")
            kwargs["timeout"] = min(15, remaining)
        return kwargs

    def _send_request(self, method, url, **kwargs):
        runner = getattr(self, "_resource_runner", None)
        if runner is None:
            return self.client.request(method, url, **kwargs)

        async def read_response():
            # HTTPX's phase timeouts do not bound a trickling response. Cancelling
            # this async request interrupts I/O and closes its response stream.
            async with asyncio.timeout(self._resource_deadline - time.monotonic()):
                return await self._resource_client.request(method, url, **kwargs)

        try:
            return runner.run(read_response())
        except (TimeoutError, httpx.TimeoutException) as exc:
            raise SourceReadTimeout("Git resource read timed out") from exc

    def _token(self, *, permissions=None):
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
        if permissions and "pull_requests" in permissions:
            slug = installation.get("app_slug")
            if not isinstance(slug, str) or not re.fullmatch(r"[A-Za-z0-9-]+", slug):
                raise SourceUnavailable("GitHub App identity is missing")
            self._installation_slug = slug.lower()
        payload = self._request(
            "POST",
            f"/app/installations/{self.installation_id}/access_tokens",
            app_token,
            json={
                "repositories": [self.repository.split("/", 1)[1]],
                "permissions": permissions or {"contents": "read"},
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
        return self._fetch_snapshot(ref, lockfiles_only=False)

    def fetch_python_lockfiles(self, ref: str) -> GitSnapshot:
        """Read only lockfile blobs from a single immutable GitHub revision."""
        return self._fetch_snapshot(ref, lockfiles_only=True)

    def _read_tree(self, ref):
        ref = (
            "heads%2F" + self._ref(ref[6:])
            if isinstance(ref, str) and ref.startswith("heads/")
            else self._ref(ref)
        )
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
        return token, commit, entries

    def load_resource(self, ref, manifest_path, loader, *, ref_kind="branch"):
        """One pinned tree; materialize only files requested by the resource parser."""
        # The parsers remain synchronous; one loop/client spans all their lazy
        # reads so connections are reused and every request shares one deadline.
        with asyncio.Runner() as runner:
            return self._load_resource(runner, ref, manifest_path, loader, ref_kind)

    def _load_resource(self, runner, ref, manifest_path, loader, ref_kind):
        self._resource_deadline = time.monotonic() + RESOURCE_READ_SECONDS
        self._resource_runner = runner
        self._resource_client = None
        try:
            self._resource_client = self._resource_client_factory()
            if ref_kind not in ("branch", "tag", "commit"):
                raise InvalidGitReference("Unsupported Git ref kind")
            resolved = self.resolve_tag(ref) if ref_kind == "tag" else ref
            if ref_kind != "branch" and not re.fullmatch(
                r"(?:[0-9a-f]{40}|[0-9a-f]{64})", resolved
            ):
                raise InvalidGitReference("A full commit is required")
            token, commit, entries = self._read_tree(
                "heads/" + ref if ref_kind == "branch" else resolved
            )
            if ref_kind != "branch" and commit != resolved:
                raise SourceUnavailable("Snapshot did not match resolved commit")
            files = _ReferencedFiles(self, token, commit, entries)
            loaded = loader(SimpleNamespace(commit=commit, files=files), manifest_path)
            self._bounded_request_options({})
            return GitSnapshot(commit, files.loaded), loaded
        finally:
            try:
                if self._resource_client is not None:
                    runner.run(self._resource_client.aclose())
            finally:
                self._resource_client = None
                self._resource_runner = None
                self._resource_deadline = None

    def _fetch_snapshot(self, ref: str, *, lockfiles_only: bool) -> GitSnapshot:
        token, commit, entries = self._read_tree(ref)
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
            path = item.get("path")
            if not isinstance(path, str) or not path:
                raise SourceUnavailable("Invalid GitHub tree path")
            if lockfiles_only:
                name = path.rsplit("/", 1)[-1]
                if not (
                    name in {"uv.lock", "poetry.lock", "Pipfile.lock", "pdm.lock"}
                    or re.fullmatch(r"pylock(?:\.[^.]+)?\.toml", name)
                    or name.endswith(".py.uv.lock")
                ):
                    continue
            content = self._read_blob(item, token, total)
            if path in files:
                raise SourceUnavailable("Duplicate GitHub snapshot path")
            files[path] = content
            total += len(content)
        try:
            return GitSnapshot(commit, files)
        except ValueError as exc:
            raise SourceUnavailable("GitHub snapshot contains unsafe paths") from exc

    def _read_blob(self, item, token, total):
        if item.get("type") != "blob" or item.get("mode") not in ("100644", "100755"):
            raise SourceUnavailable("Symlinks and submodules are unsupported")
        size = item.get("size")
        if (
            type(size) is not int
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
            content = base64.b64decode("".join(blob["content"].split()), validate=True)
            if len(content) != size:
                raise ValueError("blob size mismatch")
            return content
        except (KeyError, ValueError, TypeError, binascii.Error) as exc:
            raise SourceUnavailable("GitHub blob is invalid") from exc


class _ReferencedFiles(Mapping):
    """Read-through files from a validated, immutable tree with a shared byte limit."""

    def __init__(self, source, token, commit, entries):
        self.source, self.token = source, token
        self.entries, self.loaded, self.total = {}, {}, 0
        for entry in entries:
            if not isinstance(entry, dict):
                raise SourceUnavailable("Invalid GitHub tree entry")
            if entry.get("type") == "tree":
                continue
            path = entry.get("path")
            try:
                GitSnapshot(commit, {path: b""})
            except (TypeError, ValueError) as exc:
                raise SourceUnavailable("GitHub tree contains unsafe paths") from exc
            if path in self.entries:
                raise SourceUnavailable("Duplicate GitHub tree path")
            self.entries[path] = entry

    def __getitem__(self, path):
        if path not in self.loaded:
            content = self.source._read_blob(self.entries[path], self.token, self.total)
            self.loaded[path] = content
            self.total += len(content)
        return self.loaded[path]

    def __contains__(self, path):
        return path in self.entries

    def __iter__(self):
        return iter(self.entries)

    def __len__(self):
        return len(self.entries)


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

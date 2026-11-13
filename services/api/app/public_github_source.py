"""Anonymous, read-only GitHub access for explicitly public repositories."""

import httpx

from app.git_source import SourceNotFound, SourceUnavailable
from app.github_source import API, REPOSITORY, GitHubSource


class PublicGitHubRateLimit(SourceUnavailable):
    """The unauthenticated GitHub API budget was exhausted."""


class PublicGitHubSource(GitHubSource):
    """An explicit unauthenticated source, never an auth-failure fallback."""

    def __init__(self, repository: str, *, client: httpx.Client | None = None):
        if (
            not isinstance(repository, str)
            or not REPOSITORY.fullmatch(repository)
            or any(part in (".", "..") for part in repository.split("/"))
        ):
            raise ValueError("Invalid GitHub repository")
        self.repository = repository
        self.webhook_secret = b""
        self._owns_client = client is None
        # No inherited proxy credentials, .netrc credentials or redirects.
        self.client = client or httpx.Client(
            timeout=15, follow_redirects=False, trust_env=False
        )

    def _token(self, *, permissions=None):
        if permissions is not None:
            raise SourceUnavailable("Public GitHub source is read-only")
        return None

    def _request(self, method, path, token, *, response_type=dict, **kwargs):
        if method != "GET" or token is not None:
            raise SourceUnavailable("Public GitHub source is read-only")
        try:
            response = self.client.request(
                "GET",
                API + path,
                headers={
                    "Accept": "application/vnd.github+json",
                    "X-GitHub-Api-Version": "2022-11-28",
                },
                follow_redirects=False,
                **kwargs,
            )
            if response.status_code == 429 or (
                response.status_code == 403
                and response.headers.get("x-ratelimit-remaining") == "0"
            ):
                raise PublicGitHubRateLimit("Public GitHub API rate limit exceeded")
            if response.status_code == 404:
                raise SourceNotFound("Public GitHub source not found")
            if response.status_code < 200 or response.status_code >= 300:
                raise SourceUnavailable("Public GitHub API request failed")
            payload = response.json()
            if not isinstance(payload, response_type):
                raise SourceUnavailable("Unexpected public GitHub API response")
            return payload
        except (httpx.HTTPError, ValueError) as exc:
            raise SourceUnavailable("Public GitHub API unavailable or invalid") from exc

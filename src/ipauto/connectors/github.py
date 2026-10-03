"""GitHub releases connector (docs/DESIGN.md 사건 감지·정규화, 단계 3 MVP).

Lists a public repository's releases via the unauthenticated GitHub REST
API, for the "오픈소스 공개" event (docs/DESIGN.md MVP 수직 슬라이스: "공개
GitHub 릴리스"). Polling, not a webhook — DESIGN.md allows either
("웹훅 또는 주기 폴링으로 수집한다").

``parse_releases`` is split out from ``fetch_releases`` so JSON-shape
parsing can be unit-tested without a real network call, same pattern as
``connectors/kipris.py``.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass

_API_BASE = "https://api.github.com"
_USER_AGENT = "ipauto-github-connector/0.1"
_ACCEPT_HEADER = "application/vnd.github+json"

MIN_PER_PAGE = 1
MAX_PER_PAGE = 100  # GitHub's documented upper bound for this endpoint.


class GitHubError(Exception):
    """Base class for all GitHub connector failures."""


class GitHubNotFoundError(GitHubError):
    """The repository does not exist or is private (HTTP 404)."""


class GitHubRateLimitError(GitHubError):
    """GitHub rate-limited this (unauthenticated) request (HTTP 403/429)."""


class GitHubNetworkError(GitHubError):
    """The request could not reach GitHub, or it timed out."""


@dataclass(frozen=True)
class GitHubRelease:
    release_id: int
    tag_name: str
    name: str
    html_url: str
    published_at: str | None
    body: str


def parse_releases(payload: list[dict]) -> list[GitHubRelease]:
    """Parse a raw releases-list JSON payload. Exposed for tests and offline replay."""
    return [
        GitHubRelease(
            release_id=item["id"],
            tag_name=item.get("tag_name") or "",
            name=item.get("name") or item.get("tag_name") or "",
            html_url=item.get("html_url") or "",
            published_at=item.get("published_at"),
            body=item.get("body") or "",
        )
        for item in payload
    ]


def fetch_releases(owner: str, repo: str, per_page: int = 30) -> list[GitHubRelease]:
    """List a public repo's releases, most recent first (GitHub's own order).

    Raises a typed GitHubError on any failure. An empty list means the call
    succeeded and the repo simply has no releases yet — never used to
    signal a failed call.
    """
    if not MIN_PER_PAGE <= per_page <= MAX_PER_PAGE:
        raise ValueError(f"per_page must be between {MIN_PER_PAGE} and {MAX_PER_PAGE}.")

    url = f"{_API_BASE}/repos/{owner}/{repo}/releases?per_page={per_page}"
    request = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT, "Accept": _ACCEPT_HEADER})

    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            body = response.read()
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            raise GitHubNotFoundError(f"Repository {owner}/{repo} not found or private (HTTP 404).") from exc
        if exc.code in (403, 429):
            raise GitHubRateLimitError("GitHub rate-limited this request (HTTP 403/429).") from exc
        raise GitHubError(f"GitHub returned HTTP {exc.code}.") from exc
    except TimeoutError as exc:
        raise GitHubNetworkError("GitHub request timed out.") from exc
    except urllib.error.URLError as exc:
        raise GitHubNetworkError(f"Could not connect to GitHub: {exc.reason}") from exc

    try:
        payload = json.loads(body)
    except json.JSONDecodeError as exc:
        raise GitHubError("GitHub response is not valid JSON.") from exc

    return parse_releases(payload)

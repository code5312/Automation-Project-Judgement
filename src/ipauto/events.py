"""Event normalization and ingestion (docs/DESIGN.md Event, 단계 3 MVP: 오픈소스 공개).

Normalizes a source-specific record (currently: one GitHub release) into
the shared Event shape and inserts it, deduped by (source, source_ref) per
docs/DESIGN.md ("출처별 고유 ID로 중복 수신을 막는다"). Other sources (Jira,
기획문서, 공개 일정) get their own ``event_from_...`` function here as they're
added; the normalized shape and the dedup/storage logic stay the same.
"""

from __future__ import annotations

import sqlite3

from ipauto.connectors.github import GitHubRelease, fetch_releases
from ipauto.db.repositories import EventInput, save_event

EVENT_TYPE_OPEN_SOURCE_RELEASE = "오픈소스 공개"
SOURCE_GITHUB = "GitHub"

_SUMMARY_BODY_EXCERPT_LENGTH = 200


def event_from_github_release(release: GitHubRelease) -> EventInput:
    summary = release.name or release.tag_name
    first_body_line = next((line.strip() for line in release.body.splitlines() if line.strip()), "")
    if first_body_line:
        summary = f"{summary} — {first_body_line[:_SUMMARY_BODY_EXCERPT_LENGTH]}"
    return EventInput(
        event_type=EVENT_TYPE_OPEN_SOURCE_RELEASE,
        source=SOURCE_GITHUB,
        source_ref=str(release.release_id),
        source_url=release.html_url or None,
        occurred_at=release.published_at,
        summary=summary,
    )


def ingest_github_releases(conn: sqlite3.Connection, owner: str, repo: str, per_page: int = 30) -> tuple[int, int]:
    """Fetch a public repo's releases and insert each as an Event. Returns (created, skipped)."""
    releases = fetch_releases(owner, repo, per_page=per_page)
    created = 0
    skipped = 0
    for release in releases:
        _event_id, was_created = save_event(conn, event_from_github_release(release))
        if was_created:
            created += 1
        else:
            skipped += 1
    return created, skipped

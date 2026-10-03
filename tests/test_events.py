"""Tests for Event normalization/ingestion (docs/PIPELINE.md 단계 3).

Records here are invented sample data, not a real repo's releases.
"""

from __future__ import annotations

import sqlite3

import pytest

from ipauto.connectors.github import GitHubRelease
from ipauto.db.connection import init_db
from ipauto.db.repositories import fetch_events
from ipauto.events import (
    EVENT_TYPE_OPEN_SOURCE_RELEASE,
    SOURCE_GITHUB,
    event_from_github_release,
    ingest_github_releases,
)

SAMPLE_RELEASE = GitHubRelease(
    release_id=900001,
    tag_name="v1.1.0-sample",
    name="SAMPLE v1.1.0",
    html_url="https://github.com/sample-owner/sample-repo/releases/tag/v1.1.0-sample",
    published_at="2026-02-01T00:00:00Z",
    body="SAMPLE 릴리스 노트 첫 줄\n\nSAMPLE 상세 설명",
)


@pytest.fixture
def conn():
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    init_db(connection)
    yield connection
    connection.close()


def test_event_from_github_release_normalizes_fields():
    data = event_from_github_release(SAMPLE_RELEASE)

    assert data.event_type == EVENT_TYPE_OPEN_SOURCE_RELEASE
    assert data.source == SOURCE_GITHUB
    assert data.source_ref == "900001"
    assert data.occurred_at == "2026-02-01T00:00:00Z"
    assert "SAMPLE v1.1.0" in data.summary
    assert "SAMPLE 릴리스 노트 첫 줄" in data.summary


def test_event_from_github_release_handles_empty_body():
    release = GitHubRelease(
        release_id=900000,
        tag_name="v1.0.0-sample",
        name="v1.0.0-sample",
        html_url="https://example.invalid",
        published_at=None,
        body="",
    )
    data = event_from_github_release(release)

    assert data.summary == "v1.0.0-sample"
    assert data.occurred_at is None


def test_ingest_github_releases_inserts_and_dedupes(conn, monkeypatch):
    import ipauto.events as events_module

    monkeypatch.setattr(events_module, "fetch_releases", lambda owner, repo, per_page=30: [SAMPLE_RELEASE])

    created, skipped = ingest_github_releases(conn, "sample-owner", "sample-repo")
    assert (created, skipped) == (1, 0)
    assert len(fetch_events(conn)) == 1

    created_again, skipped_again = ingest_github_releases(conn, "sample-owner", "sample-repo")
    assert (created_again, skipped_again) == (0, 1)
    assert len(fetch_events(conn)) == 1

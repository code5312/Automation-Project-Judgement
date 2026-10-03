"""Tests for GitHub release parsing (docs/PIPELINE.md 단계 3).

Fixtures under tests/fixtures/ mimic GitHub API response shapes but are
entirely invented (filenames/values contain "sample"), not a real repo.
"""

from __future__ import annotations

import json
from pathlib import Path

from ipauto.connectors.github import parse_releases

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


def _load(name: str) -> list[dict]:
    return json.loads((FIXTURES_DIR / name).read_text(encoding="utf-8"))


def test_parse_releases_extracts_fields():
    releases = parse_releases(_load("sample_github_releases.json"))

    assert len(releases) == 2
    first = releases[0]
    assert first.release_id == 900001
    assert first.tag_name == "v1.1.0-sample"
    assert first.name == "SAMPLE v1.1.0"
    assert first.published_at == "2026-02-01T00:00:00Z"


def test_parse_releases_falls_back_to_tag_name_when_name_missing():
    releases = parse_releases(_load("sample_github_releases.json"))

    second = releases[1]
    assert second.name == "v1.0.0-sample"
    assert second.body == ""


def test_parse_releases_empty_list_is_not_an_error():
    assert parse_releases([]) == []

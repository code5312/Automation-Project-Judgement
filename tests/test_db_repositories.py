"""Tests for the SQLite schema and append-only repository functions."""

from __future__ import annotations

import sqlite3

import pytest

from ipauto.db.connection import init_db
from ipauto.db.repositories import (
    JudgmentInput,
    PremiseInput,
    count_judgments,
    fetch_judgments_for_application,
    fetch_latest_judgment,
    fetch_premises_for_judgment,
    find_migrated_judgment,
)
from ipauto.db.repositories import save_judgment as insert_judgment


@pytest.fixture
def conn():
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    init_db(connection)
    yield connection
    connection.close()


def _sample_input(**overrides) -> JudgmentInput:
    defaults = dict(
        application_number="SAMPLE-0000001",
        review_technology="샘플 기술",
        decision="유지",
        reason="샘플 이유",
        assignee="샘플 담당자",
        review_deadline="2026-12-31",
        premises=[PremiseInput(source="샘플 출처", check_key="등록상태", expected_value="공개(샘플)")],
    )
    defaults.update(overrides)
    return JudgmentInput(**defaults)


def test_save_judgment_persists_judgment_and_premises(conn):
    judgment_id = insert_judgment(conn, _sample_input())

    row = conn.execute("SELECT * FROM judgment WHERE id = ?", (judgment_id,)).fetchone()
    assert row["application_number"] == "SAMPLE-0000001"
    assert row["decision"] == "유지"

    premises = fetch_premises_for_judgment(conn, judgment_id)
    assert len(premises) == 1
    assert premises[0]["check_key"] == "등록상태"


def test_judgment_rejects_blank_reason(conn):
    with pytest.raises(sqlite3.IntegrityError):
        insert_judgment(conn, _sample_input(reason="   "))


def test_judgment_rejects_invalid_decision(conn):
    with pytest.raises(sqlite3.IntegrityError):
        insert_judgment(conn, _sample_input(decision="알 수 없는 결정"))


def test_fetch_latest_judgment_returns_most_recent_for_key(conn):
    first_id = insert_judgment(conn, _sample_input(created_at="2026-01-01T00:00:00Z"))
    second_id = insert_judgment(
        conn,
        _sample_input(
            decision="정리 검토",
            previous_judgment_id=first_id,
            created_at="2026-02-01T00:00:00Z",
        ),
    )

    latest = fetch_latest_judgment(conn, "SAMPLE-0000001", "샘플 기술")
    assert latest["id"] == second_id
    assert latest["previous_judgment_id"] == first_id


def test_fetch_judgments_for_application_orders_most_recent_first(conn):
    insert_judgment(conn, _sample_input(created_at="2026-01-01T00:00:00Z"))
    insert_judgment(conn, _sample_input(created_at="2026-03-01T00:00:00Z"))

    rows = fetch_judgments_for_application(conn, "SAMPLE-0000001")
    assert [row["created_at"] for row in rows] == ["2026-03-01T00:00:00Z", "2026-01-01T00:00:00Z"]


def test_count_judgments_filters_by_migrated_flag(conn):
    insert_judgment(conn, _sample_input())
    insert_judgment(conn, _sample_input(migrated_from_json=True, created_at="2026-01-01T00:00:00Z"))

    assert count_judgments(conn) == 2
    assert count_judgments(conn, migrated_from_json=True) == 1
    assert count_judgments(conn, migrated_from_json=False) == 1


def test_find_migrated_judgment_matches_on_app_number_and_created_at(conn):
    insert_judgment(conn, _sample_input(migrated_from_json=True, created_at="2026-01-01T00:00:00Z"))

    found = find_migrated_judgment(conn, "SAMPLE-0000001", "2026-01-01T00:00:00Z")
    assert found is not None
    assert find_migrated_judgment(conn, "SAMPLE-0000001", "2099-01-01T00:00:00Z") is None

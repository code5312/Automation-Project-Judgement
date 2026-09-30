"""Tests for Gate B validation and append-only judgment saving."""

from __future__ import annotations

import sqlite3

import pytest

from ipauto.db.connection import init_db
from ipauto.judgments.service import (
    DuplicateJudgmentError,
    JudgmentValidationError,
    fetch_latest_judgment,
    history_for_application,
    premises_for_judgment,
    save_gate_b_judgment,
)

VALID_PREMISES = [("KIPRIS 재조회", "등록상태", "공개(샘플)")]


@pytest.fixture
def conn():
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    init_db(connection)
    yield connection
    connection.close()


def _save(conn, **overrides):
    kwargs = dict(
        application_number="SAMPLE-0000001",
        review_technology="샘플 기술",
        decision="유지",
        reason="샘플 이유",
        premises=VALID_PREMISES,
        assignee="샘플 담당자",
        review_deadline="2026-12-31",
    )
    kwargs.update(overrides)
    return save_gate_b_judgment(conn, **kwargs)


def test_save_rejects_blank_reason(conn):
    with pytest.raises(JudgmentValidationError):
        _save(conn, reason="   ")


def test_save_rejects_missing_premises(conn):
    with pytest.raises(JudgmentValidationError):
        _save(conn, premises=[("출처", "확인 키", "   ")])


def test_save_rejects_missing_assignee(conn):
    with pytest.raises(JudgmentValidationError):
        _save(conn, assignee="  ")


def test_save_rejects_invalid_decision(conn):
    with pytest.raises(JudgmentValidationError):
        _save(conn, decision="알 수 없는 결정")


def test_save_succeeds_with_valid_input(conn):
    judgment_id = _save(conn)
    premises = premises_for_judgment(conn, judgment_id)
    assert len(premises) == 1
    assert premises[0]["check_key"] == "등록상태"


def test_resubmitting_identical_judgment_is_rejected_as_duplicate(conn):
    _save(conn)
    with pytest.raises(DuplicateJudgmentError):
        _save(conn)


def test_rejudgment_with_different_content_chains_previous_judgment(conn):
    first_id = _save(conn)
    second_id = _save(conn, decision="정리 검토", reason="새로운 이유")

    latest = fetch_latest_judgment(conn, "SAMPLE-0000001", "샘플 기술")
    assert latest["id"] == second_id
    assert latest["previous_judgment_id"] == first_id


def test_history_for_application_lists_all_judgments(conn):
    _save(conn)
    _save(conn, decision="정리 검토", reason="새로운 이유")

    history = history_for_application(conn, "SAMPLE-0000001")
    assert len(history) == 2

"""Tests for Gate B validation and append-only judgment saving."""

from __future__ import annotations

import sqlite3

import pytest

from ipauto.db.connection import init_db
from ipauto.db.repositories import EventInput, IpAssetInput
from ipauto.db.repositories import save_event as insert_event
from ipauto.db.repositories import save_ip_asset as insert_ip_asset
from ipauto.judgments.service import (
    DuplicateJudgmentError,
    JudgmentValidationError,
    default_premises_from_ip_asset,
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


def test_save_carries_event_id_and_model_prompt_version_onto_the_row(conn):
    event_id, _ = insert_event(
        conn, EventInput(event_type="오픈소스 공개", source="GitHub", source_ref="SAMPLE-1", summary="샘플 사건")
    )

    judgment_id = _save(conn, event_id=event_id, model_version="sample-model", prompt_version="sample-prompt-v1")

    row = conn.execute("SELECT * FROM judgment WHERE id = ?", (judgment_id,)).fetchone()
    assert row["event_id"] == event_id
    assert row["model_version"] == "sample-model"
    assert row["prompt_version"] == "sample-prompt-v1"


def test_save_without_event_id_leaves_it_null(conn):
    judgment_id = _save(conn)

    row = conn.execute("SELECT event_id FROM judgment WHERE id = ?", (judgment_id,)).fetchone()
    assert row["event_id"] is None


def test_default_premises_from_ip_asset_maps_legal_status_applicant_ipc(conn):
    asset_id = insert_ip_asset(
        conn,
        IpAssetInput(
            application_number="SAMPLE-ASSET-0000001",
            asset_kind="자사",
            applicant="샘플 주식회사",
            ipc_codes="H01M 10/613",
            legal_status="공개(샘플)",
        ),
    )
    asset_row = conn.execute("SELECT * FROM ip_asset WHERE id = ?", (asset_id,)).fetchone()

    premises = default_premises_from_ip_asset(asset_row)

    assert premises == [
        ("KIPRIS 재조회", "등록상태", "공개(샘플)"),
        ("KIPRIS 재조회", "출원인", "샘플 주식회사"),
        ("KIPRIS 재조회", "IPC", "H01M 10/613"),
    ]


def test_default_premises_from_ip_asset_handles_missing_fields(conn):
    asset_id = insert_ip_asset(conn, IpAssetInput(application_number="SAMPLE-ASSET-0000002", asset_kind="자사"))
    asset_row = conn.execute("SELECT * FROM ip_asset WHERE id = ?", (asset_id,)).fetchone()

    premises = default_premises_from_ip_asset(asset_row)

    assert all(expected_value == "" for _source, _check_key, expected_value in premises)

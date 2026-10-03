"""Tests for the SQLite schema and append-only repository functions."""

from __future__ import annotations

import sqlite3

import pytest

from ipauto.db.connection import init_db
from ipauto.db.repositories import (
    ASSET_KIND_EXTERNAL,
    ASSET_KIND_OWN,
    AUDIT_STATUS_CONFIRMED,
    AUDIT_STATUS_MISSED,
    EVENT_STATUS_TRIAGED,
    LINK_BASIS_IPC_MATCH,
    LINK_OBJECT_EVENT,
    LINK_OBJECT_IP_ASSET,
    AutoCloseLogInput,
    EventInput,
    IpAssetInput,
    JudgmentInput,
    LinkInput,
    PremiseInput,
    auto_close_miss_rate,
    confirm_link,
    count_judgments,
    fetch_audit_queue,
    fetch_auto_close_log_for_pair,
    fetch_auto_close_logs,
    fetch_event_by_source_ref,
    fetch_events,
    fetch_ip_asset,
    fetch_ip_asset_by_id,
    fetch_ip_assets,
    fetch_judgments_for_application,
    fetch_latest_judgment,
    fetch_links_from,
    fetch_links_to,
    fetch_premises_for_judgment,
    find_link,
    find_migrated_judgment,
    record_audit_result,
    select_audit_sample,
)
from ipauto.db.repositories import log_auto_close as insert_auto_close_log
from ipauto.db.repositories import save_event as insert_event
from ipauto.db.repositories import save_ip_asset as insert_ip_asset
from ipauto.db.repositories import save_judgment as insert_judgment
from ipauto.db.repositories import save_link as insert_link


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


def _sample_ip_asset(**overrides) -> IpAssetInput:
    defaults = dict(
        application_number="SAMPLE-ASSET-0000001",
        asset_kind=ASSET_KIND_OWN,
        title="샘플 배터리 팩",
        applicant="샘플 주식회사",
        ipc_codes="H01M 10/613",
        legal_status="공개(샘플)",
    )
    defaults.update(overrides)
    return IpAssetInput(**defaults)


def test_save_ip_asset_inserts_new_row(conn):
    asset_id = insert_ip_asset(conn, _sample_ip_asset())

    row = fetch_ip_asset(conn, "SAMPLE-ASSET-0000001")
    assert row["id"] == asset_id
    assert row["asset_kind"] == ASSET_KIND_OWN
    assert row["title"] == "샘플 배터리 팩"
    assert fetch_ip_asset_by_id(conn, asset_id)["application_number"] == "SAMPLE-ASSET-0000001"
    assert fetch_ip_asset_by_id(conn, 999999) is None


def test_save_ip_asset_upserts_same_application_number(conn):
    first_id = insert_ip_asset(conn, _sample_ip_asset())
    second_id = insert_ip_asset(conn, _sample_ip_asset(title="갱신된 제목", legal_status="등록(샘플)"))

    assert first_id == second_id
    row = fetch_ip_asset(conn, "SAMPLE-ASSET-0000001")
    assert row["title"] == "갱신된 제목"
    assert row["legal_status"] == "등록(샘플)"
    assert conn.execute("SELECT COUNT(*) AS n FROM ip_asset").fetchone()["n"] == 1


def test_save_ip_asset_rejects_invalid_asset_kind(conn):
    with pytest.raises(sqlite3.IntegrityError):
        insert_ip_asset(conn, _sample_ip_asset(asset_kind="알 수 없음"))


def test_fetch_ip_assets_filters_by_kind(conn):
    insert_ip_asset(conn, _sample_ip_asset())
    insert_ip_asset(conn, _sample_ip_asset(application_number="SAMPLE-ASSET-0000002", asset_kind=ASSET_KIND_EXTERNAL))

    assert len(fetch_ip_assets(conn)) == 2
    assert [row["application_number"] for row in fetch_ip_assets(conn, asset_kind=ASSET_KIND_OWN)] == [
        "SAMPLE-ASSET-0000001"
    ]


def _sample_event(**overrides) -> EventInput:
    defaults = dict(
        event_type="오픈소스 공개",
        source="GitHub",
        source_ref="SAMPLE-RELEASE-1",
        source_url="https://example.invalid/sample",
        summary="샘플 릴리스",
    )
    defaults.update(overrides)
    return EventInput(**defaults)


def test_save_event_inserts_new_row_and_sets_detected_at(conn):
    event_id, was_created = insert_event(conn, _sample_event())

    assert was_created is True
    row = fetch_event_by_source_ref(conn, "GitHub", "SAMPLE-RELEASE-1")
    assert row["id"] == event_id
    assert row["status"] == "신규"
    assert row["detected_at"]  # auto-filled, not blank


def test_save_event_is_deduped_by_source_and_source_ref(conn):
    first_id, first_created = insert_event(conn, _sample_event())
    second_id, second_created = insert_event(conn, _sample_event(summary="다른 요약이어도 중복으로 처리"))

    assert first_created is True
    assert second_created is False
    assert first_id == second_id
    assert conn.execute("SELECT COUNT(*) AS n FROM event").fetchone()["n"] == 1


def test_save_event_rejects_invalid_status(conn):
    with pytest.raises(sqlite3.IntegrityError):
        insert_event(conn, _sample_event(status="알 수 없음"))


def test_fetch_events_filters_by_status(conn):
    insert_event(conn, _sample_event())
    insert_event(conn, _sample_event(source_ref="SAMPLE-RELEASE-2", status=EVENT_STATUS_TRIAGED))

    assert len(fetch_events(conn)) == 2
    assert [row["source_ref"] for row in fetch_events(conn, status=EVENT_STATUS_TRIAGED)] == ["SAMPLE-RELEASE-2"]


def _sample_link(**overrides) -> LinkInput:
    defaults = dict(
        from_type=LINK_OBJECT_EVENT,
        from_id=1,
        to_type=LINK_OBJECT_IP_ASSET,
        to_id=1,
        basis=LINK_BASIS_IPC_MATCH,
        confidence_band="검토 우선순위 높음",
    )
    defaults.update(overrides)
    return LinkInput(**defaults)


def test_save_link_inserts_row_not_confirmed_by_default(conn):
    link_id = insert_link(conn, _sample_link())

    row = conn.execute("SELECT * FROM link WHERE id = ?", (link_id,)).fetchone()
    assert row["basis"] == LINK_BASIS_IPC_MATCH
    assert row["confirmed_by_human"] == 0


def test_save_link_allows_multiple_rows_for_same_pair(conn):
    # save_link itself doesn't dedupe; callers (ipauto.linking) are
    # responsible for calling find_link first if they need idempotency.
    insert_link(conn, _sample_link())
    insert_link(conn, _sample_link())

    assert len(fetch_links_from(conn, LINK_OBJECT_EVENT, 1)) == 2


def test_find_link_locates_existing_pair(conn):
    insert_link(conn, _sample_link())

    assert find_link(conn, LINK_OBJECT_EVENT, 1, LINK_OBJECT_IP_ASSET, 1) is not None
    assert find_link(conn, LINK_OBJECT_EVENT, 1, LINK_OBJECT_IP_ASSET, 999) is None


def test_fetch_links_from_and_to(conn):
    insert_link(conn, _sample_link())
    insert_link(conn, _sample_link(to_id=2))

    assert len(fetch_links_from(conn, LINK_OBJECT_EVENT, 1)) == 2
    assert len(fetch_links_to(conn, LINK_OBJECT_IP_ASSET, 2)) == 1
    assert len(fetch_links_to(conn, LINK_OBJECT_IP_ASSET, 999)) == 0


def test_confirm_link_sets_flag(conn):
    link_id = insert_link(conn, _sample_link())

    confirm_link(conn, link_id)

    row = conn.execute("SELECT confirmed_by_human FROM link WHERE id = ?", (link_id,)).fetchone()
    assert row["confirmed_by_human"] == 1


def test_confirm_link_rejects_unknown_id(conn):
    with pytest.raises(ValueError):
        confirm_link(conn, 999999)


def _seed_event_and_asset(conn, source_ref: str = "SAMPLE-RELEASE-1", application_number: str = "SAMPLE-ASSET-0000001"):
    event_id, _ = insert_event(conn, _sample_event(source_ref=source_ref))
    asset_id = insert_ip_asset(conn, _sample_ip_asset(application_number=application_number))
    return event_id, asset_id


def test_log_auto_close_inserts_new_row(conn):
    event_id, asset_id = _seed_event_and_asset(conn)

    log_id, created = insert_auto_close_log(
        conn,
        AutoCloseLogInput(event_id=event_id, ip_asset_id=asset_id, keyword_priority="검토 우선순위 낮음"),
    )

    assert created is True
    row = fetch_auto_close_log_for_pair(conn, event_id, asset_id)
    assert row["id"] == log_id
    assert row["audit_status"] == "대기"
    assert row["sampled_for_audit"] == 0


def test_log_auto_close_is_deduped_by_event_and_asset(conn):
    event_id, asset_id = _seed_event_and_asset(conn)
    data = AutoCloseLogInput(event_id=event_id, ip_asset_id=asset_id, keyword_priority="검토 우선순위 낮음")

    first_id, first_created = insert_auto_close_log(conn, data)
    second_id, second_created = insert_auto_close_log(conn, data)

    assert first_created is True
    assert second_created is False
    assert first_id == second_id
    assert conn.execute("SELECT COUNT(*) AS n FROM auto_close_log").fetchone()["n"] == 1


def test_fetch_auto_close_logs_filters_by_audit_status(conn):
    event_id, asset_id = _seed_event_and_asset(conn)
    log_id, _ = insert_auto_close_log(
        conn, AutoCloseLogInput(event_id=event_id, ip_asset_id=asset_id, keyword_priority="검토 우선순위 낮음")
    )
    record_audit_result(conn, log_id, AUDIT_STATUS_CONFIRMED)

    assert len(fetch_auto_close_logs(conn)) == 1
    assert len(fetch_auto_close_logs(conn, audit_status=AUDIT_STATUS_CONFIRMED)) == 1
    assert len(fetch_auto_close_logs(conn, audit_status="대기")) == 0


def test_select_audit_sample_marks_rows_sampled_and_does_not_resample(conn):
    event_id, asset_a = _seed_event_and_asset(conn, application_number="SAMPLE-ASSET-0000001")
    _, asset_b = _seed_event_and_asset(conn, source_ref="SAMPLE-RELEASE-2", application_number="SAMPLE-ASSET-0000002")
    insert_auto_close_log(
        conn, AutoCloseLogInput(event_id=event_id, ip_asset_id=asset_a, keyword_priority="검토 우선순위 낮음")
    )
    insert_auto_close_log(
        conn, AutoCloseLogInput(event_id=event_id, ip_asset_id=asset_b, keyword_priority="검토 우선순위 낮음")
    )

    first_sample = select_audit_sample(conn, sample_size=10)
    assert len(first_sample) == 2
    assert all(row["sampled_for_audit"] == 1 for row in first_sample)

    second_sample = select_audit_sample(conn, sample_size=10)
    assert second_sample == []  # nothing left un-sampled


def test_fetch_audit_queue_only_returns_pending_sampled_rows(conn):
    event_id, asset_id = _seed_event_and_asset(conn)
    log_id, _ = insert_auto_close_log(
        conn, AutoCloseLogInput(event_id=event_id, ip_asset_id=asset_id, keyword_priority="검토 우선순위 낮음")
    )

    assert fetch_audit_queue(conn) == []  # not sampled yet

    select_audit_sample(conn, sample_size=10)
    assert len(fetch_audit_queue(conn)) == 1

    record_audit_result(conn, log_id, AUDIT_STATUS_CONFIRMED)
    assert fetch_audit_queue(conn) == []  # resolved, no longer pending


def test_record_audit_result_rejects_unknown_id(conn):
    with pytest.raises(ValueError):
        record_audit_result(conn, 999999, AUDIT_STATUS_CONFIRMED)


def test_auto_close_miss_rate_is_none_before_any_audit(conn):
    event_id, asset_id = _seed_event_and_asset(conn)
    insert_auto_close_log(
        conn, AutoCloseLogInput(event_id=event_id, ip_asset_id=asset_id, keyword_priority="검토 우선순위 낮음")
    )

    assert auto_close_miss_rate(conn) is None


def test_auto_close_miss_rate_counts_only_audited_rows(conn):
    event_id, asset_a = _seed_event_and_asset(conn, application_number="SAMPLE-ASSET-0000001")
    _, asset_b = _seed_event_and_asset(conn, source_ref="SAMPLE-RELEASE-2", application_number="SAMPLE-ASSET-0000002")
    _, asset_c = _seed_event_and_asset(conn, source_ref="SAMPLE-RELEASE-3", application_number="SAMPLE-ASSET-0000003")
    log_a, _ = insert_auto_close_log(
        conn, AutoCloseLogInput(event_id=event_id, ip_asset_id=asset_a, keyword_priority="검토 우선순위 낮음")
    )
    log_b, _ = insert_auto_close_log(
        conn, AutoCloseLogInput(event_id=event_id, ip_asset_id=asset_b, keyword_priority="검토 우선순위 낮음")
    )
    insert_auto_close_log(  # left un-audited (대기) — must not count in the denominator
        conn, AutoCloseLogInput(event_id=event_id, ip_asset_id=asset_c, keyword_priority="검토 우선순위 낮음")
    )
    record_audit_result(conn, log_a, AUDIT_STATUS_CONFIRMED)
    record_audit_result(conn, log_b, AUDIT_STATUS_MISSED)

    assert auto_close_miss_rate(conn) == 0.5

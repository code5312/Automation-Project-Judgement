"""Tests for the 자동 종결 표본 감사 Streamlit page (docs/PIPELINE.md 단계 3).

Uses Streamlit's AppTest to actually run the page script and simulate
button clicks — this is what caught the real cross-thread SQLite bug fixed
alongside this feature (see tests/test_db_connection.py). Records here are
invented sample data, not real events or patents.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

from ipauto.db.connection import connect, init_db
from ipauto.db.repositories import AutoCloseLogInput, EventInput, IpAssetInput
from ipauto.db.repositories import log_auto_close as insert_auto_close_log
from ipauto.db.repositories import save_event as insert_event
from ipauto.db.repositories import save_ip_asset as insert_ip_asset

PAGE_PATH = Path(__file__).resolve().parents[1] / "app" / "pages" / "sample_audit.py"


@pytest.fixture
def db_path(tmp_path, monkeypatch):
    # st.cache_resource is a process-wide cache that otherwise survives
    # across AppTest instances within the same pytest run, so without
    # clearing it a later test would silently reuse an earlier test's
    # cached connection (and its database path) instead of its own.
    st.cache_resource.clear()
    path = tmp_path / "sample_audit_test.db"
    monkeypatch.setenv("IPAUTO_DB_PATH", str(path))
    return path


def _seed_two_auto_closed_pairs(path):
    conn = connect(path)
    init_db(conn)
    event_id, _ = insert_event(
        conn, EventInput(event_type="오픈소스 공개", source="GitHub", source_ref="SAMPLE-1", summary="샘플 사건")
    )
    asset_a = insert_ip_asset(
        conn, IpAssetInput(application_number="SAMPLE-ASSET-A", asset_kind="자사", title="샘플 자산 A")
    )
    asset_b = insert_ip_asset(
        conn, IpAssetInput(application_number="SAMPLE-ASSET-B", asset_kind="자사", title="샘플 자산 B")
    )
    insert_auto_close_log(
        conn, AutoCloseLogInput(event_id=event_id, ip_asset_id=asset_a, keyword_priority="검토 우선순위 낮음")
    )
    insert_auto_close_log(
        conn, AutoCloseLogInput(event_id=event_id, ip_asset_id=asset_b, keyword_priority="검토 우선순위 낮음")
    )
    conn.close()


def test_page_renders_with_no_data(db_path):
    assert os.environ["IPAUTO_DB_PATH"] == str(db_path)
    at = AppTest.from_file(PAGE_PATH)
    at.run()

    assert not at.exception
    assert "감사 대기 중인 표본이 없습니다" in at.info[0].value


def test_drawing_a_sample_populates_the_audit_queue(db_path):
    _seed_two_auto_closed_pairs(db_path)

    at = AppTest.from_file(PAGE_PATH)
    at.run()
    at.number_input[0].set_value(5)
    at.button[0].click()
    at.run()

    assert not at.exception
    # 1 "draw sample" button + 2 x (confirm, missed) for the two queued pairs
    assert len(at.button) == 5


def test_confirming_and_missing_updates_queue_and_miss_rate(db_path):
    _seed_two_auto_closed_pairs(db_path)

    at = AppTest.from_file(PAGE_PATH)
    at.run()
    at.number_input[0].set_value(5)
    at.button[0].click()
    at.run()

    confirm_buttons = [b for b in at.button if b.key and b.key.startswith("confirm_")]
    missed_buttons = [b for b in at.button if b.key and b.key.startswith("missed_")]
    assert len(confirm_buttons) == 2
    assert len(missed_buttons) == 2

    confirm_buttons[0].click()
    at.run()
    assert not at.exception

    remaining_missed = [b for b in at.button if b.key and b.key.startswith("missed_")]
    remaining_missed[0].click()
    at.run()
    assert not at.exception

    # both pairs resolved: queue empty, miss rate is 1 of 2 = 50%
    assert "감사 대기 중인 표본이 없습니다" in at.info[0].value
    assert any("50.0%" in m.value for m in at.metric)

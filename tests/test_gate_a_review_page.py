"""Tests for the 게이트 A (애매한 사건 확인) Streamlit page (docs/PIPELINE.md 단계 3).

Uses Streamlit's AppTest to actually run the page script and simulate
button clicks. Records here are invented sample data, not real events or
patents.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

from ipauto.db.connection import connect, init_db
from ipauto.db.repositories import EventInput, GateAQueueInput, IpAssetInput
from ipauto.db.repositories import enqueue_gate_a as insert_gate_a
from ipauto.db.repositories import save_event as insert_event
from ipauto.db.repositories import save_ip_asset as insert_ip_asset

PAGE_PATH = Path(__file__).resolve().parents[1] / "app" / "pages" / "gate_a_review.py"
# This page now also builds a judgment card per queued pair, which imports
# ipauto.scoring.keywords — its module-level kiwipiepy model load is slow
# on first import, easily exceeding AppTest's default 3s run timeout.
RUN_TIMEOUT = 30


@pytest.fixture
def db_path(tmp_path, monkeypatch):
    # st.cache_resource is a process-wide cache that otherwise survives
    # across AppTest instances within the same pytest run (see
    # tests/test_sample_audit_page.py), so it must be cleared per test.
    st.cache_resource.clear()
    path = tmp_path / "gate_a_test.db"
    monkeypatch.setenv("IPAUTO_DB_PATH", str(path))
    return path


def _seed_two_queued_pairs(path):
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
    insert_gate_a(
        conn,
        GateAQueueInput(
            event_id=event_id, ip_asset_id=asset_a, keyword_priority="검토 우선순위 보통", reasons=["확신도 중간대"]
        ),
    )
    insert_gate_a(
        conn,
        GateAQueueInput(
            event_id=event_id, ip_asset_id=asset_b, keyword_priority="검토 우선순위 보통", reasons=["신호 불일치"]
        ),
    )
    conn.close()


def test_page_renders_with_no_data(db_path):
    assert os.environ["IPAUTO_DB_PATH"] == str(db_path)
    at = AppTest.from_file(PAGE_PATH, default_timeout=RUN_TIMEOUT)
    at.run()

    assert not at.exception
    assert "게이트 A 대기열이 비어 있습니다" in at.info[0].value


def test_queued_pairs_render_with_reasons_and_buttons(db_path):
    _seed_two_queued_pairs(db_path)

    at = AppTest.from_file(PAGE_PATH, default_timeout=RUN_TIMEOUT)
    at.run()

    assert not at.exception
    assert len(at.button) == 4  # 2 pairs x (관련 확정, 무관 확정)
    warning_texts = [w.value for w in at.warning]
    assert "확신도 중간대" in warning_texts
    assert "신호 불일치" in warning_texts


def test_confirming_related_and_unrelated_resolves_queue(db_path):
    _seed_two_queued_pairs(db_path)

    at = AppTest.from_file(PAGE_PATH, default_timeout=RUN_TIMEOUT)
    at.run()

    related_buttons = [b for b in at.button if b.key and b.key.startswith("related_")]
    unrelated_buttons = [b for b in at.button if b.key and b.key.startswith("unrelated_")]
    assert len(related_buttons) == 2
    assert len(unrelated_buttons) == 2

    related_buttons[0].click()
    at.run()
    assert not at.exception

    remaining_unrelated = [b for b in at.button if b.key and b.key.startswith("unrelated_")]
    remaining_unrelated[0].click()
    at.run()
    assert not at.exception

    assert "게이트 A 대기열이 비어 있습니다" in at.info[0].value

"""Tests for Event-to-IPAsset link proposals (docs/PIPELINE.md 단계 3).

Records here are invented sample data, not real patents or real events.
"""

from __future__ import annotations

import sqlite3

import pytest

from ipauto.db.connection import init_db
from ipauto.db.repositories import (
    ASSET_KIND_EXTERNAL,
    ASSET_KIND_OWN,
    LINK_BASIS_IPC_MATCH,
    LINK_BASIS_KEYWORD,
    LINK_OBJECT_EVENT,
    LINK_OBJECT_IP_ASSET,
    IpAssetInput,
    fetch_links_from,
)
from ipauto.db.repositories import save_ip_asset as insert_ip_asset
from ipauto.linking import link_event_to_ip_assets


@pytest.fixture
def conn():
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    init_db(connection)
    yield connection
    connection.close()


def _sample_asset(**overrides) -> IpAssetInput:
    defaults = dict(
        application_number="SAMPLE-ASSET-0000001",
        asset_kind=ASSET_KIND_OWN,
        title="샘플 전기차 배터리 냉각 장치",
        ipc_codes="H01M 10/613",
    )
    defaults.update(overrides)
    return IpAssetInput(**defaults)


def test_link_event_to_ip_assets_creates_link_for_relevant_asset(conn):
    insert_ip_asset(conn, _sample_asset())

    created_ids = link_event_to_ip_assets(conn, event_id=1, event_summary="전기차 배터리 냉각 신규 공개")

    assert len(created_ids) == 1
    links = fetch_links_from(conn, LINK_OBJECT_EVENT, 1)
    assert len(links) == 1
    assert links[0]["to_type"] == LINK_OBJECT_IP_ASSET
    assert links[0]["basis"] == LINK_BASIS_IPC_MATCH
    assert links[0]["confirmed_by_human"] == 0


def test_link_event_to_ip_assets_skips_unrelated_asset(conn):
    insert_ip_asset(conn, _sample_asset(title="샘플 무관 반도체 장치", ipc_codes="G06F 1/20"))

    created_ids = link_event_to_ip_assets(conn, event_id=1, event_summary="전기차 배터리 냉각 신규 공개")

    assert created_ids == []
    assert fetch_links_from(conn, LINK_OBJECT_EVENT, 1) == []


def test_link_event_to_ip_assets_covers_both_asset_kinds(conn):
    insert_ip_asset(conn, _sample_asset())
    insert_ip_asset(
        conn,
        _sample_asset(application_number="SAMPLE-ASSET-0000002", asset_kind=ASSET_KIND_EXTERNAL),
    )

    created_ids = link_event_to_ip_assets(conn, event_id=1, event_summary="전기차 배터리 냉각 신규 공개")

    assert len(created_ids) == 2


def test_link_event_to_ip_assets_is_idempotent(conn):
    insert_ip_asset(conn, _sample_asset())

    first_run = link_event_to_ip_assets(conn, event_id=1, event_summary="전기차 배터리 냉각 신규 공개")
    second_run = link_event_to_ip_assets(conn, event_id=1, event_summary="전기차 배터리 냉각 신규 공개")

    assert len(first_run) == 1
    assert second_run == []
    assert len(fetch_links_from(conn, LINK_OBJECT_EVENT, 1)) == 1


def test_link_basis_is_keyword_when_no_ipc_hit(conn):
    # Title keyword overlap only — IPC codes don't fall in any configured
    # family/primary range, so basis should be "키워드", not "IPC 일치".
    insert_ip_asset(conn, _sample_asset(title="전기차 배터리 냉각 관련 샘플", ipc_codes="G06F 1/20"))

    link_event_to_ip_assets(conn, event_id=1, event_summary="전기차 배터리 냉각 신규 공개")

    links = fetch_links_from(conn, LINK_OBJECT_EVENT, 1)
    assert len(links) == 1
    assert links[0]["basis"] == LINK_BASIS_KEYWORD

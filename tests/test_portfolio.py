"""Tests for IP-asset portfolio ingestion (docs/PIPELINE.md 단계 3).

Records here are invented sample data, not real patents.
"""

from __future__ import annotations

import sqlite3

import pytest

from ipauto.db.connection import init_db
from ipauto.db.repositories import ASSET_KIND_EXTERNAL, ASSET_KIND_OWN, fetch_ip_asset, fetch_ip_assets
from ipauto.portfolio import ip_asset_from_fields

SAMPLE_RECORD = {
    "발명의 명칭": "샘플 배터리 팩",
    "출원번호": "SAMPLE-ASSET-0000001",
    "출원인": "샘플 주식회사",
    "IPC": "H01M 10/613",
    "등록상태": "공개(샘플)",
    "초록": "샘플 초록",
}


@pytest.fixture
def conn():
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    init_db(connection)
    yield connection
    connection.close()


def test_ip_asset_from_fields_maps_kipris_shaped_record():
    data = ip_asset_from_fields(SAMPLE_RECORD, ASSET_KIND_OWN)

    assert data.application_number == "SAMPLE-ASSET-0000001"
    assert data.asset_kind == ASSET_KIND_OWN
    assert data.title == "샘플 배터리 팩"
    assert data.ipc_codes == "H01M 10/613"


def test_ip_asset_from_fields_rejects_missing_application_number():
    with pytest.raises(ValueError):
        ip_asset_from_fields({**SAMPLE_RECORD, "출원번호": ""}, ASSET_KIND_OWN)


def test_ingest_records_upserts_each_record(conn):
    from ipauto.portfolio import ingest_records

    other_record = {**SAMPLE_RECORD, "출원번호": "SAMPLE-ASSET-0000002", "발명의 명칭": "샘플 다른 특허"}

    ids = ingest_records(conn, [SAMPLE_RECORD, other_record], asset_kind=ASSET_KIND_EXTERNAL)

    assert len(ids) == 2
    assert len(fetch_ip_assets(conn, asset_kind=ASSET_KIND_EXTERNAL)) == 2
    assert fetch_ip_asset(conn, "SAMPLE-ASSET-0000001")["title"] == "샘플 배터리 팩"


def test_ingest_records_reingesting_same_batch_does_not_duplicate(conn):
    from ipauto.portfolio import ingest_records

    ingest_records(conn, [SAMPLE_RECORD])
    ingest_records(conn, [SAMPLE_RECORD])

    assert len(fetch_ip_assets(conn)) == 1

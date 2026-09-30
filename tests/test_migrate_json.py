"""Tests for the legacy JSON -> SQLite judgment migration.

tests/fixtures/sample_judgments.json mimics the old data/judgments.json shape
with invented sample entries, not real judgment history.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from ipauto.db.connection import init_db
from ipauto.db.repositories import count_judgments, fetch_premises_for_judgment
from ipauto.judgments.migrate_json import MIGRATED_DECISION, migrate

FIXTURE_PATH = Path(__file__).resolve().parent / "fixtures" / "sample_judgments.json"


@pytest.fixture
def conn():
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    init_db(connection)
    yield connection
    connection.close()


def test_migrate_creates_one_judgment_row_per_json_entry(conn):
    migrated, skipped = migrate(conn, FIXTURE_PATH)

    entry_count = len(json.loads(FIXTURE_PATH.read_text(encoding="utf-8")))
    assert migrated == entry_count
    assert skipped == 0
    assert count_judgments(conn, migrated_from_json=True) == entry_count


def test_migrate_is_idempotent(conn):
    migrate(conn, FIXTURE_PATH)
    migrated_second_run, skipped_second_run = migrate(conn, FIXTURE_PATH)

    entry_count = len(json.loads(FIXTURE_PATH.read_text(encoding="utf-8")))
    assert migrated_second_run == 0
    assert skipped_second_run == entry_count
    assert count_judgments(conn) == entry_count


def test_migrated_rows_use_generic_decision_and_preserve_original_in_legacy_note(conn):
    migrate(conn, FIXTURE_PATH)

    row = conn.execute("SELECT * FROM judgment WHERE application_number = ?", ("SAMPLE-0000001",)).fetchone()
    assert row["decision"] == MIGRATED_DECISION
    assert "관련 있음" in row["legacy_note"]
    assert row["assignee"] == "이전 데이터"
    assert row["review_deadline"] == "이전 데이터"


def test_migrated_rows_carry_snapshot_fields_as_premises(conn):
    migrate(conn, FIXTURE_PATH)

    row = conn.execute("SELECT * FROM judgment WHERE application_number = ?", ("SAMPLE-0000001",)).fetchone()
    premises = {p["check_key"]: p["expected_value"] for p in fetch_premises_for_judgment(conn, row["id"])}
    assert premises["등록상태"] == "공개(샘플)"
    assert premises["출원인"] == "샘플대학교 산학협력단"
    assert premises["IPC"] == "H01M 10/613|H01M 10/625"


def test_migrate_returns_zero_zero_for_missing_file(conn, tmp_path):
    migrated, skipped = migrate(conn, tmp_path / "does_not_exist.json")
    assert (migrated, skipped) == (0, 0)

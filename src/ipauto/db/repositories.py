"""Append-only read/write access to the judgment ledger.

No function here issues UPDATE or DELETE against ``judgment`` or ``premise``:
a correction is always a new Judgment row chained via ``previous_judgment_id``.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field

from ipauto.db.connection import transaction

DECISION_CHOICES = (
    "신규 출원 검토",
    "기존 IP 보강 검토",
    "유지",
    "정리 검토",
    "타사 특허 확인 필요",
)


@dataclass(frozen=True)
class PremiseInput:
    source: str
    check_key: str
    expected_value: str
    check_method: str | None = None


@dataclass(frozen=True)
class JudgmentInput:
    application_number: str
    review_technology: str
    decision: str
    reason: str
    assignee: str
    review_deadline: str
    premises: list[PremiseInput] = field(default_factory=list)
    event_id: int | None = None
    search_query: str | None = None
    analysis_mode: str | None = None
    relevance_score: float | None = None
    review_priority: str | None = None
    model_version: str | None = None
    prompt_version: str | None = None
    previous_judgment_id: int | None = None
    migrated_from_json: bool = False
    legacy_note: str | None = None
    created_at: str | None = None


def fetch_latest_judgment(
    conn: sqlite3.Connection, application_number: str, review_technology: str
) -> sqlite3.Row | None:
    row = conn.execute(
        """
        SELECT * FROM judgment
        WHERE application_number = ? AND review_technology = ?
        ORDER BY created_at DESC, id DESC
        LIMIT 1
        """,
        (application_number, review_technology),
    ).fetchone()
    return row


def fetch_judgments_for_application(conn: sqlite3.Connection, application_number: str) -> list[sqlite3.Row]:
    return conn.execute(
        """
        SELECT * FROM judgment
        WHERE application_number = ?
        ORDER BY created_at DESC, id DESC
        """,
        (application_number,),
    ).fetchall()


def fetch_premises_for_judgment(conn: sqlite3.Connection, judgment_id: int) -> list[sqlite3.Row]:
    return conn.execute("SELECT * FROM premise WHERE judgment_id = ? ORDER BY id", (judgment_id,)).fetchall()


def count_judgments(conn: sqlite3.Connection, migrated_from_json: bool | None = None) -> int:
    if migrated_from_json is None:
        row = conn.execute("SELECT COUNT(*) AS n FROM judgment").fetchone()
    else:
        row = conn.execute(
            "SELECT COUNT(*) AS n FROM judgment WHERE migrated_from_json = ?",
            (1 if migrated_from_json else 0,),
        ).fetchone()
    return row["n"]


def find_migrated_judgment(conn: sqlite3.Connection, application_number: str, created_at: str) -> sqlite3.Row | None:
    """Look up a previously migrated row by its original (app number, decisionTime).

    Used by migrate_json.py to stay idempotent across repeated runs.
    """
    return conn.execute(
        """
        SELECT * FROM judgment
        WHERE application_number = ? AND created_at = ? AND migrated_from_json = 1
        """,
        (application_number, created_at),
    ).fetchone()


def _insert_judgment_row(conn: sqlite3.Connection, data: JudgmentInput) -> int:
    columns = [
        "application_number",
        "review_technology",
        "event_id",
        "search_query",
        "analysis_mode",
        "decision",
        "reason",
        "assignee",
        "review_deadline",
        "relevance_score",
        "review_priority",
        "model_version",
        "prompt_version",
        "previous_judgment_id",
        "migrated_from_json",
        "legacy_note",
    ]
    values = [
        data.application_number,
        data.review_technology,
        data.event_id,
        data.search_query,
        data.analysis_mode,
        data.decision,
        data.reason,
        data.assignee,
        data.review_deadline,
        data.relevance_score,
        data.review_priority,
        data.model_version,
        data.prompt_version,
        data.previous_judgment_id,
        1 if data.migrated_from_json else 0,
        data.legacy_note,
    ]
    if data.created_at is not None:
        columns.append("created_at")
        values.append(data.created_at)

    placeholders = ", ".join("?" for _ in columns)
    cursor = conn.execute(f"INSERT INTO judgment ({', '.join(columns)}) VALUES ({placeholders})", values)
    return cursor.lastrowid


def save_judgment(conn: sqlite3.Connection, data: JudgmentInput) -> int:
    """Insert one Judgment plus its Premise rows in a single transaction."""
    with transaction(conn):
        judgment_id = _insert_judgment_row(conn, data)
        for premise in data.premises:
            conn.execute(
                """
                INSERT INTO premise (judgment_id, source, check_key, expected_value, check_method)
                VALUES (?, ?, ?, ?, ?)
                """,
                (judgment_id, premise.source, premise.check_key, premise.expected_value, premise.check_method),
            )
    return judgment_id

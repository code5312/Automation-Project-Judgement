"""One-time migration: legacy data/judgments.json -> Judgment/Premise rows.

The old JSON entries never captured 검토 기술, 검색어, 담당자, 재검토 기한, or
a decision from the new IP-action enum (they held a relevance judgment:
관련 있음/없음/추가 검토, a different concept). Rather than guess a specific
IP action, every migrated row gets the generic "타사 특허 확인 필요" decision
so it surfaces for a human recheck, and the original relevance judgment is
preserved verbatim in ``legacy_note`` so no information is lost. Missing
fields are set to the literal string "이전 데이터", never NULL, so they are
visibly marked as migrated rather than looking like real new-schema data.

Idempotent: re-running skips any (application_number, decisionTime) pair
that was already migrated (see db.repositories.find_migrated_judgment).
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from ipauto.db.repositories import JudgmentInput, PremiseInput, find_migrated_judgment
from ipauto.db.repositories import save_judgment as _insert_judgment

LEGACY_PLACEHOLDER = "이전 데이터"
MIGRATED_DECISION = "타사 특허 확인 필요"

DEFAULT_JSON_PATH = Path(__file__).resolve().parents[3] / "data" / "judgments.json"

_SNAPSHOT_PREMISE_KEYS = (
    ("registerStatusAtDecision", "등록상태"),
    ("applicantNameAtDecision", "출원인"),
    ("ipcNumberAtDecision", "IPC"),
)


def _load_entries(json_path: Path) -> list[dict]:
    if not json_path.exists():
        return []
    with json_path.open("r", encoding="utf-8") as source:
        data = json.load(source)
    if not isinstance(data, list):
        raise ValueError(f"{json_path} does not contain a JSON list.")
    return [entry for entry in data if isinstance(entry, dict)]


def _premises_from_entry(entry: dict) -> list[PremiseInput]:
    premises = [
        PremiseInput(source=LEGACY_PLACEHOLDER, check_key=check_key, expected_value=str(value))
        for json_key, check_key in _SNAPSHOT_PREMISE_KEYS
        if (value := entry.get(json_key))
    ]
    if not premises:
        premises = [
            PremiseInput(source=LEGACY_PLACEHOLDER, check_key=LEGACY_PLACEHOLDER, expected_value=LEGACY_PLACEHOLDER)
        ]
    return premises


def migrate(conn: sqlite3.Connection, json_path: Path = DEFAULT_JSON_PATH) -> tuple[int, int]:
    """Migrate every entry in json_path. Returns (migrated_count, skipped_count)."""
    entries = _load_entries(json_path)
    migrated = 0
    skipped = 0
    for entry in entries:
        application_number = str(entry.get("applicationNumber") or "")
        created_at = str(entry.get("decisionTime") or "")
        if find_migrated_judgment(conn, application_number, created_at) is not None:
            skipped += 1
            continue

        original_decision = str(entry.get("decision") or "")
        data = JudgmentInput(
            application_number=application_number,
            review_technology=LEGACY_PLACEHOLDER,
            decision=MIGRATED_DECISION,
            reason=str(entry.get("decisionReason") or LEGACY_PLACEHOLDER),
            assignee=LEGACY_PLACEHOLDER,
            review_deadline=LEGACY_PLACEHOLDER,
            premises=_premises_from_entry(entry),
            search_query=LEGACY_PLACEHOLDER,
            analysis_mode=LEGACY_PLACEHOLDER,
            relevance_score=entry.get("relevanceScoreAtDecision"),
            review_priority=str(entry.get("reviewPriorityAtDecision") or "") or None,
            migrated_from_json=True,
            legacy_note=f"이전 데이터(관련도 판단): {original_decision}",
            created_at=created_at or None,
        )
        _insert_judgment(conn, data)
        migrated += 1
    return migrated, skipped


def main() -> int:
    from ipauto.db.connection import connect, init_db
    from ipauto.db.repositories import count_judgments

    conn = connect()
    init_db(conn)
    migrated, skipped = migrate(conn)
    total_legacy = len(_load_entries(DEFAULT_JSON_PATH))
    total_migrated_rows = count_judgments(conn, migrated_from_json=True)
    print(f"Migrated {migrated} row(s), skipped {skipped} already-migrated row(s).")
    print(f"Legacy JSON entries: {total_legacy}  |  Migrated Judgment rows in DB: {total_migrated_rows}")
    if total_migrated_rows != total_legacy:
        print("WARNING: migrated row count does not match legacy entry count.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

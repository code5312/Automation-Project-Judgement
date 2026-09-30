"""Gate B judgment storage against SQLite (docs/DESIGN.md IP 조치 결정).

Validates before writing: reason non-blank, at least one premise, and
assignee/review_deadline present. A re-judgment for the same
(application_number, review_technology) key is chained via
previous_judgment_id instead of overwriting anything; an identical
resubmission for the same key is rejected as a duplicate.
"""

from __future__ import annotations

import sqlite3

from ipauto.db.repositories import (
    DECISION_CHOICES,
    JudgmentInput,
    PremiseInput,
    fetch_judgments_for_application,
    fetch_latest_judgment,
    fetch_premises_for_judgment,
)
from ipauto.db.repositories import save_judgment as _insert_judgment

TITLE_FIELD = "발명의 명칭"
APPLICATION_FIELD = "출원번호"
APPLICANT_FIELD = "출원인"
IPC_FIELD = "IPC"
STATUS_FIELD = "등록상태"


class JudgmentValidationError(ValueError):
    """Gate B validation failed; nothing was written."""


class DuplicateJudgmentError(ValueError):
    """An identical judgment for this key already exists as the latest one."""


def _is_duplicate(latest: sqlite3.Row | None, decision: str, reason: str, assignee: str, review_deadline: str) -> bool:
    if latest is None:
        return False
    return (
        latest["decision"] == decision
        and latest["reason"] == reason
        and latest["assignee"] == assignee
        and latest["review_deadline"] == review_deadline
    )


def save_gate_b_judgment(
    conn: sqlite3.Connection,
    *,
    application_number: str,
    review_technology: str,
    decision: str,
    reason: str,
    premises: list[tuple[str, str, str]],
    assignee: str,
    review_deadline: str,
    search_query: str | None = None,
    analysis_mode: str | None = None,
    relevance_score: float | None = None,
    review_priority: str | None = None,
) -> int:
    """Validate and append one Gate B judgment. Returns the new judgment id.

    ``premises`` is a list of (source, check_key, expected_value) triples;
    rows with a blank expected_value are dropped before the "at least one
    premise" check, so a UI can pass a fixed number of input rows and let
    empty ones simply not count.
    """
    reason = reason.strip()
    assignee = assignee.strip()
    review_deadline = review_deadline.strip()

    if decision not in DECISION_CHOICES:
        raise JudgmentValidationError(f"결정은 다음 중 하나여야 합니다: {', '.join(DECISION_CHOICES)}")
    if not reason:
        raise JudgmentValidationError("판단 이유는 비어 있을 수 없습니다.")
    if not assignee:
        raise JudgmentValidationError("담당자를 입력해주세요.")
    if not review_deadline:
        raise JudgmentValidationError("재검토 기한을 입력해주세요.")

    cleaned_premises = [
        (source.strip(), check_key.strip(), expected_value.strip())
        for source, check_key, expected_value in premises
        if expected_value.strip()
    ]
    if not cleaned_premises:
        raise JudgmentValidationError("전제를 1개 이상 입력해주세요.")

    latest = fetch_latest_judgment(conn, application_number, review_technology)
    if _is_duplicate(latest, decision, reason, assignee, review_deadline):
        raise DuplicateJudgmentError("동일한 판단이 이미 저장되어 있습니다.")

    data = JudgmentInput(
        application_number=application_number,
        review_technology=review_technology,
        decision=decision,
        reason=reason,
        assignee=assignee,
        review_deadline=review_deadline,
        premises=[
            PremiseInput(source=source, check_key=check_key, expected_value=expected_value)
            for source, check_key, expected_value in cleaned_premises
        ],
        search_query=search_query,
        analysis_mode=analysis_mode,
        relevance_score=relevance_score,
        review_priority=review_priority,
        previous_judgment_id=latest["id"] if latest is not None else None,
    )
    return _insert_judgment(conn, data)


def history_for_application(conn: sqlite3.Connection, application_number: str) -> list[sqlite3.Row]:
    """All judgments for one application number, most recent first."""
    return fetch_judgments_for_application(conn, application_number)


def premises_for_judgment(conn: sqlite3.Connection, judgment_id: int) -> list[sqlite3.Row]:
    return fetch_premises_for_judgment(conn, judgment_id)

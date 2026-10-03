"""Triage re-measurement against the labeled evaluation set (docs/PIPELINE.md 단계 3: "평가 세트로 트리아지 재측정").

Reuses the same evaluation set ``ipauto.evaluation`` already validates the
raw scorer against (``data/eval/ev_battery_cooling_v1.json``) instead of
building a second one — PIPELINE.md asks to re-measure with "평가 세트" (the
existing, human-confirmed one), not a brand-new triage-specific label set.
Relevance labels map onto triage outcomes the same way the bands already do:
높음 → 관련, 보통 → 애매, 낮음 → 무관.

Each item runs through ``ipauto.triage.routing.decide_triage`` with no LLM
result — this environment has no ``ANTHROPIC_API_KEY`` (docs/PIPELINE.md
단계 3 LLM 항목) — against a fresh, judgment-free in-memory database. That
means the LLM-dependent ambiguity rules (신호 불일치, 확신도 중간대) and the
과거 판단 충돌 rule structurally cannot fire here: this measures whether the
new routing layer reproduces 단계 2's validated scorer accuracy end-to-end,
not whether the LLM/past-judgment signals add anything on top — this
environment cannot measure that without a real API key.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field

from ipauto.db.connection import init_db
from ipauto.evaluation import EvalItem
from ipauto.scoring.bands import PRIORITY_HIGH, PRIORITY_LOW, PRIORITY_MEDIUM
from ipauto.triage.routing import TRIAGE_AMBIGUOUS, TRIAGE_RELATED, TRIAGE_UNRELATED, decide_triage

EXPECTED_OUTCOME_BY_PRIORITY = {
    PRIORITY_HIGH: TRIAGE_RELATED,
    PRIORITY_MEDIUM: TRIAGE_AMBIGUOUS,
    PRIORITY_LOW: TRIAGE_UNRELATED,
}

_TITLE_FIELD = "발명의 명칭"
_IPC_FIELD = "IPC"

# Neutral stand-ins so only the keyword/IPC signal drives the outcome: a
# non-high-risk event type and a non-blank occurred_at keep rules 3/4 from
# firing on every single item regardless of its actual relevance.
_BENIGN_EVENT_TYPE = "오픈소스 공개"
_DUMMY_OCCURRED_AT = "2026-01-01T00:00:00Z"


@dataclass(frozen=True)
class TriageEvalResult:
    total: int
    correct: int
    outcome_counts: dict[str, int] = field(default_factory=dict)
    mismatches: list[tuple[EvalItem, str, str]] = field(default_factory=list)  # (item, expected, actual)

    @property
    def accuracy(self) -> float:
        return self.correct / self.total if self.total else 0.0

    @property
    def ambiguous_rate(self) -> float:
        return self.outcome_counts.get(TRIAGE_AMBIGUOUS, 0) / self.total if self.total else 0.0


def _fresh_memory_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    init_db(conn)
    return conn


def measure_triage_accuracy(items: list[EvalItem]) -> TriageEvalResult:
    """Run each eval item through decide_triage (no LLM) and compare to its mapped outcome."""
    conn = _fresh_memory_db()
    try:
        correct = 0
        outcome_counts: dict[str, int] = {}
        mismatches: list[tuple[EvalItem, str, str]] = []
        for item in items:
            expected = EXPECTED_OUTCOME_BY_PRIORITY[item.human_label]
            decision = decide_triage(
                conn,
                event_type=_BENIGN_EVENT_TYPE,
                event_summary=item.review_technology,
                event_occurred_at=_DUMMY_OCCURRED_AT,
                asset_title=item.record.get(_TITLE_FIELD, ""),
                asset_ipc=item.record.get(_IPC_FIELD, ""),
                application_number=item.application_number,
                llm_result=None,
            )
            outcome_counts[decision.outcome] = outcome_counts.get(decision.outcome, 0) + 1
            if decision.outcome == expected:
                correct += 1
            else:
                mismatches.append((item, expected, decision.outcome))
    finally:
        conn.close()

    return TriageEvalResult(total=len(items), correct=correct, outcome_counts=outcome_counts, mismatches=mismatches)

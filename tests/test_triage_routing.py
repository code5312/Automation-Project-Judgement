"""Tests for ambiguous-queue routing (docs/PIPELINE.md 단계 3: 애매 큐 라우팅 규칙 5가지).

Records/events here are invented sample data, not real patents or events.
"""

from __future__ import annotations

import sqlite3

import pytest

from ipauto.db.connection import init_db
from ipauto.db.repositories import JudgmentInput, PremiseInput
from ipauto.db.repositories import save_judgment as insert_judgment
from ipauto.triage.llm_classifier import LABEL_RELEVANT, LABEL_UNRELATED, ClassificationResult
from ipauto.triage.routing import (
    HIGH_RISK_EVENT_TYPES,
    MID_CONFIDENCE_RANGE,
    TRIAGE_AMBIGUOUS,
    TRIAGE_RELATED,
    TRIAGE_UNRELATED,
    decide_triage,
)

EV_SUMMARY = "전기차 배터리 냉각 신규 공개"
EV_TYPE = "오픈소스 공개"
ASSET_TITLE_RELEVANT = "전기차 배터리 냉각 장치"
ASSET_IPC_RELEVANT = "H01M 10/613"
ASSET_TITLE_UNRELATED = "샘플 무관 반도체 장치"
ASSET_IPC_UNRELATED = "G06F 1/20"


@pytest.fixture
def conn():
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    init_db(connection)
    yield connection
    connection.close()


def _llm(label: str, confidence: float, missing_info: list[str] | None = None) -> ClassificationResult:
    return ClassificationResult(
        label=label, confidence=confidence, evidence=["샘플 근거"], missing_info=missing_info or [], raw_response="{}"
    )


def _decide(conn, **overrides):
    defaults = dict(
        event_type=EV_TYPE,
        event_summary=EV_SUMMARY,
        event_occurred_at="2026-01-01T00:00:00Z",
        asset_title=ASSET_TITLE_RELEVANT,
        asset_ipc=ASSET_IPC_RELEVANT,
        application_number="SAMPLE-0000001",
        llm_result=_llm(LABEL_RELEVANT, 0.9),
    )
    defaults.update(overrides)
    return decide_triage(conn, **defaults)


# --- base outcome without ambiguity ---------------------------------------


def test_high_confidence_agreement_routes_related(conn):
    decision = _decide(conn, llm_result=_llm(LABEL_RELEVANT, 0.95))

    assert decision.outcome == TRIAGE_RELATED
    assert decision.reasons == []


def test_high_confidence_agreement_on_unrelated_routes_unrelated(conn):
    decision = _decide(
        conn,
        asset_title=ASSET_TITLE_UNRELATED,
        asset_ipc=ASSET_IPC_UNRELATED,
        llm_result=_llm(LABEL_UNRELATED, 0.95),
    )

    assert decision.outcome == TRIAGE_UNRELATED
    assert decision.reasons == []


def test_without_llm_high_keyword_band_routes_related(conn):
    decision = _decide(conn, llm_result=None)

    assert decision.outcome == TRIAGE_RELATED


def test_without_llm_low_keyword_band_routes_unrelated(conn):
    decision = _decide(conn, asset_title=ASSET_TITLE_UNRELATED, asset_ipc=ASSET_IPC_UNRELATED, llm_result=None)

    assert decision.outcome == TRIAGE_UNRELATED


def test_without_llm_medium_keyword_band_routes_ambiguous(conn):
    # vehicle+battery text match plus both IPC families (no cooling text, so
    # no primary-signal bonus) lands at 41 points, inside the medium band;
    # verified empirically against ipauto.scoring.keywords.calculate_relevance.
    decision = _decide(conn, asset_title="전기차 배터리 시스템", asset_ipc="H01M 10/42|B60L 50/50", llm_result=None)

    assert decision.outcome == TRIAGE_AMBIGUOUS
    assert decision.reasons  # non-empty: "판단 보류" fallback reason


# --- rule 1: 신호 불일치 -----------------------------------------------------


def test_rule1_signal_disagreement_high_keyword_llm_unrelated(conn):
    decision = _decide(conn, llm_result=_llm(LABEL_UNRELATED, 0.9))

    assert decision.outcome == TRIAGE_AMBIGUOUS
    assert any("신호 불일치" in reason for reason in decision.reasons)


def test_rule1_signal_disagreement_low_keyword_llm_relevant(conn):
    decision = _decide(
        conn,
        asset_title=ASSET_TITLE_UNRELATED,
        asset_ipc=ASSET_IPC_UNRELATED,
        llm_result=_llm(LABEL_RELEVANT, 0.9),
    )

    assert decision.outcome == TRIAGE_AMBIGUOUS
    assert any("신호 불일치" in reason for reason in decision.reasons)


# --- rule 2: 확신도 중간대 ---------------------------------------------------


def test_rule2_mid_confidence_routes_ambiguous(conn):
    low, high = MID_CONFIDENCE_RANGE
    mid = (low + high) / 2
    decision = _decide(conn, llm_result=_llm(LABEL_RELEVANT, mid))

    assert decision.outcome == TRIAGE_AMBIGUOUS
    assert any("확신도 중간대" in reason for reason in decision.reasons)


def test_confidence_just_above_mid_range_does_not_trigger_rule2(conn):
    _low, high = MID_CONFIDENCE_RANGE
    decision = _decide(conn, llm_result=_llm(LABEL_RELEVANT, high + 0.2))

    assert decision.outcome == TRIAGE_RELATED


# --- rule 3: 필수 정보 누락 ---------------------------------------------------


def test_rule3_missing_occurred_at_routes_ambiguous(conn):
    decision = _decide(conn, event_occurred_at=None)

    assert decision.outcome == TRIAGE_AMBIGUOUS
    assert any("필수 정보 누락" in reason and "발생/공개 시각" in reason for reason in decision.reasons)


def test_rule3_llm_missing_info_routes_ambiguous(conn):
    decision = _decide(conn, llm_result=_llm(LABEL_RELEVANT, 0.9, missing_info=["샘플 부족 정보"]))

    assert decision.outcome == TRIAGE_AMBIGUOUS
    assert any("샘플 부족 정보" in reason for reason in decision.reasons)


# --- rule 4: 고위험 사건 유형 -------------------------------------------------


def test_rule4_high_risk_event_type_routes_ambiguous(conn):
    assert HIGH_RISK_EVENT_TYPES  # sanity: constant is non-empty
    decision = _decide(conn, event_type=HIGH_RISK_EVENT_TYPES[0])

    assert decision.outcome == TRIAGE_AMBIGUOUS
    assert any("고위험 사건 유형" in reason for reason in decision.reasons)


def test_normal_event_type_does_not_trigger_rule4(conn):
    decision = _decide(conn, event_type="오픈소스 공개")

    assert decision.outcome == TRIAGE_RELATED


# --- rule 5: 과거 판단과 충돌 -------------------------------------------------


def _insert_past_judgment(conn, application_number: str, decision: str) -> None:
    insert_judgment(
        conn,
        JudgmentInput(
            application_number=application_number,
            review_technology="샘플 기술",
            decision=decision,
            reason="샘플 이유",
            assignee="샘플 담당자",
            review_deadline="2026-12-31",
            premises=[PremiseInput(source="샘플", check_key="등록상태", expected_value="공개(샘플)")],
        ),
    )


def test_rule5_conflicts_with_past_no_action_decision(conn):
    _insert_past_judgment(conn, "SAMPLE-0000001", "유지")

    decision = _decide(conn, llm_result=_llm(LABEL_RELEVANT, 0.9))

    assert decision.outcome == TRIAGE_AMBIGUOUS
    assert any("과거 판단과 충돌" in reason for reason in decision.reasons)


def test_rule5_conflicts_with_past_action_decision(conn):
    _insert_past_judgment(conn, "SAMPLE-0000001", "신규 출원 검토")

    decision = _decide(
        conn,
        asset_title=ASSET_TITLE_UNRELATED,
        asset_ipc=ASSET_IPC_UNRELATED,
        llm_result=_llm(LABEL_UNRELATED, 0.9),
    )

    assert decision.outcome == TRIAGE_AMBIGUOUS
    assert any("과거 판단과 충돌" in reason for reason in decision.reasons)


def test_rule5_no_conflict_when_past_decision_agrees(conn):
    _insert_past_judgment(conn, "SAMPLE-0000001", "신규 출원 검토")

    decision = _decide(conn, llm_result=_llm(LABEL_RELEVANT, 0.9))

    assert decision.outcome == TRIAGE_RELATED


def test_rule5_no_past_judgment_does_not_trigger(conn):
    decision = _decide(conn, application_number="SAMPLE-NEVER-JUDGED", llm_result=_llm(LABEL_RELEVANT, 0.9))

    assert decision.outcome == TRIAGE_RELATED

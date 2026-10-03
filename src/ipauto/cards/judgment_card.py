"""Judgment card assembly (docs/DESIGN.md 판단 카드, docs/PIPELINE.md 단계 3).

Assembles everything a human needs to decide on one Event/IPAsset pair into
a single read-only snapshot, right before 게이트 B:

- 사건 요약과 원문 링크
- 관련 근거 원문 인용
- 과거 결정과 유사 사례
- 누락된 정보와 사람이 확인할 질문
- 추천 조치(정해진 목록에서만) — 항상 docs/DESIGN.md 결정 열거형 전체를
  반환하고, 가장 그럴듯한 항목을 앞으로 재배열만 한다. 자유 서술 추천은
  절대 하지 않는다("추천은 열거형 선택지로 제한").
- "법률 자문 아님" 문구와 사용한 모델·프롬프트 버전

This module never calls the LLM itself — pass an already-computed
``ClassificationResult`` (e.g. from ``ipauto.cli triage``) if one exists;
without it, the card falls back to the keyword/IPC scorer's own reasoning
text as its only evidence, with no model/prompt version to cite.

판단 카드 자체는 DESIGN.md의 저장 모델에 없는, 매번 다시 계산하는 뷰다 —
Event·IPAsset·Link·Judgment·(선택) LLM 결과가 이미 있으니 따로 저장할
필요가 없다.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass

from ipauto.db.repositories import ASSET_KIND_EXTERNAL, DECISION_CHOICES, fetch_judgments_for_application
from ipauto.judgments.service import save_gate_b_judgment
from ipauto.scoring.keywords import (
    ANALYSIS_MODE_FIELD,
    MATCHED_FIELD,
    PRIORITY_FIELD,
    REASON_FIELD,
    SCORE_FIELD,
    calculate_relevance,
)
from ipauto.triage.llm_classifier import ClassificationResult

LEGAL_DISCLAIMER = (
    "이 판단 카드는 선행특허 여부·등록 가능성·침해 여부에 대한 법적 판단이나 법률 자문이 아닙니다. "
    "모든 추천은 근거와 함께 제시되며, 최종 IP 조치 결정은 항상 사람이 내립니다."
)

_TITLE_FIELD = "발명의 명칭"
_IPC_FIELD = "IPC"


@dataclass(frozen=True)
class SimilarCase:
    judgment_id: int
    decision: str
    reason: str
    created_at: str


@dataclass(frozen=True)
class JudgmentCard:
    event_id: int
    ip_asset_id: int
    application_number: str
    event_summary: str
    event_source_url: str | None
    ip_asset_title: str
    evidence: list[str]
    similar_cases: list[SimilarCase]
    missing_info: list[str]
    recommended_decisions: list[str]
    relevance_score: float
    review_priority: str
    analysis_mode: str
    disclaimer: str = LEGAL_DISCLAIMER
    model_version: str | None = None
    prompt_version: str | None = None


def _recommend_decisions(asset_kind: str, past_decision: str | None) -> list[str]:
    """Reorder the full decision enum with the most plausible option(s) first.

    This is a starting heuristic (asset_kind + the single most recent past
    Judgment for this application_number), not a legal or technical
    conclusion, and it never drops a choice — a human can still pick any
    option in the enum.
    """
    if asset_kind == ASSET_KIND_EXTERNAL:
        primary = ["타사 특허 확인 필요"]
    elif past_decision == "유지":
        primary = ["유지", "기존 IP 보강 검토"]
    elif past_decision is not None and past_decision in DECISION_CHOICES:
        primary = [past_decision]
    else:
        primary = ["신규 출원 검토", "기존 IP 보강 검토"]
    rest = [decision for decision in DECISION_CHOICES if decision not in primary]
    return [*primary, *rest]


def _similar_cases(conn: sqlite3.Connection, application_number: str) -> list[SimilarCase]:
    rows = fetch_judgments_for_application(conn, application_number)
    return [
        SimilarCase(
            judgment_id=row["id"], decision=row["decision"], reason=row["reason"], created_at=row["created_at"]
        )
        for row in rows
    ]


def build_judgment_card(
    conn: sqlite3.Connection,
    event_row: sqlite3.Row,
    asset_row: sqlite3.Row,
    llm_result: ClassificationResult | None = None,
) -> JudgmentCard:
    """Assemble a read-only Judgment Card for one Event/IPAsset pair.

    Pass the LLM classification result if one was already computed
    (e.g. by ``ipauto.cli triage``) — this function never calls the LLM.
    """
    similar_cases = _similar_cases(conn, asset_row["application_number"])
    past_decision = similar_cases[0].decision if similar_cases else None

    # The keyword/IPC score is computed regardless of whether an LLM result
    # is available — relevance_score/review_priority/analysis_mode are
    # provenance for the eventual Judgment row either way; only the
    # evidence/missing_info text source switches on llm_result.
    record = {_TITLE_FIELD: asset_row["title"] or "", _IPC_FIELD: asset_row["ipc_codes"] or ""}
    scoring_result = calculate_relevance(event_row["summary"] or "", record)

    if llm_result is not None:
        evidence = list(llm_result.evidence)
        missing_info = list(llm_result.missing_info)
        model_version = llm_result.model
        prompt_version = llm_result.prompt_version
    else:
        evidence = [str(scoring_result[REASON_FIELD])] if scoring_result[MATCHED_FIELD] else []
        missing_info = []
        model_version = None
        prompt_version = None

    return JudgmentCard(
        event_id=event_row["id"],
        ip_asset_id=asset_row["id"],
        application_number=asset_row["application_number"],
        event_summary=event_row["summary"] or "",
        event_source_url=event_row["source_url"],
        ip_asset_title=asset_row["title"] or "",
        evidence=evidence,
        similar_cases=similar_cases,
        missing_info=missing_info,
        recommended_decisions=_recommend_decisions(asset_row["asset_kind"], past_decision),
        relevance_score=float(scoring_result[SCORE_FIELD]),
        review_priority=str(scoring_result[PRIORITY_FIELD]),
        analysis_mode=str(scoring_result[ANALYSIS_MODE_FIELD]),
        model_version=model_version,
        prompt_version=prompt_version,
    )


def save_judgment_from_card(
    conn: sqlite3.Connection,
    card: JudgmentCard,
    *,
    decision: str,
    reason: str,
    premises: list[tuple[str, str, str]],
    assignee: str,
    review_deadline: str,
) -> int:
    """Save one Gate B Judgment sourced from a Judgment Card (판단 카드 → 게이트 B).

    ``review_technology`` is the card's ``event_summary`` — playing the same
    role the free-text "검토하려는 기술" field plays in the original
    KIPRIS-search flow, since here the 사건 itself is what's being checked
    against. All of the card's scoring/LLM provenance (relevance_score,
    review_priority, analysis_mode, model_version, prompt_version) and the
    source event_id are carried onto the saved Judgment row. Validation and
    duplicate detection are still ``ipauto.judgments.service``'s job — this
    only wires the card's fields into that same call.
    """
    return save_gate_b_judgment(
        conn,
        application_number=card.application_number,
        review_technology=card.event_summary,
        decision=decision,
        reason=reason,
        premises=premises,
        assignee=assignee,
        review_deadline=review_deadline,
        analysis_mode=card.analysis_mode,
        relevance_score=card.relevance_score,
        review_priority=card.review_priority,
        event_id=card.event_id,
        model_version=card.model_version,
        prompt_version=card.prompt_version,
    )


def format_card_text(card: JudgmentCard) -> str:
    """Render a JudgmentCard as plain text (CLI output)."""
    lines = [
        f"[판단 카드] 사건 #{card.event_id} x IP 자산 #{card.ip_asset_id} ({card.application_number})",
        f"IP 자산: {card.ip_asset_title}",
        f"사건 요약: {card.event_summary}",
    ]
    if card.event_source_url:
        lines.append(f"원문 링크: {card.event_source_url}")

    lines.append("근거:")
    if card.evidence:
        lines.extend(f"  - {item}" for item in card.evidence)
    else:
        lines.append("  (없음)")

    lines.append(f"유사 사례 ({len(card.similar_cases)}건):")
    if card.similar_cases:
        for case in card.similar_cases:
            lines.append(f"  - [{case.created_at}] {case.decision}: {case.reason}")
    else:
        lines.append("  (과거 판단 이력 없음)")

    lines.append("누락 정보:")
    if card.missing_info:
        lines.extend(f"  - {item}" for item in card.missing_info)
    else:
        lines.append("  (없음)")

    lines.append(f"추천 선택지 (순서대로): {', '.join(card.recommended_decisions)}")
    lines.append(
        f"관련도 점수/우선순위/분석 모드: {card.relevance_score} / {card.review_priority} / {card.analysis_mode}"
    )
    lines.append(f"모델/프롬프트 버전: {card.model_version or '-'} / {card.prompt_version or '-'}")
    lines.append(card.disclaimer)
    return "\n".join(lines)

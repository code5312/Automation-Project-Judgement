"""애매 큐 라우팅 (docs/DESIGN.md 트리아지, docs/PIPELINE.md 단계 3).

docs/DESIGN.md의 네 신호(IPC 주 신호, 개념 키워드, 임베딩 유사도, LLM
구조화 판정) 중 임베딩 유사도는 이 저장소에 아직 없다(단계 2·3 어디에도
구현되지 않음). 규칙 1 "신호 불일치"는 원래 "임베딩 유사도 vs LLM" 조합을
이 저장소가 실제로 가진 "키워드/IPC 점수 밴드 vs LLM" 조합으로 대체했다
— 임베딩 유사도가 추가되면 이 함수에 세 번째 신호로 끼워 넣는다.

출력은 세 갈래(무관/관련/애매, docs/DESIGN.md)이고, 애매 라우팅은 다음
다섯 규칙 중 하나라도 해당하면 적용된다(사람이 직접 확인, 게이트 A):

1. 신호 불일치: 키워드/IPC 점수가 높음인데 LLM은 무관으로 판정, 또는 그 반대
2. 확신도가 중간대 (LLM confidence가 설정된 중간 구간에 있음)
3. 필수 정보 누락: 사건의 발생/공개 시각이 없거나, LLM이 missing_info를 남김
4. 고위험 사건 유형: 공개 예정·등록 IP 변경 등 설계상 늘 사람이 보는 유형
5. 과거 판단과 충돌: 이 출원번호에 대한 과거 Judgment와 지금 결론의 방향이 다름

LLM 판정은 선택적이다(``llm_result=None``) — 접근키가 없거나 호출을
생략한 경우 키워드/IPC 신호만으로 라우팅하며, 그 경우 중간 밴드는 항상
애매로 보낸다(아무것도 확인해주지 않았으므로).

"자동 종결 로그"(무관으로 자동 종료된 건의 기록)는 다음 PIPELINE.md
항목이고, 이 모듈은 라우팅 결론만 낸다.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field

from ipauto.db.repositories import DECISION_CHOICES, fetch_judgments_for_application
from ipauto.scoring.bands import PRIORITY_HIGH, PRIORITY_LOW
from ipauto.scoring.keywords import PRIORITY_FIELD, calculate_relevance
from ipauto.triage.llm_classifier import LABEL_RELEVANT, LABEL_UNRELATED, ClassificationResult

TRIAGE_UNRELATED = "무관"
TRIAGE_RELATED = "관련"
TRIAGE_AMBIGUOUS = "애매"
TRIAGE_OUTCOME_CHOICES = (TRIAGE_UNRELATED, TRIAGE_RELATED, TRIAGE_AMBIGUOUS)

# docs/DESIGN.md "확신도가 중간대" — 이 범위에 들면 LLM 혼자서는 확신하지
# 못한다고 본다. 평가 세트로 튜닝되지 않은 시작값(단계 2의 임계값과 같은 상황).
MID_CONFIDENCE_RANGE = (0.4, 0.75)

# docs/DESIGN.md "고위험 사건 유형: 공개 예정, 등록 IP 변경은 항상 사람".
# 지금 커넥터(GitHub 릴리스)는 "오픈소스 공개" 하나만 만들어내므로 이
# 규칙은 아직 실제로 걸리지 않지만, 다른 커넥터가 추가되면 바로 적용된다.
HIGH_RISK_EVENT_TYPES = ("공개 예정", "등록 IP 변경")

_ACTION_DECISIONS = tuple(decision for decision in DECISION_CHOICES if decision != "유지")
_NO_ACTION_DECISIONS = ("유지",)

_TITLE_FIELD = "발명의 명칭"
_IPC_FIELD = "IPC"


@dataclass(frozen=True)
class TriageDecision:
    outcome: str
    reasons: list[str] = field(default_factory=list)


def _keyword_priority(event_summary: str, asset_title: str, asset_ipc: str) -> str:
    record = {_TITLE_FIELD: asset_title, _IPC_FIELD: asset_ipc}
    result = calculate_relevance(event_summary, record)
    return str(result[PRIORITY_FIELD])


def _base_outcome(keyword_priority: str, llm_result: ClassificationResult | None) -> str:
    if llm_result is not None:
        return TRIAGE_RELATED if llm_result.label == LABEL_RELEVANT else TRIAGE_UNRELATED
    if keyword_priority == PRIORITY_HIGH:
        return TRIAGE_RELATED
    if keyword_priority == PRIORITY_LOW:
        return TRIAGE_UNRELATED
    return TRIAGE_AMBIGUOUS  # 중간 밴드이고 LLM도 없으면 아무것도 확인해주지 않은 셈


def _signal_disagreement(keyword_priority: str, llm_result: ClassificationResult | None) -> str | None:
    if llm_result is None:
        return None
    if keyword_priority == PRIORITY_HIGH and llm_result.label == LABEL_UNRELATED:
        return "신호 불일치: 키워드/IPC 점수는 높음인데 LLM은 무관으로 판정"
    if keyword_priority == PRIORITY_LOW and llm_result.label == LABEL_RELEVANT:
        return "신호 불일치: 키워드/IPC 점수는 낮음인데 LLM은 관련으로 판정"
    return None


def _mid_confidence(llm_result: ClassificationResult | None) -> str | None:
    if llm_result is None:
        return None
    low, high = MID_CONFIDENCE_RANGE
    if low <= llm_result.confidence <= high:
        return f"확신도 중간대: LLM confidence={llm_result.confidence}"
    return None


def _missing_info(event_occurred_at: str | None, llm_result: ClassificationResult | None) -> str | None:
    gaps = []
    if not event_occurred_at:
        gaps.append("사건 발생/공개 시각 없음")
    if llm_result is not None and llm_result.missing_info:
        gaps.append("LLM이 부족한 정보 지적: " + "; ".join(llm_result.missing_info))
    if not gaps:
        return None
    return "필수 정보 누락: " + " / ".join(gaps)


def _high_risk_event_type(event_type: str) -> str | None:
    if event_type in HIGH_RISK_EVENT_TYPES:
        return f"고위험 사건 유형: {event_type}"
    return None


def _past_judgment_conflict(conn: sqlite3.Connection, application_number: str, base_outcome: str) -> str | None:
    if not application_number:
        return None
    judgments = fetch_judgments_for_application(conn, application_number)
    if not judgments:
        return None
    latest_decision = judgments[0]["decision"]
    if base_outcome == TRIAGE_RELATED and latest_decision in _NO_ACTION_DECISIONS:
        return f"과거 판단과 충돌: 이전 판단은 '{latest_decision}'(조치 불필요)인데 이번엔 관련으로 보임"
    if base_outcome == TRIAGE_UNRELATED and latest_decision in _ACTION_DECISIONS:
        return f"과거 판단과 충돌: 이전 판단은 '{latest_decision}'(조치 필요)인데 이번엔 무관으로 보임"
    return None


def decide_triage(
    conn: sqlite3.Connection,
    *,
    event_type: str,
    event_summary: str,
    event_occurred_at: str | None,
    asset_title: str,
    asset_ipc: str,
    application_number: str,
    llm_result: ClassificationResult | None = None,
) -> TriageDecision:
    """Combine the available signals into one 무관/관련/애매 decision.

    ``llm_result`` is optional — pass None to route on the keyword/IPC
    signal alone (no LLM call made). A medium keyword/IPC band with no LLM
    result always routes to 애매, since nothing confirmed it either way.
    """
    keyword_priority = _keyword_priority(event_summary, asset_title, asset_ipc)
    base_outcome = _base_outcome(keyword_priority, llm_result)

    reasons = [
        reason
        for reason in (
            _signal_disagreement(keyword_priority, llm_result),
            _mid_confidence(llm_result),
            _missing_info(event_occurred_at, llm_result),
            _high_risk_event_type(event_type),
            _past_judgment_conflict(conn, application_number, base_outcome),
        )
        if reason is not None
    ]
    if base_outcome == TRIAGE_AMBIGUOUS and not reasons:
        reasons.append("키워드/IPC 점수가 중간대이고 LLM 판정이 없어 판단 보류")

    if reasons:
        return TriageDecision(outcome=TRIAGE_AMBIGUOUS, reasons=reasons)
    return TriageDecision(outcome=base_outcome, reasons=[])

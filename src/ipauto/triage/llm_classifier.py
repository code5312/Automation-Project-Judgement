"""LLM structured relevance classification (docs/DESIGN.md 트리아지, 단계 3).

One signal among the four docs/DESIGN.md 트리아지 names (IPC 주신호, 개념
키워드, 임베딩 유사도는 각각 다른 모듈/단계 작업; 이 모듈은 "LLM 구조화
판정"만 담당한다). ``classify`` builds a few-shot prompt, calls Claude
(``ipauto.connectors.llm``), and validates the reply against a fixed JSON
shape (label, confidence, evidence, missing_info) — a malformed reply
raises ``ClassificationFormatError`` rather than being guessed at.

Combining this signal with the other three into the actual
무관/관련/애매 routing decision is the next docs/PIPELINE.md 단계 3 item
("애매 큐 라우팅 규칙 5가지"), not this module's job.

The few-shot examples below are hand-written placeholders — docs/DESIGN.md's
plan is for real human judgment logs to replace them once enough exist
("사람이 남긴 판단 로그가 프롬프트 예시와 평가셋이 된다"). They are marked
"(가상 예시)" and invented end-to-end: no real event or patent data.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

from ipauto.connectors.llm import DEFAULT_MODEL, complete

LABEL_RELEVANT = "관련"
LABEL_UNRELATED = "무관"
LABEL_CHOICES = (LABEL_RELEVANT, LABEL_UNRELATED)

_REQUIRED_KEYS = ("label", "confidence", "evidence", "missing_info")

_SYSTEM_PROMPT = (
    "당신은 특허 IP 담당자를 보조하는 분류기다. 사건(예: 오픈소스 공개)과 "
    "비교 대상 IP 자산(자사 특허 또는 외부 특허) 1건을 받아, 이 사건이 그 "
    "IP 자산과 관련이 있는지 판단한다. 이 판단은 법률 자문이 아니며, 최종 "
    "IP 조치 결정은 항상 사람이 내린다.\n\n"
    "반드시 아래 형식의 JSON 객체 하나만 답하라. 다른 설명이나 코드펜스를 "
    "덧붙이지 마라.\n"
    '{"label": "관련" 또는 "무관", '
    '"confidence": 0.0부터 1.0 사이의 숫자, '
    '"evidence": ["판단에 쓴 사건 또는 IP 자산 원문의 인용 문장", ...], '
    '"missing_info": ["판단 확신도를 높이려면 필요한데 지금 없는 정보", ...]}'
)

# (가상 예시) — 실제 사건·특허 데이터가 아니다. docs/DESIGN.md의 계획대로
# 실제 판단 로그가 쌓이면 이 자리를 대체한다.
_FEW_SHOT_EXAMPLES = (
    {
        "event_summary": "(가상 예시) OpenBattery SDK v3.0 — 배터리 셀 온도를 실시간 모니터링하고 "
        "과열 시 자동 차단하는 오픈소스 펌웨어 공개",
        "asset_title": "(가상 예시) 배터리 셀 온도 모니터링 및 자동 차단 장치",
        "asset_ipc": "H01M 10/48",
        "response": {
            "label": "관련",
            "confidence": 0.9,
            "evidence": [
                "배터리 셀 온도를 실시간 모니터링하고 과열 시 자동 차단하는 오픈소스 펌웨어 공개",
                "배터리 셀 온도 모니터링 및 자동 차단 장치",
            ],
            "missing_info": ["공개 라이선스 종류(특허 실시권에 영향)"],
        },
    },
    {
        "event_summary": "(가상 예시) markdown-lint-cli v1.2 — 마크다운 문서 문법 검사 CLI 도구 공개",
        "asset_title": "(가상 예시) 배터리 팩",
        "asset_ipc": "H01M 50/249",
        "response": {
            "label": "무관",
            "confidence": 0.95,
            "evidence": ["마크다운 문서 문법 검사 CLI 도구 공개"],
            "missing_info": [],
        },
    },
    {
        "event_summary": "(가상 예시) EVPowerStack v0.9 — 전기차 구동계 전력 관리 소프트웨어 베타 공개, "
        "배터리 모듈 인터페이스 포함",
        "asset_title": "(가상 예시) 전기차 배터리 모듈 인터페이스 제어 방법",
        "asset_ipc": "B60L 58/21",
        "response": {
            "label": "관련",
            "confidence": 0.55,
            "evidence": ["배터리 모듈 인터페이스 포함"],
            "missing_info": [
                "소프트웨어가 제어하는 인터페이스의 구체적 프로토콜/신호 방식",
                "공개 범위(소스 전체 공개 여부)",
            ],
        },
    },
)


class ClassificationFormatError(ValueError):
    """The LLM's response did not match the required structured JSON shape."""


@dataclass(frozen=True)
class ClassificationResult:
    label: str
    confidence: float
    evidence: list[str]
    missing_info: list[str]
    raw_response: str


def _format_example(example: dict) -> str:
    return (
        f"사건 요약: {example['event_summary']}\n"
        f"비교 대상 IP 자산 제목: {example['asset_title']}\n"
        f"비교 대상 IP 자산 IPC: {example['asset_ipc']}\n"
        f"답변: {json.dumps(example['response'], ensure_ascii=False)}"
    )


def build_prompt(event_summary: str, asset_title: str, asset_ipc: str) -> str:
    examples = "\n\n".join(_format_example(example) for example in _FEW_SHOT_EXAMPLES)
    return (
        f"{examples}\n\n"
        f"사건 요약: {event_summary}\n"
        f"비교 대상 IP 자산 제목: {asset_title}\n"
        f"비교 대상 IP 자산 IPC: {asset_ipc}\n"
        "답변:"
    )


def _extract_json_object(text: str) -> dict:
    """Pull the first {...} JSON object out of text (tolerates stray prose/code fences)."""
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise ClassificationFormatError(f"No JSON object found in LLM response: {text!r}")
    try:
        parsed = json.loads(text[start : end + 1])
    except json.JSONDecodeError as exc:
        raise ClassificationFormatError(f"LLM response is not valid JSON: {text!r}") from exc
    if not isinstance(parsed, dict):
        raise ClassificationFormatError(f"LLM response JSON is not an object: {text!r}")
    return parsed


def _require_string_list(payload: dict, key: str) -> list[str]:
    value = payload[key]
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ClassificationFormatError(f"{key!r} must be a list of strings, got {value!r}")
    return value


def parse_classification(raw_response: str) -> ClassificationResult:
    """Validate and parse one LLM structured-JSON reply. Raises ClassificationFormatError."""
    payload = _extract_json_object(raw_response)

    missing_keys = [key for key in _REQUIRED_KEYS if key not in payload]
    if missing_keys:
        raise ClassificationFormatError(f"LLM response missing required key(s): {missing_keys}")

    label = payload["label"]
    if label not in LABEL_CHOICES:
        raise ClassificationFormatError(f"'label' must be one of {LABEL_CHOICES}, got {label!r}")

    confidence = payload["confidence"]
    if isinstance(confidence, bool) or not isinstance(confidence, (int, float)):
        raise ClassificationFormatError(f"'confidence' must be a number, got {confidence!r}")
    if not 0.0 <= confidence <= 1.0:
        raise ClassificationFormatError(f"'confidence' must be between 0 and 1, got {confidence!r}")

    return ClassificationResult(
        label=label,
        confidence=float(confidence),
        evidence=_require_string_list(payload, "evidence"),
        missing_info=_require_string_list(payload, "missing_info"),
        raw_response=raw_response,
    )


def classify(
    event_summary: str,
    asset_title: str,
    asset_ipc: str,
    *,
    api_key: str,
    model: str = DEFAULT_MODEL,
) -> ClassificationResult:
    """Build the few-shot prompt, call Claude, and validate its structured response.

    Raises a typed ipauto.connectors.llm.LLMError if the call itself fails,
    or ClassificationFormatError if Claude's reply doesn't match the
    required JSON shape.
    """
    prompt = build_prompt(event_summary, asset_title, asset_ipc)
    raw_response = complete(prompt, api_key=api_key, system=_SYSTEM_PROMPT, model=model)
    return parse_classification(raw_response)

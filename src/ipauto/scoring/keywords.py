"""Concept-group and generic-keyword relevance scoring.

This is a direct, Korean-readable port of the prototype's scoring logic
(previously in ``main.py`` with ``\\uXXXX``-escaped literals). Concept
groups/weights and the particle/ending suffix lists are still module
constants; moving them to ``config/concepts.yaml`` and swapping the suffix
stripping for a real morphological analyzer (kiwipiepy) is phase 2 work
(docs/PIPELINE.md 단계 2).
"""

from __future__ import annotations

import re

from ipauto.scoring import bands, ipc

SCORE_FIELD = "relevance_score"
PRIORITY_FIELD = "review_priority"
MATCHED_FIELD = "matched_concepts"
REASON_FIELD = "score_reason"
ANALYSIS_MODE_FIELD = "analysis_mode"

MODE_CONCEPT_GROUP = "concept_group"
MODE_GENERIC_KEYWORD = "generic_keyword"

GENERIC_FALLBACK_MESSAGE = (
    "사전 정의된 기술 개념 그룹이 없어 입력된 평가 기술어를 기반으로 범용 키워드 분석을 수행했습니다."
)

CONCEPT_GROUPS: dict[str, tuple[str, ...]] = {
    "vehicle": ("전기차", "전기 자동차", "차량", "자동차"),
    "battery": ("배터리",),
    "cooling": ("냉각", "열관리", "온도관리", "수냉", "냉각수", "냉매", "열교환"),
}
# Points per concept mention. Title evidence is worth more than abstract evidence.
TITLE_WEIGHTS = {"vehicle": 3, "battery": 4, "cooling": 6}
ABSTRACT_WEIGHTS = {"vehicle": 2, "battery": 2, "cooling": 3}
CORE_BOTH_BONUS = 65  # battery and cooling both found
SINGLE_CORE_BONUS = 25  # only battery or only cooling found
VEHICLE_PRESENCE_BONUS = 5
IPC_CODE_BONUS = 2  # small supplement only: configured IPC families

GENERIC_TITLE_WEIGHT = 4
GENERIC_ABSTRACT_WEIGHT = 2
GENERIC_MULTI_KEYWORD_BONUS = 3
GENERIC_IPC_WEIGHT = 1

KOREAN_PARTICLES = (
    "으로부터",
    "에게서",
    "에서는",
    "으로",
    "에게",
    "한테",
    "부터",
    "까지",
    "처럼",
    "보다",
    "이랑",
    "하고",
    "이나",
    "라도",
    "마저",
    "조차",
    "은",
    "는",
    "이",
    "가",
    "을",
    "를",
    "의",
    "에",
    "로",
    "와",
    "과",
    "도",
    "만",
    "랑",
    "께",
)
KOREAN_VERB_ENDINGS = (
    "하여서",
    "하면서",
    "하는",
    "하기",
    "하며",
    "하고",
    "한다",
    "된다",
    "되는",
    "되고",
    "하여",
    "함",
)
GENERIC_STOPWORDS = {
    "기술",
    "방법",
    "시스템",
    "장치",
    "구조",
    "관련",
    "분야",
    "위한",
    "대한",
    "통한",
    "특허",
    "및",
    "또는",
    "그리고",
    "등",
    "각",
    "본",
    "여러",
}


def _has_phrase(text: str, phrase: str) -> bool:
    """Match a listed concept phrase literally; no fuzzy/partial-character matching."""
    return phrase.casefold() in text.casefold()


def extract_generic_keywords(technology: str) -> list[str]:
    """Extract distinct, useful literal terms when no configured group applies."""
    raw_terms = re.findall(r"[\w]+", technology.casefold(), flags=re.UNICODE)
    keywords: list[str] = []
    for raw in raw_terms:
        term = raw
        for suffix in (*KOREAN_VERB_ENDINGS, *KOREAN_PARTICLES):
            if term.endswith(suffix) and len(term) - len(suffix) >= 2:
                term = term[: -len(suffix)]
                break
        if len(term) < 2 or term in GENERIC_STOPWORDS:
            continue
        if not re.search(r"[A-Za-z가-힣]", term, flags=re.UNICODE):
            continue
        if term not in keywords:
            keywords.append(term)
    return keywords


def _generic_relevance(technology: str, title: str, abstract: str, ipc_value: str) -> dict[str, str | float]:
    keywords = extract_generic_keywords(technology)
    if not keywords:
        return {
            SCORE_FIELD: 0.0,
            PRIORITY_FIELD: bands.classify(0, bands.GENERIC_PRIORITY_HIGH_MIN, bands.GENERIC_PRIORITY_MEDIUM_MIN),
            MATCHED_FIELD: "",
            REASON_FIELD: "의미 있는 키워드를 추출하지 못해 0점 처리",
            ANALYSIS_MODE_FIELD: MODE_GENERIC_KEYWORD,
        }

    folded_title = title.casefold()
    folded_abstract = abstract.casefold()
    title_hits = [word for word in keywords if word in folded_title]
    abstract_hits = [word for word in keywords if word in folded_abstract]
    found = list(dict.fromkeys([*title_hits, *abstract_hits]))
    ipc_hits = ipc.detected_families(ipc_value)

    points = len(title_hits) * GENERIC_TITLE_WEIGHT
    points += len(abstract_hits) * GENERIC_ABSTRACT_WEIGHT
    multi_bonus = GENERIC_MULTI_KEYWORD_BONUS if len(found) >= 2 else 0
    points += multi_bonus
    points += len(ipc_hits) * GENERIC_IPC_WEIGHT

    maximum = len(keywords) * (GENERIC_TITLE_WEIGHT + GENERIC_ABSTRACT_WEIGHT)
    maximum += GENERIC_MULTI_KEYWORD_BONUS if len(keywords) >= 2 else 0
    maximum += 2 * GENERIC_IPC_WEIGHT
    score = round(100 * points / maximum, 1) if maximum else 0.0

    reasons = []
    if title_hits:
        reasons.append("제목 키워드: " + "·".join(title_hits))
    if abstract_hits:
        reasons.append("초록 키워드: " + "·".join(abstract_hits))
    if multi_bonus:
        reasons.append("복수 키워드 동시 발견 (+3점)")
    if ipc_hits:
        reasons.append("IPC 보조 확인: " + "/".join(ipc_hits))
    if not reasons:
        reasons.append("제목·초록에서 키워드를 찾지 못함")

    return {
        SCORE_FIELD: score,
        PRIORITY_FIELD: bands.classify(score, bands.GENERIC_PRIORITY_HIGH_MIN, bands.GENERIC_PRIORITY_MEDIUM_MIN),
        MATCHED_FIELD: ";".join(found),
        REASON_FIELD: ", ".join(reasons),
        ANALYSIS_MODE_FIELD: MODE_GENERIC_KEYWORD,
    }


def calculate_relevance(technology: str, record: dict[str, str]) -> dict[str, str | float]:
    """Return score, priority, matched concepts, and a human-readable explanation."""
    target_concepts = {
        concept
        for concept, phrases in CONCEPT_GROUPS.items()
        if any(_has_phrase(technology, phrase) for phrase in phrases)
    }
    title = record.get("발명의 명칭", "") or ""
    abstract = record.get("초록", "") or ""
    ipc_value = record.get("IPC", "") or ""

    if not target_concepts:
        return _generic_relevance(technology, title, abstract, ipc_value)

    title_hits: set[str] = set()
    abstract_hits: set[str] = set()
    for concept, phrases in CONCEPT_GROUPS.items():
        if concept not in target_concepts:
            continue
        if any(_has_phrase(title, phrase) for phrase in phrases):
            title_hits.add(concept)
        if any(_has_phrase(abstract, phrase) for phrase in phrases):
            abstract_hits.add(concept)

    found_concepts = title_hits | abstract_hits
    detected_ipc = ipc.detected_families(ipc_value)
    ipc_hits = [
        code
        for code in detected_ipc
        if (code == "H01M" and "battery" in target_concepts) or (code == "B60L" and "vehicle" in target_concepts)
    ]

    score = sum(TITLE_WEIGHTS[c] for c in title_hits)
    score += sum(ABSTRACT_WEIGHTS[c] for c in abstract_hits)
    has_battery = "battery" in found_concepts
    has_cooling = "cooling" in found_concepts
    has_vehicle = "vehicle" in found_concepts
    if has_battery and has_cooling:
        score += CORE_BOTH_BONUS
    elif has_battery or has_cooling:
        score += SINGLE_CORE_BONUS
    if has_vehicle:
        score += VEHICLE_PRESENCE_BONUS
    score += IPC_CODE_BONUS * len(ipc_hits)
    score = float(min(score, 100))

    concept_order = ("vehicle", "battery", "cooling")
    matched = [concept for concept in concept_order if concept in found_concepts]
    matched.extend(f"IPC:{code}" for code in ipc_hits)

    concept_names = {"vehicle": "차량", "battery": "배터리", "cooling": "냉각"}
    reasons = []
    if has_battery and has_cooling:
        reasons.append("배터리·냉각 개념 모두 확인")
    elif has_battery:
        reasons.append("배터리 개념 확인")
    elif has_cooling:
        reasons.append("냉각 개념 확인")
    if has_vehicle:
        reasons.append("차량 개념 확인")
    title_names = [concept_names[c] for c in concept_order if c in title_hits]
    abstract_names = [concept_names[c] for c in concept_order if c in abstract_hits]
    if title_names:
        reasons.append("제목에서 " + "·".join(title_names) + " 발견")
    if abstract_names:
        reasons.append("초록에서 " + "·".join(abstract_names) + " 발견")
    if ipc_hits:
        reasons.append("/".join(ipc_hits) + " IPC 확인")
    if not reasons:
        reasons.append("평가 개념을 제목·초록·IPC에서 찾지 못함")

    return {
        SCORE_FIELD: score,
        PRIORITY_FIELD: bands.classify(score, bands.CONCEPT_PRIORITY_HIGH_MIN, bands.CONCEPT_PRIORITY_MEDIUM_MIN),
        MATCHED_FIELD: ";".join(matched),
        REASON_FIELD: ", ".join(reasons),
        ANALYSIS_MODE_FIELD: MODE_CONCEPT_GROUP,
    }


def rank_records(technology: str, records: list[dict[str, str]]) -> list[dict[str, str | float]]:
    """Add assessment fields and sort by score descending (stable ties)."""
    ranked = []
    for record in records:
        result = dict(record)
        result.update(calculate_relevance(technology, result))
        ranked.append(result)
    return sorted(ranked, key=lambda record: float(record[SCORE_FIELD]), reverse=True)

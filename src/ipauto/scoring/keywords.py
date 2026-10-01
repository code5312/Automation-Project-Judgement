"""Concept-group and generic-keyword relevance scoring.

This is a direct, Korean-readable port of the prototype's scoring logic
(previously in ``main.py`` with ``\\uXXXX``-escaped literals). Concept
groups, weights, and bonuses are loaded from ``config/concepts.yaml`` via
``ipauto.scoring.rules`` (docs/PIPELINE.md 단계 2).

``extract_generic_keywords`` uses kiwipiepy for real morphological analysis
instead of stripping a fixed list of particle/ending suffixes by regex — a
suffix like "은/는/이/가" or "하여/하고" is just whatever the analyzer leaves
after splitting off its own NNG/NNP/SL-tagged content morphemes, not a
pattern matched in code.
"""

from __future__ import annotations

from kiwipiepy import Kiwi

from ipauto.scoring import bands, ipc, rules

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

# Content-bearing part-of-speech tags to keep: common/proper nouns and
# foreign-script tokens (e.g. English terms written in Latin letters).
# Particles, verb/adjective endings, numerals, and symbols are dropped by
# virtue of not being in this set.
_CONTENT_POS_TAGS = frozenset({"NNG", "NNP", "SL"})

# Loading the morphological model takes real time, so load it once per
# process instead of per call.
_KIWI = Kiwi()


def _has_phrase(text: str, phrase: str) -> bool:
    """Match a listed concept phrase literally; no fuzzy/partial-character matching."""
    return phrase.casefold() in text.casefold()


def extract_generic_keywords(technology: str) -> list[str]:
    """Extract distinct, useful terms when no configured group applies."""
    keywords: list[str] = []
    for token in _KIWI.tokenize(technology):
        if token.tag not in _CONTENT_POS_TAGS:
            continue
        term = token.form.casefold()
        if len(term) < 2 or term in GENERIC_STOPWORDS:
            continue
        if term not in keywords:
            keywords.append(term)
    return keywords


def _generic_relevance(technology: str, title: str, abstract: str, ipc_value: str) -> dict[str, str | float]:
    concept_rules = rules.get_concept_rules()
    keywords = extract_generic_keywords(technology)
    if not keywords:
        return {
            SCORE_FIELD: 0.0,
            PRIORITY_FIELD: bands.classify(
                0, concept_rules.generic_priority_high_min, concept_rules.generic_priority_medium_min
            ),
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

    points = len(title_hits) * concept_rules.generic_title_weight
    points += len(abstract_hits) * concept_rules.generic_abstract_weight
    multi_bonus = concept_rules.generic_multi_keyword_bonus if len(found) >= 2 else 0
    points += multi_bonus
    points += len(ipc_hits) * concept_rules.generic_ipc_weight

    maximum = len(keywords) * (concept_rules.generic_title_weight + concept_rules.generic_abstract_weight)
    maximum += concept_rules.generic_multi_keyword_bonus if len(keywords) >= 2 else 0
    maximum += 2 * concept_rules.generic_ipc_weight
    score = round(100 * points / maximum, 1) if maximum else 0.0

    reasons = []
    if title_hits:
        reasons.append("제목 키워드: " + "·".join(title_hits))
    if abstract_hits:
        reasons.append("초록 키워드: " + "·".join(abstract_hits))
    if multi_bonus:
        reasons.append(f"복수 키워드 동시 발견 (+{multi_bonus}점)")
    if ipc_hits:
        reasons.append("IPC 보조 확인: " + "/".join(ipc_hits))
    if not reasons:
        reasons.append("제목·초록에서 키워드를 찾지 못함")

    return {
        SCORE_FIELD: score,
        PRIORITY_FIELD: bands.classify(
            score, concept_rules.generic_priority_high_min, concept_rules.generic_priority_medium_min
        ),
        MATCHED_FIELD: ";".join(found),
        REASON_FIELD: ", ".join(reasons),
        ANALYSIS_MODE_FIELD: MODE_GENERIC_KEYWORD,
    }


def calculate_relevance(technology: str, record: dict[str, str]) -> dict[str, str | float]:
    """Return score, priority, matched concepts, and a human-readable explanation."""
    concept_rules = rules.get_concept_rules()
    concept_groups = concept_rules.concept_groups
    target_concepts = {
        concept
        for concept, phrases in concept_groups.items()
        if any(_has_phrase(technology, phrase) for phrase in phrases)
    }
    title = record.get("발명의 명칭", "") or ""
    abstract = record.get("초록", "") or ""
    ipc_value = record.get("IPC", "") or ""

    if not target_concepts:
        return _generic_relevance(technology, title, abstract, ipc_value)

    title_hits: set[str] = set()
    abstract_hits: set[str] = set()
    for concept, phrases in concept_groups.items():
        if concept not in target_concepts:
            continue
        if any(_has_phrase(title, phrase) for phrase in phrases):
            title_hits.add(concept)
        if any(_has_phrase(abstract, phrase) for phrase in phrases):
            abstract_hits.add(concept)

    found_concepts = title_hits | abstract_hits
    detected_ipc = ipc.detected_families(ipc_value)
    concept_family_map = rules.get_ipc_rules().concept_family_map
    ipc_hits = [
        code
        for concept, code in concept_family_map.items()
        if concept in target_concepts and code in detected_ipc
    ]
    primary_hits = [
        code for code, concept in ipc.detected_primary_signals(ipc_value) if concept in target_concepts
    ]

    score = sum(concept_rules.title_weights[c] for c in title_hits)
    score += sum(concept_rules.abstract_weights[c] for c in abstract_hits)
    has_battery = "battery" in found_concepts
    has_cooling = "cooling" in found_concepts
    has_vehicle = "vehicle" in found_concepts
    if has_battery and has_cooling:
        score += concept_rules.core_both_bonus
    elif has_battery or has_cooling:
        score += concept_rules.single_core_bonus
    if has_vehicle:
        score += concept_rules.vehicle_presence_bonus
    score += concept_rules.ipc_code_bonus * len(ipc_hits)
    score += concept_rules.primary_ipc_bonus * len(primary_hits)
    score = float(min(score, 100))

    concept_order = ("vehicle", "battery", "cooling")
    matched = [concept for concept in concept_order if concept in found_concepts]
    matched.extend(f"IPC:{code}" for code in ipc_hits)
    matched.extend(f"IPC-주신호:{code}" for code in primary_hits)

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
    if primary_hits:
        reasons.append("IPC 세부분류로 정밀 확인: " + "/".join(primary_hits))
    if not reasons:
        reasons.append("평가 개념을 제목·초록·IPC에서 찾지 못함")

    return {
        SCORE_FIELD: score,
        PRIORITY_FIELD: bands.classify(
            score, concept_rules.concept_priority_high_min, concept_rules.concept_priority_medium_min
        ),
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

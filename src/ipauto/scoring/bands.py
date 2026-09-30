"""Human-facing review-priority bands.

The design (docs/DESIGN.md 검색·점수 설계) calls for a 3-band 높음/중간/낮음
display with no 100-point number shown to the user; the numeric score stays
internal and is only used for sorting. The UI layer decides what to show,
this module only classifies.
"""

from __future__ import annotations

PRIORITY_HIGH = "검토 우선순위 높음"
PRIORITY_MEDIUM = "검토 우선순위 보통"
PRIORITY_LOW = "검토 우선순위 낮음"

# Concept-group and generic-keyword scoring do not share thresholds (design
# doc: "임계값(70/40)을 공유하지 않고 각각 따로 정한 뒤, 평가 세트로 조정한다").
# Phase 0 keeps both modes on the same starting bands; phase 2 splits and
# tunes them against the evaluation set.
CONCEPT_PRIORITY_HIGH_MIN = 70
CONCEPT_PRIORITY_MEDIUM_MIN = 40

GENERIC_PRIORITY_HIGH_MIN = 70
GENERIC_PRIORITY_MEDIUM_MIN = 40


def classify(score: float, high_min: float, medium_min: float) -> str:
    """Map a 0-100 score to a review-priority band using the given thresholds."""
    if score >= high_min:
        return PRIORITY_HIGH
    if score >= medium_min:
        return PRIORITY_MEDIUM
    return PRIORITY_LOW

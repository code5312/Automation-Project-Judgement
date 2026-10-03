"""Tests for triage re-measurement against the evaluation set (docs/PIPELINE.md 단계 3).

Uses small invented records (not real patents), matching the style of
tests/test_evaluation.py.
"""

from __future__ import annotations

from ipauto.evaluation import EvalItem
from ipauto.scoring.bands import PRIORITY_HIGH, PRIORITY_LOW, PRIORITY_MEDIUM
from ipauto.triage.evaluation import measure_triage_accuracy
from ipauto.triage.routing import TRIAGE_AMBIGUOUS, TRIAGE_RELATED, TRIAGE_UNRELATED

_TECHNOLOGY = "전기차 배터리 냉각"

_HIGH_RECORD = {
    "발명의 명칭": "전기차 배터리 냉각 장치",
    "출원번호": "SAMPLE-EVAL-0000001",
    "IPC": "H01M 10/613",
}

_LOW_RECORD = {
    "발명의 명칭": "샘플 무관 반도체 장치",
    "출원번호": "SAMPLE-EVAL-0000002",
    "IPC": "G06F 1/20",
}

# vehicle+battery text only (no cooling) lands in the medium band without
# an abstract, same fixture used by tests/test_triage_routing.py.
_MEDIUM_RECORD = {
    "발명의 명칭": "전기차 배터리 시스템",
    "출원번호": "SAMPLE-EVAL-0000003",
    "IPC": "H01M 10/42|B60L 50/50",
}


def _item(record: dict, human_label: str, application_number: str | None = None) -> EvalItem:
    return EvalItem(
        application_number=application_number or record["출원번호"],
        title=record["발명의 명칭"],
        record=record,
        review_technology=_TECHNOLOGY,
        human_label=human_label,
        rationale="테스트용 가상 근거",
    )


def test_measure_triage_accuracy_maps_bands_to_outcomes_correctly():
    items = [
        _item(_HIGH_RECORD, PRIORITY_HIGH),
        _item(_LOW_RECORD, PRIORITY_LOW),
        _item(_MEDIUM_RECORD, PRIORITY_MEDIUM),
    ]

    result = measure_triage_accuracy(items)

    assert result.total == 3
    assert result.correct == 3
    assert result.accuracy == 1.0
    assert result.outcome_counts == {TRIAGE_RELATED: 1, TRIAGE_UNRELATED: 1, TRIAGE_AMBIGUOUS: 1}
    assert result.ambiguous_rate == 1 / 3
    assert result.mismatches == []


def test_measure_triage_accuracy_reports_mismatches_with_expected_and_actual():
    # Human says this is only medium relevance, but the keyword/IPC scorer
    # (title+IPC only, no abstract — matching the real ip_asset schema)
    # rates it as clearly relevant, so the mapped outcomes disagree.
    items = [_item(_HIGH_RECORD, PRIORITY_MEDIUM)]

    result = measure_triage_accuracy(items)

    assert result.correct == 0
    assert len(result.mismatches) == 1
    item, expected, actual = result.mismatches[0]
    assert expected == TRIAGE_AMBIGUOUS
    assert actual == TRIAGE_RELATED


def test_measure_triage_accuracy_is_isolated_across_items_with_same_application_number():
    # Two items that happen to reuse an application_number must not let a
    # (non-existent) past Judgment from one leak into the other's routing —
    # here neither has any stored Judgment, so rule 5 must stay inert for both.
    items = [
        _item(_HIGH_RECORD, PRIORITY_HIGH, application_number="SAMPLE-SHARED"),
        _item(_LOW_RECORD, PRIORITY_LOW, application_number="SAMPLE-SHARED"),
    ]

    result = measure_triage_accuracy(items)

    assert result.correct == 2
    assert result.mismatches == []


def test_measure_triage_accuracy_handles_empty_list():
    result = measure_triage_accuracy([])

    assert result.total == 0
    assert result.accuracy == 0.0
    assert result.ambiguous_rate == 0.0

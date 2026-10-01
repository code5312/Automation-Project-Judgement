"""Tests for evaluation-set accuracy measurement (docs/PIPELINE.md 단계 2).

Uses small invented records (filenames/content are not real KIPRIS data),
not the real labeled set under data/eval/ — that file's own README explains
its labels are an unreviewed AI draft, which is out of scope for unit tests.
"""

from __future__ import annotations

import json

from ipauto.evaluation import load_eval_set, measure_accuracy
from ipauto.scoring.bands import PRIORITY_HIGH, PRIORITY_LOW

_TECHNOLOGY = "전기차 배터리 냉각"

_HIGH_RECORD = {
    "발명의 명칭": "전기차 배터리 냉각 장치",
    "출원번호": "SAMPLE-EVAL-0000001",
    "출원인": "샘플 주식회사",
    "IPC": "H01M 10/613",
    "등록상태": "공개(샘플)",
    "초록": "전기차 배터리를 냉각수로 냉각하는 장치에 대한 가상의 설명입니다.",
}

_LOW_RECORD = {
    "발명의 명칭": "샘플 무관 반도체 장치",
    "출원번호": "SAMPLE-EVAL-0000002",
    "출원인": "샘플 주식회사",
    "IPC": "G06F 1/20",
    "등록상태": "등록(샘플)",
    "초록": "샘플 반도체 공정 최적화에 대한 가상의 설명입니다.",
}


def _write_eval_set(tmp_path, entries):
    path = tmp_path / "eval_set.json"
    path.write_text(json.dumps(entries, ensure_ascii=False), encoding="utf-8")
    return path


def _entry(record, label, rationale="테스트용 가상 근거"):
    return {**record, "review_technology": _TECHNOLOGY, "human_label": label, "label_rationale": rationale}


def test_load_eval_set_maps_korean_labels_to_priority_bands(tmp_path):
    path = _write_eval_set(tmp_path, [_entry(_HIGH_RECORD, "높음"), _entry(_LOW_RECORD, "낮음")])

    items = load_eval_set(path)

    assert [item.human_label for item in items] == [PRIORITY_HIGH, PRIORITY_LOW]
    assert items[0].application_number == "SAMPLE-EVAL-0000001"
    assert items[0].record["초록"] == _HIGH_RECORD["초록"]


def test_load_eval_set_rejects_unknown_label(tmp_path):
    path = _write_eval_set(tmp_path, [_entry(_HIGH_RECORD, "매우높음")])

    try:
        load_eval_set(path)
        raised = False
    except ValueError:
        raised = True
    assert raised


def test_measure_accuracy_reports_correct_and_mismatched_predictions(tmp_path):
    # The high record's human_label agrees with the scorer; flip the low
    # record's label on purpose to exercise the mismatch/confusion path.
    path = _write_eval_set(
        tmp_path,
        [_entry(_HIGH_RECORD, "높음"), _entry(_LOW_RECORD, "높음", "일부러 틀리게 표시한 라벨")],
    )
    items = load_eval_set(path)

    result = measure_accuracy(items)

    assert result.total == 2
    assert result.correct == 1
    assert result.accuracy == 0.5
    assert len(result.mismatches) == 1
    mismatched_item, predicted = result.mismatches[0]
    assert mismatched_item.application_number == "SAMPLE-EVAL-0000002"
    assert predicted == PRIORITY_LOW
    assert confusion_total(result.confusion) == 2


def confusion_total(confusion: dict) -> int:
    return sum(confusion.values())

"""Evaluation-set accuracy measurement (docs/PIPELINE.md 단계 2).

Compares the scorer's current review_priority against a labeled evaluation
set and reports accuracy plus a confusion matrix. The evaluation set itself
(data/eval/*.json) must be real KIPRIS records — never fabricated patent
data (README.md "가짜 특허 데이터를 생성하지 않으며"). Whether the labels in
a given file are a validated human judgment or an unreviewed AI draft is a
property of that file, not of this module; see each file's own metadata.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from ipauto.scoring.bands import PRIORITY_HIGH, PRIORITY_LOW, PRIORITY_MEDIUM
from ipauto.scoring.keywords import PRIORITY_FIELD, calculate_relevance

LABEL_TO_PRIORITY = {
    "높음": PRIORITY_HIGH,
    "보통": PRIORITY_MEDIUM,
    "낮음": PRIORITY_LOW,
}

RECORD_FIELDS = ("발명의 명칭", "출원번호", "출원인", "IPC", "등록상태", "초록")


@dataclass(frozen=True)
class EvalItem:
    application_number: str
    title: str
    record: dict[str, str]
    review_technology: str
    human_label: str
    rationale: str


@dataclass(frozen=True)
class EvalResult:
    total: int
    correct: int
    confusion: dict[tuple[str, str], int]  # (human_label, predicted) -> count
    mismatches: list[tuple[EvalItem, str]]  # (item, predicted)

    @property
    def accuracy(self) -> float:
        return self.correct / self.total if self.total else 0.0


def load_eval_set(path: Path) -> list[EvalItem]:
    """Load a labeled evaluation set. Raises KeyError/ValueError on a malformed entry."""
    raw = json.loads(path.read_text(encoding="utf-8"))
    items = []
    for entry in raw:
        label = entry["human_label"]
        if label not in LABEL_TO_PRIORITY:
            app_no = entry.get("출원번호")
            raise ValueError(f"Unknown human_label {label!r} for {app_no}; expected one of 높음/보통/낮음")
        record = {field: entry.get(field, "") for field in RECORD_FIELDS}
        items.append(
            EvalItem(
                application_number=entry["출원번호"],
                title=entry["발명의 명칭"],
                record=record,
                review_technology=entry["review_technology"],
                human_label=LABEL_TO_PRIORITY[label],
                rationale=entry.get("label_rationale", ""),
            )
        )
    return items


def measure_accuracy(items: list[EvalItem]) -> EvalResult:
    """Score every item with the current scorer and compare to its human_label."""
    correct = 0
    confusion: dict[tuple[str, str], int] = {}
    mismatches: list[tuple[EvalItem, str]] = []
    for item in items:
        result = calculate_relevance(item.review_technology, item.record)
        predicted = str(result[PRIORITY_FIELD])
        key = (item.human_label, predicted)
        confusion[key] = confusion.get(key, 0) + 1
        if predicted == item.human_label:
            correct += 1
        else:
            mismatches.append((item, predicted))
    return EvalResult(total=len(items), correct=correct, confusion=confusion, mismatches=mismatches)

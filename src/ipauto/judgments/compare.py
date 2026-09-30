"""Compare a freshly fetched KIPRIS record against a judgment's stored premises.

IPC and 출원인 are compared as sets (docs/DESIGN.md 설계 규칙: "비교는 집합
비교로 하고"), so reordering the same values is not reported as a change.
Every other premise falls back to a normalized string comparison.
"""

from __future__ import annotations

import re
import sqlite3

from ipauto.judgments.service import APPLICANT_FIELD, IPC_FIELD

SET_COMPARISON_CHECK_KEYS = {IPC_FIELD, APPLICANT_FIELD}
_SPLIT_PATTERN = re.compile(r"[|,;]")


def _normalized(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _as_set(value: str) -> set[str]:
    return {part.strip() for part in _SPLIT_PATTERN.split(value) if part.strip()}


def _values_differ(check_key: str, previous: str, current: str) -> bool:
    if check_key in SET_COMPARISON_CHECK_KEYS:
        return _as_set(previous) != _as_set(current)
    return _normalized(previous) != _normalized(current)


def compare_with_premises(record: dict[str, str | float], premises: list[sqlite3.Row]) -> list[tuple[str, str, str]]:
    """Return (check_key, expected_value, current_value) for every changed premise."""
    differences = []
    for premise in premises:
        check_key = premise["check_key"]
        expected_value = premise["expected_value"]
        current_value = _normalized(record.get(check_key))
        if _values_differ(check_key, expected_value, current_value):
            differences.append((check_key, expected_value, current_value))
    return differences

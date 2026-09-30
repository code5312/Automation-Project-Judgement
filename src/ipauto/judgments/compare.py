"""Compare a freshly fetched KIPRIS record against the latest saved judgment.

Field access uses the named constants from ``judgments.service``, not tuple
indices. Comparison here is still a normalized string comparison; switching
IPC/출원인 to a true set comparison (so reordering the same values does not
read as a change) is phase 1 scope (docs/DESIGN.md 설계 규칙).
"""

from __future__ import annotations

import re

from ipauto.judgments.service import APPLICANT_FIELD, IPC_FIELD, STATUS_FIELD

CHANGE_FIELDS = (
    ("registerStatusAtDecision", STATUS_FIELD, "등록상태"),
    ("applicantNameAtDecision", APPLICANT_FIELD, "출원인"),
    ("ipcNumberAtDecision", IPC_FIELD, "IPC"),
)


def _normalized(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def compare_with_latest(
    record: dict[str, str | float], history: list[dict[str, str | float]]
) -> list[tuple[str, str, str]]:
    """Return (display_name, previous, current) for every field that changed."""
    if not history:
        return []
    latest = max(history, key=lambda entry: str(entry.get("decisionTime", "")))
    differences = []
    for stored_key, current_key, display_name in CHANGE_FIELDS:
        previous = _normalized(latest.get(stored_key))
        current = _normalized(record.get(current_key))
        if previous != current:
            differences.append((display_name, previous, current))
    return differences

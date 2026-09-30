"""Append-only local judgment history (data/judgments.json).

This keeps the prototype's JSON storage for phase 0; phase 1 moves the same
shape into a SQLite ``Judgment`` table. A blank reason is rejected here
before it ever reaches disk, matching docs/PIPELINE.md 단계 0's
"사유 공백 저장 차단" requirement.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

TITLE_FIELD = "발명의 명칭"
APPLICATION_FIELD = "출원번호"
APPLICANT_FIELD = "출원인"
IPC_FIELD = "IPC"
STATUS_FIELD = "등록상태"

REVIEW_CHOICES = ("관련 있음", "관련 없음", "추가 검토")

DATA_DIR = Path(__file__).resolve().parents[3] / "data"
JUDGMENTS_PATH = DATA_DIR / "judgments.json"

_READ_ERROR_MESSAGE = "data/judgments.json을 읽지 못했습니다. 파일이 손상되지 않았는지 확인해주세요."
_FORMAT_ERROR_MESSAGE = (
    "data/judgments.json 형식이 올바르지 않습니다. 기존 판단 기록을 유지하기 위해 자동 저장을 중단합니다."
)


class JudgmentStoreError(RuntimeError):
    """The judgment history file could not be read or is malformed."""


def load_judgments(path: Path = JUDGMENTS_PATH) -> list[dict[str, str | float]]:
    """Load judgment history. Never silently replaces a bad file with an empty one."""
    if not path.exists():
        return []
    try:
        with path.open("r", encoding="utf-8") as source:
            data = json.load(source)
    except OSError as exc:
        raise JudgmentStoreError(_READ_ERROR_MESSAGE) from exc
    except json.JSONDecodeError as exc:
        raise JudgmentStoreError(_FORMAT_ERROR_MESSAGE) from exc
    if not isinstance(data, list):
        raise JudgmentStoreError(_FORMAT_ERROR_MESSAGE)
    return [entry for entry in data if isinstance(entry, dict)]


def save_judgment(
    record: dict[str, str | float],
    decision: str,
    reason: str,
    score_field: str,
    priority_field: str,
    path: Path = JUDGMENTS_PATH,
) -> dict[str, str | float]:
    """Append one human decision. Rejects a blank reason before writing anything."""
    if decision not in REVIEW_CHOICES:
        raise ValueError(f"decision must be one of {REVIEW_CHOICES}.")
    reason = reason.strip()
    if not reason:
        raise ValueError("판단 이유는 비어 있을 수 없습니다.")

    history = load_judgments(path)
    entry: dict[str, str | float] = {
        "applicationNumber": str(record.get(APPLICATION_FIELD) or ""),
        "inventionTitle": str(record.get(TITLE_FIELD) or ""),
        "decision": decision,
        "decisionReason": reason,
        "decisionTime": datetime.now().astimezone().isoformat(timespec="seconds"),
        "registerStatusAtDecision": str(record.get(STATUS_FIELD) or ""),
        "applicantNameAtDecision": str(record.get(APPLICANT_FIELD) or ""),
        "ipcNumberAtDecision": str(record.get(IPC_FIELD) or ""),
        "relevanceScoreAtDecision": float(record.get(score_field) or 0),
        "reviewPriorityAtDecision": str(record.get(priority_field) or ""),
    }
    history.append(entry)

    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_suffix(".json.tmp")
    with temporary_path.open("w", encoding="utf-8") as destination:
        json.dump(history, destination, ensure_ascii=False, indent=2)
        destination.write("\n")
    temporary_path.replace(path)
    return entry

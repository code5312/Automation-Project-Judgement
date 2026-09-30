"""Tests for comparing a current record against the latest saved judgment."""

from __future__ import annotations

from ipauto.judgments.compare import compare_with_latest

HISTORY = [
    {
        "decisionTime": "2026-01-01T00:00:00+09:00",
        "registerStatusAtDecision": "공개(샘플)",
        "applicantNameAtDecision": "샘플대학교",
        "ipcNumberAtDecision": "H01M 10/613",
    },
    {
        "decisionTime": "2026-02-01T00:00:00+09:00",
        "registerStatusAtDecision": "등록(샘플)",
        "applicantNameAtDecision": "샘플대학교",
        "ipcNumberAtDecision": "H01M 10/613",
    },
]


def test_compare_with_latest_returns_empty_when_no_history():
    assert compare_with_latest({"등록상태": "공개(샘플)"}, []) == []


def test_compare_with_latest_uses_most_recent_entry_only():
    current = {"등록상태": "등록(샘플)", "출원인": "샘플대학교", "IPC": "H01M 10/613"}
    assert compare_with_latest(current, HISTORY) == []


def test_compare_with_latest_flags_changed_fields():
    current = {"등록상태": "소멸(샘플)", "출원인": "샘플대학교", "IPC": "H01M 10/613"}
    differences = compare_with_latest(current, HISTORY)
    assert differences == [("등록상태", "등록(샘플)", "소멸(샘플)")]

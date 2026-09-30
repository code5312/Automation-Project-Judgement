"""Tests for the append-only JSON judgment store."""

from __future__ import annotations

import json

import pytest

from ipauto.judgments.service import (
    APPLICATION_FIELD,
    JudgmentStoreError,
    load_judgments,
    save_judgment,
)

SAMPLE_RECORD = {
    APPLICATION_FIELD: "SAMPLE-0000001",
    "발명의 명칭": "샘플 발명",
    "출원인": "샘플대학교",
    "IPC": "H01M 10/613",
    "등록상태": "공개(샘플)",
}


def test_load_judgments_returns_empty_list_when_file_missing(tmp_path):
    assert load_judgments(tmp_path / "judgments.json") == []


def test_load_judgments_raises_on_malformed_json(tmp_path):
    path = tmp_path / "judgments.json"
    path.write_text("{not valid json", encoding="utf-8")
    with pytest.raises(JudgmentStoreError):
        load_judgments(path)


def test_save_judgment_rejects_blank_reason(tmp_path):
    path = tmp_path / "judgments.json"
    with pytest.raises(ValueError):
        save_judgment(SAMPLE_RECORD, "관련 있음", "   ", "relevance_score", "review_priority", path)
    assert not path.exists()


def test_save_judgment_rejects_unknown_decision(tmp_path):
    path = tmp_path / "judgments.json"
    with pytest.raises(ValueError):
        save_judgment(SAMPLE_RECORD, "알 수 없음", "이유", "relevance_score", "review_priority", path)


def test_save_judgment_appends_without_overwriting_history(tmp_path):
    path = tmp_path / "judgments.json"
    save_judgment(SAMPLE_RECORD, "관련 있음", "샘플 이유 1", "relevance_score", "review_priority", path)
    save_judgment(SAMPLE_RECORD, "관련 없음", "샘플 이유 2", "relevance_score", "review_priority", path)

    history = json.loads(path.read_text(encoding="utf-8"))
    assert len(history) == 2
    assert [entry["decisionReason"] for entry in history] == ["샘플 이유 1", "샘플 이유 2"]

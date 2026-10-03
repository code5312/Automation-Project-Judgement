"""Tests for LLM structured-classification prompting and format validation
(docs/PIPELINE.md 단계 3: "LLM 분류 프롬프트 ... + 형식 검증").

No real network calls or real API keys here — ``classify`` is tested with
``connectors.llm.complete`` monkeypatched. Example/record text is all
invented sample data.
"""

from __future__ import annotations

import json

import pytest

from ipauto.triage import llm_classifier
from ipauto.triage.llm_classifier import (
    LABEL_RELEVANT,
    ClassificationFormatError,
    build_prompt,
    classify,
    parse_classification,
)

VALID_RESPONSE = json.dumps(
    {
        "label": "관련",
        "confidence": 0.8,
        "evidence": ["샘플 인용문"],
        "missing_info": ["샘플 누락 정보"],
    },
    ensure_ascii=False,
)


def test_build_prompt_includes_few_shot_examples_and_the_new_case():
    prompt = build_prompt("샘플 사건 요약", "샘플 자산 제목", "H01M 10/613")

    assert "샘플 사건 요약" in prompt
    assert "샘플 자산 제목" in prompt
    assert "(가상 예시)" in prompt  # few-shot examples are present and clearly marked
    assert prompt.strip().endswith("답변:")


def test_parse_classification_accepts_well_formed_json():
    result = parse_classification(VALID_RESPONSE)

    assert result.label == LABEL_RELEVANT
    assert result.confidence == 0.8
    assert result.evidence == ["샘플 인용문"]
    assert result.missing_info == ["샘플 누락 정보"]


def test_parse_classification_tolerates_surrounding_prose():
    wrapped = f"물론입니다, 분석 결과는 다음과 같습니다:\n{VALID_RESPONSE}\n감사합니다."

    result = parse_classification(wrapped)

    assert result.label == LABEL_RELEVANT


@pytest.mark.parametrize(
    "broken_response",
    [
        "이건 JSON이 아닙니다",
        json.dumps({"confidence": 0.8, "evidence": [], "missing_info": []}),  # missing label
        json.dumps({"label": "애매", "confidence": 0.8, "evidence": [], "missing_info": []}),  # invalid label
        json.dumps({"label": "관련", "confidence": 1.5, "evidence": [], "missing_info": []}),  # out-of-range
        json.dumps({"label": "관련", "confidence": "높음", "evidence": [], "missing_info": []}),  # non-numeric
        json.dumps({"label": "관련", "confidence": 0.8, "evidence": "문자열", "missing_info": []}),  # not a list
        json.dumps({"label": "관련", "confidence": 0.8, "evidence": [1, 2], "missing_info": []}),  # non-string items
    ],
)
def test_parse_classification_rejects_malformed_responses(broken_response):
    with pytest.raises(ClassificationFormatError):
        parse_classification(broken_response)


def test_classify_calls_llm_with_built_prompt_and_parses_result(monkeypatch):
    captured = {}

    def fake_complete(prompt, *, api_key, system=None, model=None):
        captured["prompt"] = prompt
        captured["api_key"] = api_key
        captured["system"] = system
        return VALID_RESPONSE

    monkeypatch.setattr(llm_classifier, "complete", fake_complete)

    result = classify("샘플 사건", "샘플 자산", "H01M 10/613", api_key="sample-key")

    assert result.label == LABEL_RELEVANT
    assert captured["api_key"] == "sample-key"
    assert "샘플 사건" in captured["prompt"]
    assert captured["system"] is not None


def test_classify_propagates_format_error_on_bad_llm_output(monkeypatch):
    monkeypatch.setattr(llm_classifier, "complete", lambda *a, **k: "응답이 아예 다름")

    with pytest.raises(ClassificationFormatError):
        classify("샘플 사건", "샘플 자산", "H01M 10/613", api_key="sample-key")

"""Tests for IPC/keyword scoring. Records here are invented sample data, not real patents."""

from __future__ import annotations

from ipauto.scoring import ipc
from ipauto.scoring.bands import PRIORITY_HIGH, PRIORITY_LOW, classify
from ipauto.scoring.keywords import (
    MODE_CONCEPT_GROUP,
    MODE_GENERIC_KEYWORD,
    calculate_relevance,
    extract_generic_keywords,
    rank_records,
)

SAMPLE_BATTERY_COOLING_RECORD = {
    "발명의 명칭": "샘플 전기차 배터리 냉각 장치",
    "출원번호": "SAMPLE-0000001",
    "출원인": "샘플대학교",
    "IPC": "H01M 10/613",
    "등록상태": "공개(샘플)",
    "초록": "샘플 배터리 냉각수 순환 구조에 대한 가상의 설명입니다.",
}

SAMPLE_UNRELATED_RECORD = {
    "발명의 명칭": "샘플 무관 반도체 장치",
    "출원번호": "SAMPLE-0000002",
    "출원인": "샘플 주식회사",
    "IPC": "G06F 1/20",
    "등록상태": "등록(샘플)",
    "초록": "샘플 반도체 공정 최적화에 대한 가상의 설명입니다.",
}


def test_ipc_detected_families_matches_configured_codes_only():
    assert ipc.detected_families("H01M 10/613|H01M 10/625") == ["H01M"]
    assert ipc.detected_families("G06F 1/20") == []


def test_calculate_relevance_concept_mode_scores_battery_and_cooling_high():
    result = calculate_relevance("전기차 배터리 냉각", SAMPLE_BATTERY_COOLING_RECORD)

    assert result["analysis_mode"] == MODE_CONCEPT_GROUP
    assert result["relevance_score"] >= 70
    assert result["review_priority"] == PRIORITY_HIGH


def test_calculate_relevance_concept_mode_scores_unrelated_record_low():
    result = calculate_relevance("전기차 배터리 냉각", SAMPLE_UNRELATED_RECORD)

    assert result["review_priority"] == PRIORITY_LOW


def test_calculate_relevance_falls_back_to_generic_keywords():
    result = calculate_relevance("반도체 장치", SAMPLE_UNRELATED_RECORD)

    assert result["analysis_mode"] == MODE_GENERIC_KEYWORD


def test_extract_generic_keywords_strips_particles_and_stopwords():
    keywords = extract_generic_keywords("반도체 장치에서의 열처리 공정을 개선")
    assert "장치" not in keywords  # stopword
    assert any(word.startswith("반도체") for word in keywords)


def test_rank_records_sorts_by_score_descending():
    ranked = rank_records("전기차 배터리 냉각", [SAMPLE_BATTERY_COOLING_RECORD, SAMPLE_UNRELATED_RECORD])
    assert ranked[0]["출원번호"] == "SAMPLE-0000001"
    assert ranked[0]["relevance_score"] >= ranked[1]["relevance_score"]


def test_bands_classify_thresholds():
    assert classify(70, high_min=70, medium_min=40) == PRIORITY_HIGH
    assert classify(39, high_min=70, medium_min=40) == PRIORITY_LOW

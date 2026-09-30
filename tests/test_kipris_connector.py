"""Tests for XML parsing and success/failure classification.

Fixtures under tests/fixtures/ mimic KIPRIS response shapes but are entirely
invented (filenames contain "sample"; values contain "샘플"/"SAMPLE").
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ipauto.connectors.kipris import (
    KiprisResponseError,
    parse_response,
    raise_if_unsuccessful,
)

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


def _load(name: str) -> bytes:
    return (FIXTURES_DIR / name).read_bytes()


def test_parse_response_extracts_records():
    page = parse_response(_load("sample_kipris_response.xml"))

    assert page.success_yn == "Y"
    assert len(page.records) == 2
    first = page.records[0]
    assert first.get("발명의 명칭") == "샘플 배터리 열관리 시스템"
    assert first.get("출원번호") == "SAMPLE-0000001"
    assert "H01M" in first.get("IPC")


def test_parse_response_zero_results_is_not_an_error():
    page = parse_response(_load("sample_kipris_response_empty.xml"))

    assert page.success_yn == "Y"
    assert page.records == []
    # Zero results on a successful call must not raise.
    raise_if_unsuccessful(page)


def test_raise_if_unsuccessful_raises_on_failure_response():
    page = parse_response(_load("sample_kipris_response_failure.xml"))

    assert page.success_yn == "N"
    with pytest.raises(KiprisResponseError, match="SAMPLE SERVICE ERROR"):
        raise_if_unsuccessful(page)

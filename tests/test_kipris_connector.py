"""Tests for XML parsing and success/failure classification.

Fixtures under tests/fixtures/ mimic KIPRIS response shapes but are entirely
invented (filenames contain "sample"; values contain "샘플"/"SAMPLE").
"""

from __future__ import annotations

from pathlib import Path

import pytest

import ipauto.connectors.kipris as kipris
from ipauto.connectors.kipris import (
    KiprisPage,
    KiprisRecord,
    KiprisResponseError,
    dedupe_by_application_number,
    fetch_all,
    parse_response,
    raise_if_unsuccessful,
)

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


def _load(name: str) -> bytes:
    return (FIXTURES_DIR / name).read_bytes()


def _record(application_number: str, title: str = "제목") -> KiprisRecord:
    return KiprisRecord(fields={"발명의 명칭": title, "출원번호": application_number})


def _page(records: list[KiprisRecord]) -> KiprisPage:
    return KiprisPage(
        records=records,
        result_code="00",
        result_msg="",
        success_yn="Y",
        http_status=200,
        patent_node_count=len(records),
        item_node_count=0,
    )


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


def test_dedupe_by_application_number_drops_repeats_keeps_first():
    records = [_record("SAMPLE-1", "첫번째"), _record("SAMPLE-2"), _record("SAMPLE-1", "중복")]

    deduped, duplicate_count = dedupe_by_application_number(records)

    assert [r.get("출원번호") for r in deduped] == ["SAMPLE-1", "SAMPLE-2"]
    assert deduped[0].get("발명의 명칭") == "첫번째"
    assert duplicate_count == 1


def test_dedupe_by_application_number_keeps_records_without_one():
    records = [_record(""), _record("")]

    deduped, duplicate_count = dedupe_by_application_number(records)

    assert len(deduped) == 2
    assert duplicate_count == 0


def test_fetch_all_paginates_until_short_page(monkeypatch):
    pages = {
        ("냉각", 1): _page([_record("A-1"), _record("A-2")]),
        ("냉각", 3): _page([_record("A-3")]),
    }
    calls: list[tuple[str, int]] = []

    def fake_fetch_page(query, access_key, count=2, start=1):
        calls.append((query, start))
        return pages[(query, start)]

    monkeypatch.setattr(kipris, "fetch_page", fake_fetch_page)

    result = fetch_all(["냉각"], "key", page_size=2)

    assert [r.get("출원번호") for r in result.records] == ["A-1", "A-2", "A-3"]
    assert result.query_page_counts == {"냉각": 2}
    assert calls == [("냉각", 1), ("냉각", 3)]


def test_fetch_all_fans_out_over_queries_and_dedupes(monkeypatch):
    pages = {
        ("배터리", 1): _page([_record("A-1"), _record("A-2")]),
        ("냉각", 1): _page([_record("A-2")]),
    }

    def fake_fetch_page(query, access_key, count=3, start=1):
        return pages[(query, start)]

    monkeypatch.setattr(kipris, "fetch_page", fake_fetch_page)

    result = fetch_all(["배터리", "냉각"], "key", page_size=3)

    assert [r.get("출원번호") for r in result.records] == ["A-1", "A-2"]
    assert result.duplicate_count == 1
    assert result.query_page_counts == {"배터리": 1, "냉각": 1}


def test_fetch_all_respects_max_pages_per_query(monkeypatch):
    def fake_fetch_page(query, access_key, count=2, start=1):
        # Always return a full page so pagination would run forever without the cap.
        return _page([_record(f"A-{start}"), _record(f"A-{start + 1}")])

    monkeypatch.setattr(kipris, "fetch_page", fake_fetch_page)

    result = fetch_all(["배터리"], "key", page_size=2, max_pages_per_query=3)

    assert result.query_page_counts == {"배터리": 3}
    assert len(result.records) == 6


def test_fetch_all_requires_at_least_one_query():
    with pytest.raises(ValueError):
        fetch_all([], "key")

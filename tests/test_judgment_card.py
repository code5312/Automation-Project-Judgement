"""Tests for judgment card assembly (docs/PIPELINE.md 단계 3: 판단 카드 생성).

Records here are invented sample data, not real events or patents.
"""

from __future__ import annotations

import sqlite3

import pytest

from ipauto.cards.judgment_card import (
    LEGAL_DISCLAIMER,
    build_judgment_card,
    format_card_text,
    save_judgment_from_card,
)
from ipauto.db.connection import init_db
from ipauto.db.repositories import (
    ASSET_KIND_EXTERNAL,
    ASSET_KIND_OWN,
    EventInput,
    IpAssetInput,
    JudgmentInput,
    PremiseInput,
)
from ipauto.db.repositories import fetch_event as get_event
from ipauto.db.repositories import fetch_ip_asset_by_id as get_asset
from ipauto.db.repositories import save_event as insert_event
from ipauto.db.repositories import save_ip_asset as insert_ip_asset
from ipauto.db.repositories import save_judgment as insert_judgment
from ipauto.judgments.service import JudgmentValidationError, premises_for_judgment
from ipauto.scoring.bands import PRIORITY_HIGH
from ipauto.triage.llm_classifier import ClassificationResult


@pytest.fixture
def conn():
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    init_db(connection)
    yield connection
    connection.close()


def _seed(conn, asset_kind=ASSET_KIND_OWN, application_number="SAMPLE-ASSET-0000001"):
    event_id, _ = insert_event(
        conn,
        EventInput(
            event_type="오픈소스 공개",
            source="GitHub",
            source_ref="SAMPLE-RELEASE-1",
            source_url="https://example.invalid/release",
            summary="전기차 배터리 냉각 신규 공개",
        ),
    )
    asset_id = insert_ip_asset(
        conn,
        IpAssetInput(
            application_number=application_number,
            asset_kind=asset_kind,
            title="전기차 배터리 냉각 장치",
            ipc_codes="H01M 10/613",
        ),
    )
    return get_event(conn, event_id), get_asset(conn, asset_id)


def test_build_judgment_card_without_llm_uses_keyword_reason_as_evidence(conn):
    event_row, asset_row = _seed(conn)

    card = build_judgment_card(conn, event_row, asset_row)

    assert card.application_number == "SAMPLE-ASSET-0000001"
    assert card.ip_asset_title == "전기차 배터리 냉각 장치"
    assert card.event_source_url == "https://example.invalid/release"
    assert card.evidence  # keyword/IPC reasoning text, non-empty for this clear match
    assert card.similar_cases == []
    assert card.missing_info == []
    assert card.model_version is None
    assert card.prompt_version is None
    assert card.disclaimer == LEGAL_DISCLAIMER
    # title+IPC clearly match "전기차 배터리 냉각" -> high band, concept-group mode
    assert card.review_priority == PRIORITY_HIGH
    assert card.relevance_score > 0
    assert card.analysis_mode == "concept_group"


def test_build_judgment_card_with_llm_result_uses_its_fields(conn):
    event_row, asset_row = _seed(conn)
    llm_result = ClassificationResult(
        label="관련",
        confidence=0.9,
        evidence=["샘플 인용문"],
        missing_info=["샘플 누락 정보"],
        raw_response="{}",
        model="sample-model",
        prompt_version="sample-prompt-v1",
    )

    card = build_judgment_card(conn, event_row, asset_row, llm_result=llm_result)

    assert card.evidence == ["샘플 인용문"]
    assert card.missing_info == ["샘플 누락 정보"]
    assert card.model_version == "sample-model"
    assert card.prompt_version == "sample-prompt-v1"
    # the keyword/IPC score is still computed for provenance, independent
    # of whether an LLM result was supplied
    assert card.review_priority == PRIORITY_HIGH
    assert card.relevance_score > 0


def test_recommended_decisions_always_cover_the_full_enum(conn):
    event_row, asset_row = _seed(conn)

    card = build_judgment_card(conn, event_row, asset_row)

    assert sorted(card.recommended_decisions) == sorted(
        ["신규 출원 검토", "기존 IP 보강 검토", "유지", "정리 검토", "타사 특허 확인 필요"]
    )


def test_recommended_decisions_prioritize_third_party_check_for_external_assets(conn):
    event_row, asset_row = _seed(conn, asset_kind=ASSET_KIND_EXTERNAL)

    card = build_judgment_card(conn, event_row, asset_row)

    assert card.recommended_decisions[0] == "타사 특허 확인 필요"


def test_recommended_decisions_repeat_the_most_recent_past_decision_first(conn):
    event_row, asset_row = _seed(conn)
    insert_judgment(
        conn,
        JudgmentInput(
            application_number=asset_row["application_number"],
            review_technology="샘플 기술",
            decision="정리 검토",
            reason="샘플 이유",
            assignee="샘플 담당자",
            review_deadline="2026-12-31",
            premises=[PremiseInput(source="샘플", check_key="등록상태", expected_value="공개(샘플)")],
        ),
    )

    card = build_judgment_card(conn, event_row, asset_row)

    assert card.recommended_decisions[0] == "정리 검토"
    assert len(card.similar_cases) == 1
    assert card.similar_cases[0].decision == "정리 검토"


def test_format_card_text_includes_disclaimer_and_key_sections(conn):
    event_row, asset_row = _seed(conn)
    card = build_judgment_card(conn, event_row, asset_row)

    text = format_card_text(card)

    assert "판단 카드" in text
    assert card.event_summary in text
    assert LEGAL_DISCLAIMER in text
    assert "추천 선택지" in text


def test_save_judgment_from_card_persists_a_gate_b_judgment_with_card_provenance(conn):
    event_row, asset_row = _seed(conn)
    card = build_judgment_card(conn, event_row, asset_row)

    judgment_id = save_judgment_from_card(
        conn,
        card,
        decision="신규 출원 검토",
        reason="사건이 자사 특허와 직접 겹친다고 판단",
        premises=[("KIPRIS 재조회", "등록상태", "공개(샘플)")],
        assignee="샘플 담당자",
        review_deadline="2026-12-31",
    )

    row = conn.execute("SELECT * FROM judgment WHERE id = ?", (judgment_id,)).fetchone()
    assert row["application_number"] == card.application_number
    assert row["review_technology"] == card.event_summary
    assert row["decision"] == "신규 출원 검토"
    assert row["event_id"] == event_row["id"]
    assert row["analysis_mode"] == card.analysis_mode
    assert row["relevance_score"] == card.relevance_score
    assert row["review_priority"] == card.review_priority
    assert row["model_version"] == card.model_version
    assert row["prompt_version"] == card.prompt_version

    premises = premises_for_judgment(conn, judgment_id)
    assert len(premises) == 1
    assert premises[0]["check_key"] == "등록상태"


def test_save_judgment_from_card_carries_llm_model_and_prompt_version(conn):
    event_row, asset_row = _seed(conn)
    llm_result = ClassificationResult(
        label="관련",
        confidence=0.9,
        evidence=["샘플 인용문"],
        missing_info=[],
        raw_response="{}",
        model="sample-model",
        prompt_version="sample-prompt-v1",
    )
    card = build_judgment_card(conn, event_row, asset_row, llm_result=llm_result)

    judgment_id = save_judgment_from_card(
        conn,
        card,
        decision="기존 IP 보강 검토",
        reason="LLM 근거로 판단",
        premises=[("KIPRIS 재조회", "등록상태", "공개(샘플)")],
        assignee="샘플 담당자",
        review_deadline="2026-12-31",
    )

    row = conn.execute("SELECT * FROM judgment WHERE id = ?", (judgment_id,)).fetchone()
    assert row["model_version"] == "sample-model"
    assert row["prompt_version"] == "sample-prompt-v1"


def test_save_judgment_from_card_propagates_gate_b_validation(conn):
    event_row, asset_row = _seed(conn)
    card = build_judgment_card(conn, event_row, asset_row)

    with pytest.raises(JudgmentValidationError):
        save_judgment_from_card(
            conn,
            card,
            decision="유지",
            reason="   ",  # blank reason must be rejected
            premises=[("KIPRIS 재조회", "등록상태", "공개(샘플)")],
            assignee="샘플 담당자",
            review_deadline="2026-12-31",
        )

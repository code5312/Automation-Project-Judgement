"""Propose Links between an Event and the IP asset portfolio (docs/DESIGN.md Link, 단계 3).

Reuses the existing concept/IPC relevance scorer (``ipauto.scoring.keywords``
— the same one that ranks KIPRIS search results) to propose candidate
links, basis "IPC 일치" 또는 "키워드" (schema's own basis enum comment on
``link.basis``). It does not distinguish 자사/외부 IP — ``ip_asset.asset_kind``
already carries that, and every asset in the portfolio is scored the same
way, so "사건 ↔ 자사 IP ↔ 외부 특허 연결"은 포트폴리오에 넣은 자산 종류에
따라 자연히 양쪽 다 다뤄진다.

Two things this module deliberately does not do yet, both separate
PIPELINE.md 단계 3 items: "LLM 제안"(LLM 분류 프롬프트)과 사람이 제안을
확인하는 화면(게이트 A) — 제안된 Link는 항상 ``confirmed_by_human=False``로
저장되고, ``ipauto.db.repositories.confirm_link``로 나중에 확정한다.
"""

from __future__ import annotations

import sqlite3

from ipauto.db.repositories import (
    LINK_BASIS_IPC_MATCH,
    LINK_BASIS_KEYWORD,
    LINK_OBJECT_EVENT,
    LINK_OBJECT_IP_ASSET,
    LinkInput,
    fetch_ip_assets,
    find_link,
    save_link,
)
from ipauto.scoring.bands import PRIORITY_LOW
from ipauto.scoring.keywords import MATCHED_FIELD, PRIORITY_FIELD, calculate_relevance

_TITLE_FIELD = "발명의 명칭"
_IPC_FIELD = "IPC"


def _basis_for(matched_concepts: str) -> str:
    return LINK_BASIS_IPC_MATCH if "IPC" in matched_concepts else LINK_BASIS_KEYWORD


def link_event_to_ip_assets(conn: sqlite3.Connection, event_id: int, event_summary: str) -> list[int]:
    """Score event_summary against every IPAsset and save a Link for each non-낮음 match.

    Skips any (event, ip_asset) pair that already has a Link, so re-running
    after new assets are added only creates links for the new ones.
    Returns the ids of newly created Link rows.
    """
    created_ids: list[int] = []
    for asset in fetch_ip_assets(conn):
        if find_link(conn, LINK_OBJECT_EVENT, event_id, LINK_OBJECT_IP_ASSET, asset["id"]) is not None:
            continue

        record = {_TITLE_FIELD: asset["title"] or "", _IPC_FIELD: asset["ipc_codes"] or ""}
        result = calculate_relevance(event_summary, record)
        if result[PRIORITY_FIELD] == PRIORITY_LOW:
            continue

        link_id = save_link(
            conn,
            LinkInput(
                from_type=LINK_OBJECT_EVENT,
                from_id=event_id,
                to_type=LINK_OBJECT_IP_ASSET,
                to_id=asset["id"],
                basis=_basis_for(str(result[MATCHED_FIELD])),
                confidence_band=str(result[PRIORITY_FIELD]),
            ),
        )
        created_ids.append(link_id)
    return created_ids

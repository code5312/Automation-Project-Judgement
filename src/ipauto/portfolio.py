"""자사/외부 IP 포트폴리오 적재 (docs/DESIGN.md IPAsset, docs/PIPELINE.md 단계 3).

KIPRIS가 출원인 기준 조회를 지원하는지 아직 미확인이라(docs/OPEN_QUESTIONS.md),
출원인으로 일괄 수집하는 기능은 아직 없다. 대신 두 가지 경로를 제공한다:

- ``ingest_records``: 이미 가진 KIPRIS 레코드 묶음(JSON 등)을 바로 적재한다.
  접근키가 필요 없어 데모·오프라인 재적재에 쓴다.
- ``ingest_application_numbers``: 출원번호 목록을 받아
  ``ipauto.connectors.kipris.fetch_by_application_number``로 하나씩 재조회해
  적재한다. 실제 접근키가 필요하며, 출원인 기준 조회가 확인되면 이 함수를
  "출원인 → 출원번호 목록" 조회로 앞단에 이어 붙이면 된다.
"""

from __future__ import annotations

import sqlite3

from ipauto.connectors.kipris import fetch_by_application_number
from ipauto.db.repositories import ASSET_KIND_OWN, IpAssetInput, save_ip_asset

TITLE_FIELD = "발명의 명칭"
APPLICATION_FIELD = "출원번호"
APPLICANT_FIELD = "출원인"
IPC_FIELD = "IPC"
STATUS_FIELD = "등록상태"


def ip_asset_from_fields(fields: dict[str, str], asset_kind: str, last_fetched_at: str | None = None) -> IpAssetInput:
    """Build an IPAsset row from KIPRIS-shaped fields (same keys as KiprisRecord.fields)."""
    application_number = fields.get(APPLICATION_FIELD, "")
    if not application_number:
        raise ValueError("Record is missing a non-empty 출원번호.")
    return IpAssetInput(
        application_number=application_number,
        asset_kind=asset_kind,
        title=fields.get(TITLE_FIELD) or None,
        applicant=fields.get(APPLICANT_FIELD) or None,
        ipc_codes=fields.get(IPC_FIELD) or None,
        legal_status=fields.get(STATUS_FIELD) or None,
        last_fetched_at=last_fetched_at,
    )


def ingest_records(
    conn: sqlite3.Connection, records: list[dict[str, str]], asset_kind: str = ASSET_KIND_OWN
) -> list[int]:
    """Upsert a batch of already-fetched KIPRIS-shaped records into ip_asset. Returns their row ids."""
    return [save_ip_asset(conn, ip_asset_from_fields(fields, asset_kind)) for fields in records]


def ingest_application_numbers(
    conn: sqlite3.Connection,
    application_numbers: list[str],
    access_key: str,
    asset_kind: str = ASSET_KIND_OWN,
) -> list[str]:
    """Re-query KIPRIS for each application number and upsert it as an IPAsset.

    Returns the application numbers fetch_by_application_number could not
    (re)confirm — the same "inconclusive, not a confirmed absence" caveat as
    that function applies; an unresolved number is left untouched in
    ip_asset rather than removed.
    """
    unresolved: list[str] = []
    for application_number in application_numbers:
        record = fetch_by_application_number(application_number, access_key)
        if record is None:
            unresolved.append(application_number)
            continue
        save_ip_asset(conn, ip_asset_from_fields(record.fields, asset_kind))
    return unresolved

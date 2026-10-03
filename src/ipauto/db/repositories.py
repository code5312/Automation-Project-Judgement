"""Read/write access to the judgment ledger, IP asset portfolio, events, and links.

``judgment``/``premise`` are append-only: no function here issues UPDATE or
DELETE against them, a correction is always a new Judgment row chained via
``previous_judgment_id``. ``ip_asset`` (단계 3) is different — it is a
re-fetchable cache of KIPRIS attributes, so ``save_ip_asset`` is a normal
upsert keyed by application_number. ``event`` (단계 3) is deduped by
``(source, source_ref)`` instead — ``save_event`` is insert-or-skip, not an
upsert, since a source's own record of an event doesn't change after the
fact the way a KIPRIS record can. ``link`` (단계 3) is plain insert
(``save_link``) plus one explicit ``confirm_link`` UPDATE for the one field
docs/DESIGN.md expects to change after the fact: 사람 확인 여부.
``auto_close_log`` (단계 3) is deduped by ``(event_id, ip_asset_id)`` like
``event``, plus an explicit ``record_audit_result`` UPDATE for the sample-
audit outcome (docs/DESIGN.md "자동 종결하되 표본 감사로 검증").
``gate_a_queue`` (단계 3) follows the same pattern — deduped insert
(``enqueue_gate_a``) plus one ``resolve_gate_a`` UPDATE for the human's
관련/무관 확정 decision (docs/DESIGN.md "애매: 게이트 A로 보내 사람이
검토 여부를 정한다").
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from datetime import UTC, datetime

from ipauto.db.connection import transaction

DECISION_CHOICES = (
    "신규 출원 검토",
    "기존 IP 보강 검토",
    "유지",
    "정리 검토",
    "타사 특허 확인 필요",
)

EVENT_STATUS_NEW = "신규"
EVENT_STATUS_TRIAGED = "트리아지 완료"
EVENT_STATUS_CLOSED = "종결"
EVENT_STATUS_CHOICES = (EVENT_STATUS_NEW, EVENT_STATUS_TRIAGED, EVENT_STATUS_CLOSED)

ASSET_KIND_OWN = "자사"
ASSET_KIND_EXTERNAL = "외부"
ASSET_KIND_CHOICES = (ASSET_KIND_OWN, ASSET_KIND_EXTERNAL)

# link.from_type/to_type (schema comment): 'event' | 'ip_asset' | 'judgment' | 'task'
LINK_OBJECT_EVENT = "event"
LINK_OBJECT_IP_ASSET = "ip_asset"
LINK_OBJECT_JUDGMENT = "judgment"
LINK_OBJECT_TASK = "task"

# link.basis (schema comment): IPC 일치 / 키워드 / 담당자 지정 / LLM 제안
LINK_BASIS_IPC_MATCH = "IPC 일치"
LINK_BASIS_KEYWORD = "키워드"
LINK_BASIS_ASSIGNED = "담당자 지정"
LINK_BASIS_LLM_SUGGESTION = "LLM 제안"

AUDIT_STATUS_PENDING = "대기"
AUDIT_STATUS_CONFIRMED = "확인 완료"
AUDIT_STATUS_MISSED = "누락 발견"
AUDIT_STATUS_CHOICES = (AUDIT_STATUS_PENDING, AUDIT_STATUS_CONFIRMED, AUDIT_STATUS_MISSED)

GATE_A_STATUS_PENDING = "대기"
GATE_A_STATUS_RELATED = "관련 확정"
GATE_A_STATUS_UNRELATED = "무관 확정"
GATE_A_STATUS_CHOICES = (GATE_A_STATUS_PENDING, GATE_A_STATUS_RELATED, GATE_A_STATUS_UNRELATED)

_REASON_SEPARATOR = "|"


@dataclass(frozen=True)
class PremiseInput:
    source: str
    check_key: str
    expected_value: str
    check_method: str | None = None


@dataclass(frozen=True)
class JudgmentInput:
    application_number: str
    review_technology: str
    decision: str
    reason: str
    assignee: str
    review_deadline: str
    premises: list[PremiseInput] = field(default_factory=list)
    event_id: int | None = None
    search_query: str | None = None
    analysis_mode: str | None = None
    relevance_score: float | None = None
    review_priority: str | None = None
    model_version: str | None = None
    prompt_version: str | None = None
    previous_judgment_id: int | None = None
    migrated_from_json: bool = False
    legacy_note: str | None = None
    created_at: str | None = None


def fetch_latest_judgment(
    conn: sqlite3.Connection, application_number: str, review_technology: str
) -> sqlite3.Row | None:
    row = conn.execute(
        """
        SELECT * FROM judgment
        WHERE application_number = ? AND review_technology = ?
        ORDER BY created_at DESC, id DESC
        LIMIT 1
        """,
        (application_number, review_technology),
    ).fetchone()
    return row


def fetch_judgments_for_application(conn: sqlite3.Connection, application_number: str) -> list[sqlite3.Row]:
    return conn.execute(
        """
        SELECT * FROM judgment
        WHERE application_number = ?
        ORDER BY created_at DESC, id DESC
        """,
        (application_number,),
    ).fetchall()


def fetch_premises_for_judgment(conn: sqlite3.Connection, judgment_id: int) -> list[sqlite3.Row]:
    return conn.execute("SELECT * FROM premise WHERE judgment_id = ? ORDER BY id", (judgment_id,)).fetchall()


def count_judgments(conn: sqlite3.Connection, migrated_from_json: bool | None = None) -> int:
    if migrated_from_json is None:
        row = conn.execute("SELECT COUNT(*) AS n FROM judgment").fetchone()
    else:
        row = conn.execute(
            "SELECT COUNT(*) AS n FROM judgment WHERE migrated_from_json = ?",
            (1 if migrated_from_json else 0,),
        ).fetchone()
    return row["n"]


def find_migrated_judgment(conn: sqlite3.Connection, application_number: str, created_at: str) -> sqlite3.Row | None:
    """Look up a previously migrated row by its original (app number, decisionTime).

    Used by migrate_json.py to stay idempotent across repeated runs.
    """
    return conn.execute(
        """
        SELECT * FROM judgment
        WHERE application_number = ? AND created_at = ? AND migrated_from_json = 1
        """,
        (application_number, created_at),
    ).fetchone()


def _insert_judgment_row(conn: sqlite3.Connection, data: JudgmentInput) -> int:
    columns = [
        "application_number",
        "review_technology",
        "event_id",
        "search_query",
        "analysis_mode",
        "decision",
        "reason",
        "assignee",
        "review_deadline",
        "relevance_score",
        "review_priority",
        "model_version",
        "prompt_version",
        "previous_judgment_id",
        "migrated_from_json",
        "legacy_note",
    ]
    values = [
        data.application_number,
        data.review_technology,
        data.event_id,
        data.search_query,
        data.analysis_mode,
        data.decision,
        data.reason,
        data.assignee,
        data.review_deadline,
        data.relevance_score,
        data.review_priority,
        data.model_version,
        data.prompt_version,
        data.previous_judgment_id,
        1 if data.migrated_from_json else 0,
        data.legacy_note,
    ]
    if data.created_at is not None:
        columns.append("created_at")
        values.append(data.created_at)

    placeholders = ", ".join("?" for _ in columns)
    cursor = conn.execute(f"INSERT INTO judgment ({', '.join(columns)}) VALUES ({placeholders})", values)
    return cursor.lastrowid


def save_judgment(conn: sqlite3.Connection, data: JudgmentInput) -> int:
    """Insert one Judgment plus its Premise rows in a single transaction."""
    with transaction(conn):
        judgment_id = _insert_judgment_row(conn, data)
        for premise in data.premises:
            conn.execute(
                """
                INSERT INTO premise (judgment_id, source, check_key, expected_value, check_method)
                VALUES (?, ?, ?, ?, ?)
                """,
                (judgment_id, premise.source, premise.check_key, premise.expected_value, premise.check_method),
            )
    return judgment_id


@dataclass(frozen=True)
class IpAssetInput:
    application_number: str
    asset_kind: str
    title: str | None = None
    applicant: str | None = None
    ipc_codes: str | None = None
    legal_status: str | None = None
    source_url: str | None = None
    last_fetched_at: str | None = None


def save_ip_asset(conn: sqlite3.Connection, data: IpAssetInput) -> int:
    """Upsert one IPAsset keyed by application_number.

    Unlike Judgment/Premise, IPAsset is a re-fetchable cache of KIPRIS
    attributes (docs/DESIGN.md), not an append-only ledger, so re-ingesting
    the same application number updates the row in place instead of
    chaining a new one.
    """
    with transaction(conn):
        conn.execute(
            """
            INSERT INTO ip_asset
                (application_number, asset_kind, title, applicant, ipc_codes, legal_status, source_url, last_fetched_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (application_number) DO UPDATE SET
                asset_kind = excluded.asset_kind,
                title = excluded.title,
                applicant = excluded.applicant,
                ipc_codes = excluded.ipc_codes,
                legal_status = excluded.legal_status,
                source_url = excluded.source_url,
                last_fetched_at = excluded.last_fetched_at
            """,
            (
                data.application_number,
                data.asset_kind,
                data.title,
                data.applicant,
                data.ipc_codes,
                data.legal_status,
                data.source_url,
                data.last_fetched_at,
            ),
        )
        row = conn.execute(
            "SELECT id FROM ip_asset WHERE application_number = ?", (data.application_number,)
        ).fetchone()
    return row["id"]


def fetch_ip_asset(conn: sqlite3.Connection, application_number: str) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM ip_asset WHERE application_number = ?", (application_number,)).fetchone()


def fetch_ip_asset_by_id(conn: sqlite3.Connection, ip_asset_id: int) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM ip_asset WHERE id = ?", (ip_asset_id,)).fetchone()


def fetch_ip_assets(conn: sqlite3.Connection, asset_kind: str | None = None) -> list[sqlite3.Row]:
    if asset_kind is None:
        return conn.execute("SELECT * FROM ip_asset ORDER BY application_number").fetchall()
    return conn.execute(
        "SELECT * FROM ip_asset WHERE asset_kind = ? ORDER BY application_number", (asset_kind,)
    ).fetchall()


def _now_iso() -> str:
    now = datetime.now(UTC)
    return now.strftime("%Y-%m-%dT%H:%M:%S.") + f"{now.microsecond // 1000:03d}Z"


@dataclass(frozen=True)
class EventInput:
    event_type: str
    source: str
    source_ref: str
    source_url: str | None = None
    detected_at: str | None = None
    occurred_at: str | None = None
    summary: str | None = None
    status: str = EVENT_STATUS_NEW


def save_event(conn: sqlite3.Connection, data: EventInput) -> tuple[int, bool]:
    """Insert one Event, deduped by (source, source_ref) (docs/DESIGN.md "출처별 고유 ID로 중복 수신을 막는다").

    Returns (id, was_created): was_created is False when a row for this
    (source, source_ref) already existed, in which case nothing was
    written and the existing row's id is returned.
    """
    existing = fetch_event_by_source_ref(conn, data.source, data.source_ref)
    if existing is not None:
        return existing["id"], False

    detected_at = data.detected_at if data.detected_at is not None else _now_iso()
    with transaction(conn):
        cursor = conn.execute(
            """
            INSERT INTO event (event_type, source, source_ref, source_url, detected_at, occurred_at, summary, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                data.event_type,
                data.source,
                data.source_ref,
                data.source_url,
                detected_at,
                data.occurred_at,
                data.summary,
                data.status,
            ),
        )
        event_id = cursor.lastrowid
    return event_id, True


def fetch_event_by_source_ref(conn: sqlite3.Connection, source: str, source_ref: str) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM event WHERE source = ? AND source_ref = ?", (source, source_ref)).fetchone()


def fetch_event(conn: sqlite3.Connection, event_id: int) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM event WHERE id = ?", (event_id,)).fetchone()


def fetch_events(conn: sqlite3.Connection, status: str | None = None) -> list[sqlite3.Row]:
    if status is None:
        return conn.execute("SELECT * FROM event ORDER BY detected_at DESC, id DESC").fetchall()
    return conn.execute(
        "SELECT * FROM event WHERE status = ? ORDER BY detected_at DESC, id DESC", (status,)
    ).fetchall()


@dataclass(frozen=True)
class LinkInput:
    from_type: str
    from_id: int
    to_type: str
    to_id: int
    basis: str
    confidence_band: str | None = None
    confirmed_by_human: bool = False


def save_link(conn: sqlite3.Connection, data: LinkInput) -> int:
    """Insert one Link row. Not deduped here — call find_link first if the caller needs idempotency."""
    with transaction(conn):
        cursor = conn.execute(
            """
            INSERT INTO link (from_type, from_id, to_type, to_id, basis, confidence_band, confirmed_by_human)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                data.from_type,
                data.from_id,
                data.to_type,
                data.to_id,
                data.basis,
                data.confidence_band,
                1 if data.confirmed_by_human else 0,
            ),
        )
        link_id = cursor.lastrowid
    return link_id


def find_link(conn: sqlite3.Connection, from_type: str, from_id: int, to_type: str, to_id: int) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM link WHERE from_type = ? AND from_id = ? AND to_type = ? AND to_id = ?",
        (from_type, from_id, to_type, to_id),
    ).fetchone()


def fetch_links_from(conn: sqlite3.Connection, from_type: str, from_id: int) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM link WHERE from_type = ? AND from_id = ? ORDER BY id", (from_type, from_id)
    ).fetchall()


def fetch_links_to(conn: sqlite3.Connection, to_type: str, to_id: int) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM link WHERE to_type = ? AND to_id = ? ORDER BY id", (to_type, to_id)
    ).fetchall()


def confirm_link(conn: sqlite3.Connection, link_id: int) -> None:
    """Mark one Link as 사람이 확인함 (docs/DESIGN.md Link.확인자, 게이트 A)."""
    with transaction(conn):
        cursor = conn.execute("UPDATE link SET confirmed_by_human = 1 WHERE id = ?", (link_id,))
        if cursor.rowcount == 0:
            raise ValueError(f"No link with id {link_id}.")


@dataclass(frozen=True)
class AutoCloseLogInput:
    event_id: int
    ip_asset_id: int
    keyword_priority: str
    llm_label: str | None = None
    llm_confidence: float | None = None


def log_auto_close(conn: sqlite3.Connection, data: AutoCloseLogInput) -> tuple[int, bool]:
    """Insert one auto-close log row, deduped by (event_id, ip_asset_id).

    Returns (id, was_created): was_created is False when this pair was
    already logged, in which case nothing was written.
    """
    existing = fetch_auto_close_log_for_pair(conn, data.event_id, data.ip_asset_id)
    if existing is not None:
        return existing["id"], False

    with transaction(conn):
        cursor = conn.execute(
            """
            INSERT INTO auto_close_log (event_id, ip_asset_id, keyword_priority, llm_label, llm_confidence)
            VALUES (?, ?, ?, ?, ?)
            """,
            (data.event_id, data.ip_asset_id, data.keyword_priority, data.llm_label, data.llm_confidence),
        )
        log_id = cursor.lastrowid
    return log_id, True


def fetch_auto_close_log_for_pair(conn: sqlite3.Connection, event_id: int, ip_asset_id: int) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM auto_close_log WHERE event_id = ? AND ip_asset_id = ?", (event_id, ip_asset_id)
    ).fetchone()


def fetch_auto_close_logs(conn: sqlite3.Connection, audit_status: str | None = None) -> list[sqlite3.Row]:
    if audit_status is None:
        return conn.execute("SELECT * FROM auto_close_log ORDER BY closed_at DESC, id DESC").fetchall()
    return conn.execute(
        "SELECT * FROM auto_close_log WHERE audit_status = ? ORDER BY closed_at DESC, id DESC", (audit_status,)
    ).fetchall()


def select_audit_sample(conn: sqlite3.Connection, sample_size: int) -> list[sqlite3.Row]:
    """Mark up to sample_size un-sampled auto-close rows as sampled, chosen at random, and return them.

    Rows already marked sampled_for_audit are never re-selected — call this
    again later to draw a fresh sample from whatever has accumulated since.
    """
    with transaction(conn):
        rows = conn.execute(
            "SELECT id FROM auto_close_log WHERE sampled_for_audit = 0 ORDER BY RANDOM() LIMIT ?", (sample_size,)
        ).fetchall()
        ids = [row["id"] for row in rows]
        if ids:
            placeholders = ", ".join("?" for _ in ids)
            conn.execute(f"UPDATE auto_close_log SET sampled_for_audit = 1 WHERE id IN ({placeholders})", ids)
    if not ids:
        return []
    placeholders = ", ".join("?" for _ in ids)
    return conn.execute(f"SELECT * FROM auto_close_log WHERE id IN ({placeholders}) ORDER BY id", ids).fetchall()


def fetch_audit_queue(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """Sampled rows still awaiting a human audit decision."""
    return conn.execute(
        "SELECT * FROM auto_close_log WHERE sampled_for_audit = 1 AND audit_status = ? ORDER BY closed_at",
        (AUDIT_STATUS_PENDING,),
    ).fetchall()


def record_audit_result(
    conn: sqlite3.Connection, log_id: int, audit_status: str, audit_note: str | None = None
) -> None:
    """Record a human's sample-audit decision for one auto-close log row."""
    with transaction(conn):
        cursor = conn.execute(
            """
            UPDATE auto_close_log
            SET audit_status = ?, audit_note = ?, audited_at = ?
            WHERE id = ?
            """,
            (audit_status, audit_note, _now_iso(), log_id),
        )
        if cursor.rowcount == 0:
            raise ValueError(f"No auto_close_log row with id {log_id}.")


def auto_close_miss_rate(conn: sqlite3.Connection) -> float | None:
    """자동 종결 누락률 (docs/DESIGN.md 평가 지표): share of *audited* rows marked 누락 발견.

    Returns None when nothing has been audited yet (undefined, not 0.0).
    """
    row = conn.execute(
        """
        SELECT
            COUNT(*) AS audited,
            SUM(CASE WHEN audit_status = ? THEN 1 ELSE 0 END) AS missed
        FROM auto_close_log
        WHERE audit_status != ?
        """,
        (AUDIT_STATUS_MISSED, AUDIT_STATUS_PENDING),
    ).fetchone()
    if not row["audited"]:
        return None
    return row["missed"] / row["audited"]


@dataclass(frozen=True)
class GateAQueueInput:
    event_id: int
    ip_asset_id: int
    keyword_priority: str
    reasons: list[str]
    llm_label: str | None = None
    llm_confidence: float | None = None


def enqueue_gate_a(conn: sqlite3.Connection, data: GateAQueueInput) -> tuple[int, bool]:
    """Insert one 게이트 A queue row, deduped by (event_id, ip_asset_id).

    Returns (id, was_created): was_created is False when this pair was
    already queued, in which case nothing was written.
    """
    existing = fetch_gate_a_entry_for_pair(conn, data.event_id, data.ip_asset_id)
    if existing is not None:
        return existing["id"], False

    with transaction(conn):
        cursor = conn.execute(
            """
            INSERT INTO gate_a_queue (event_id, ip_asset_id, keyword_priority, llm_label, llm_confidence, reasons)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                data.event_id,
                data.ip_asset_id,
                data.keyword_priority,
                data.llm_label,
                data.llm_confidence,
                _REASON_SEPARATOR.join(data.reasons),
            ),
        )
        queue_id = cursor.lastrowid
    return queue_id, True


def fetch_gate_a_entry_for_pair(conn: sqlite3.Connection, event_id: int, ip_asset_id: int) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM gate_a_queue WHERE event_id = ? AND ip_asset_id = ?", (event_id, ip_asset_id)
    ).fetchone()


def fetch_gate_a_queue(conn: sqlite3.Connection, status: str = GATE_A_STATUS_PENDING) -> list[sqlite3.Row]:
    """Queue rows with the given status (대기 by default), oldest first."""
    return conn.execute(
        "SELECT * FROM gate_a_queue WHERE status = ? ORDER BY queued_at", (status,)
    ).fetchall()


def gate_a_reasons(row: sqlite3.Row) -> list[str]:
    """Split a gate_a_queue row's stored reasons string back into a list."""
    return [reason for reason in row["reasons"].split(_REASON_SEPARATOR) if reason]


def resolve_gate_a(conn: sqlite3.Connection, queue_id: int, status: str, resolution_note: str | None = None) -> None:
    """Record a human's 게이트 A 확인 decision (관련 확정 또는 무관 확정)."""
    if status not in (GATE_A_STATUS_RELATED, GATE_A_STATUS_UNRELATED):
        raise ValueError(f"status must be {GATE_A_STATUS_RELATED!r} or {GATE_A_STATUS_UNRELATED!r}, got {status!r}")
    with transaction(conn):
        cursor = conn.execute(
            """
            UPDATE gate_a_queue
            SET status = ?, resolution_note = ?, resolved_at = ?
            WHERE id = ?
            """,
            (status, resolution_note, _now_iso(), queue_id),
        )
        if cursor.rowcount == 0:
            raise ValueError(f"No gate_a_queue row with id {queue_id}.")

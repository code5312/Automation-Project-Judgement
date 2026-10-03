-- SQLite schema for the IP judgment ledger (docs/DESIGN.md 데이터 모델).
-- Judgment and Premise rows are append-only: this file defines no UPDATE
-- path, and the repositories layer never issues UPDATE/DELETE against them.
-- A correction is a new Judgment row that points back via previous_judgment_id.

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS event (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type TEXT NOT NULL,       -- 출시 / 공개 / 논문 / 오픈소스 공개 / 기술 변경
    source TEXT NOT NULL,           -- GitHub / Jira / 기획문서 등
    source_ref TEXT NOT NULL,       -- source 내 고유 ID, 중복 수신 방지
    source_url TEXT,
    detected_at TEXT NOT NULL,
    occurred_at TEXT,
    summary TEXT,
    status TEXT NOT NULL DEFAULT '신규' CHECK (status IN ('신규', '트리아지 완료', '종결')),
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    UNIQUE (source, source_ref)
);

CREATE TABLE IF NOT EXISTS ip_asset (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    application_number TEXT NOT NULL UNIQUE,
    asset_kind TEXT NOT NULL CHECK (asset_kind IN ('자사', '외부')),
    title TEXT,
    applicant TEXT,
    ipc_codes TEXT,                 -- '|'로 구분된 다중 코드; 비교는 집합 비교로 한다
    legal_status TEXT,
    source_url TEXT,
    last_fetched_at TEXT,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

-- from_type/to_type: 'event' | 'ip_asset' | 'judgment' | 'task'
CREATE TABLE IF NOT EXISTS link (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    from_type TEXT NOT NULL,
    from_id INTEGER NOT NULL,
    to_type TEXT NOT NULL,
    to_id INTEGER NOT NULL,
    basis TEXT NOT NULL,            -- IPC 일치 / 키워드 / 담당자 지정 / LLM 제안
    confidence_band TEXT,
    confirmed_by_human INTEGER NOT NULL DEFAULT 0 CHECK (confirmed_by_human IN (0, 1)),
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

-- decision is the fixed IP-action enum from docs/DESIGN.md 게이트 B, not the
-- prototype's relevance judgment (관련 있음/없음). reason must be non-blank;
-- assignee and review_deadline are required by 게이트 B validation in the
-- application layer, but migrated legacy rows use the literal placeholder
-- '이전 데이터' (see judgments/migrate_json.py) since the source JSON never
-- captured them.
CREATE TABLE IF NOT EXISTS judgment (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    application_number TEXT NOT NULL,
    review_technology TEXT NOT NULL,
    event_id INTEGER REFERENCES event (id),
    search_query TEXT,
    analysis_mode TEXT,
    decision TEXT NOT NULL CHECK (
        decision IN ('신규 출원 검토', '기존 IP 보강 검토', '유지', '정리 검토', '타사 특허 확인 필요')
    ),
    reason TEXT NOT NULL CHECK (length(trim(reason)) > 0),
    assignee TEXT NOT NULL CHECK (length(trim(assignee)) > 0),
    review_deadline TEXT NOT NULL CHECK (length(trim(review_deadline)) > 0),
    relevance_score REAL,
    review_priority TEXT,
    model_version TEXT,
    prompt_version TEXT,
    previous_judgment_id INTEGER REFERENCES judgment (id),
    migrated_from_json INTEGER NOT NULL DEFAULT 0 CHECK (migrated_from_json IN (0, 1)),
    legacy_note TEXT,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE INDEX IF NOT EXISTS idx_judgment_key ON judgment (application_number, review_technology);

-- Premise rows are the confirmed assumptions a Judgment leans on (docs/DESIGN.md
-- Premise). At least one row per Judgment is required by 게이트 B validation.
CREATE TABLE IF NOT EXISTS premise (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    judgment_id INTEGER NOT NULL REFERENCES judgment (id),
    source TEXT NOT NULL,
    check_key TEXT NOT NULL,
    expected_value TEXT NOT NULL,
    check_method TEXT,
    last_checked_at TEXT,
    status TEXT NOT NULL DEFAULT '유지' CHECK (status IN ('유지', '변경', '확인 불가')),
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE INDEX IF NOT EXISTS idx_premise_judgment ON premise (judgment_id);

CREATE TABLE IF NOT EXISTS task (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    judgment_id INTEGER NOT NULL REFERENCES judgment (id),
    title TEXT NOT NULL,
    assignee TEXT,
    deadline TEXT,
    external_ticket_url TEXT,
    status TEXT NOT NULL DEFAULT '대기',
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

-- Logs each 무관(무관) triage auto-close decision for one Event/IPAsset pair
-- (docs/DESIGN.md "명확하게 무관한 사건은 자동 종결하되 표본 감사로
-- 검증한다"). sampled_for_audit/audit_status let a human periodically
-- review a random sample and catch false negatives — "자동 종결 누락률"
-- (docs/DESIGN.md 평가 지표).
CREATE TABLE IF NOT EXISTS auto_close_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id INTEGER NOT NULL REFERENCES event (id),
    ip_asset_id INTEGER NOT NULL REFERENCES ip_asset (id),
    keyword_priority TEXT NOT NULL,
    llm_label TEXT,
    llm_confidence REAL,
    closed_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    sampled_for_audit INTEGER NOT NULL DEFAULT 0 CHECK (sampled_for_audit IN (0, 1)),
    audit_status TEXT NOT NULL DEFAULT '대기' CHECK (audit_status IN ('대기', '확인 완료', '누락 발견')),
    audit_note TEXT,
    audited_at TEXT,
    UNIQUE (event_id, ip_asset_id)
);

CREATE TABLE IF NOT EXISTS review_request (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    original_judgment_id INTEGER NOT NULL REFERENCES judgment (id),
    trigger_premise_id INTEGER REFERENCES premise (id),
    change_summary TEXT,
    status TEXT NOT NULL DEFAULT '대기' CHECK (status IN ('대기', '처리 중', '완료', '기각')),
    new_judgment_id INTEGER REFERENCES judgment (id),
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

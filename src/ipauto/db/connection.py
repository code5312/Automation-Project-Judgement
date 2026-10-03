"""SQLite connection setup: foreign keys on, transactional writes.

One file, per docs/DESIGN.md ("모든 데이터는 SQLite 한 파일에 저장한다").
"""

from __future__ import annotations

import os
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

_SCHEMA_PATH = Path(__file__).resolve().parent / "schema.sql"
_PROJECT_ROOT = Path(__file__).resolve().parents[3]

IPAUTO_DB_PATH_ENV = "IPAUTO_DB_PATH"
DEFAULT_DB_PATH = _PROJECT_ROOT / "data" / "ipauto.db"


def get_db_path() -> Path:
    override = os.getenv(IPAUTO_DB_PATH_ENV)
    return Path(override) if override else DEFAULT_DB_PATH


def connect(db_path: Path | None = None) -> sqlite3.Connection:
    """Open a connection with foreign keys enforced and row access by name.

    ``check_same_thread=False`` because the Streamlit app caches this
    connection with ``st.cache_resource`` and reuses it across reruns;
    Streamlit's ScriptRunner can execute each rerun on a different thread,
    which the sqlite3 module otherwise rejects outright even though access
    is never actually concurrent within one session. This does not make the
    connection safe for truly concurrent multi-user writes — that question
    ("저장소: SQLite로 충분한지, 동시 사용자 수") is still an open blocker in
    docs/PIPELINE.md, not solved here.
    """
    path = db_path if db_path is not None else get_db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    """Create tables if they do not exist yet. Safe to call every startup."""
    conn.executescript(_SCHEMA_PATH.read_text(encoding="utf-8"))
    conn.commit()


@contextmanager
def transaction(conn: sqlite3.Connection) -> Iterator[sqlite3.Connection]:
    """Wrap a block of writes in a single commit/rollback."""
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise

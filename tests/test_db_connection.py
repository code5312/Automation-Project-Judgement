"""Tests for SQLite connection setup.

Regression test for a real bug found while building the sample-audit
Streamlit page (docs/PIPELINE.md 단계 3): the connection ``st.cache_resource``
caches is reused across Streamlit reruns, and Streamlit's ScriptRunner can
execute each rerun on a different thread, which sqlite3 rejects unless
``check_same_thread=False``.
"""

from __future__ import annotations

import threading

from ipauto.db.connection import connect, init_db


def test_connection_usable_from_a_different_thread(tmp_path):
    conn = connect(tmp_path / "cross_thread.db")
    init_db(conn)

    errors: list[BaseException] = []

    def use_from_other_thread() -> None:
        try:
            conn.execute("SELECT 1").fetchone()
        except BaseException as exc:  # noqa: BLE001 - capture to report in the main thread
            errors.append(exc)

    thread = threading.Thread(target=use_from_other_thread)
    thread.start()
    thread.join(timeout=5)

    assert errors == []

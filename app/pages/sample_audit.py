"""자동 종결 표본 감사 화면 (docs/DESIGN.md "자동 종결하되 표본 감사로 검증", 단계 3).

무관(자동 종결)으로 라우팅된 사건↔IP 자산 쌍 중 일부를 무작위로 뽑아 사람이
다시 확인하고, 실제로 놓친 건이 있는지 기록한다 — 자동 종결 누락률
(docs/DESIGN.md 평가 지표). 저장·조회는 ``ipauto.db.repositories``에 있고,
이 파일은 화면만 그린다. Streamlit이 ``app/pages/`` 아래 파일을 자동으로
사이드바 페이지로 인식하므로 ``streamlit run app/streamlit_app.py``로 함께
뜬다.
"""

from __future__ import annotations

import streamlit as st

from ipauto.db.connection import connect, init_db
from ipauto.db.repositories import (
    AUDIT_STATUS_CONFIRMED,
    AUDIT_STATUS_MISSED,
    auto_close_miss_rate,
    fetch_audit_queue,
    fetch_auto_close_logs,
    fetch_event,
    fetch_ip_asset_by_id,
    record_audit_result,
    select_audit_sample,
)

DEFAULT_SAMPLE_SIZE = 5
MAX_SAMPLE_SIZE = 50


@st.cache_resource
def _get_connection():
    conn = connect()
    init_db(conn)
    return conn


def _render_queue_item(conn, log_row) -> None:
    event = fetch_event(conn, log_row["event_id"])
    asset = fetch_ip_asset_by_id(conn, log_row["ip_asset_id"])

    with st.container(border=True):
        st.markdown(f"**사건:** {event['summary'] if event else '(삭제된 사건)'}")
        asset_title = asset["title"] if asset else "(삭제된 자산)"
        asset_app_no = asset["application_number"] if asset else "-"
        st.write(f"**IP 자산:** {asset_title} ({asset_app_no})")
        st.write(f"**키워드/IPC 점수 밴드:** {log_row['keyword_priority']}")
        if log_row["llm_label"]:
            st.write(f"**LLM 판정:** {log_row['llm_label']} (확신도 {log_row['llm_confidence']})")
        else:
            st.caption("LLM 판정 없이 키워드/IPC 신호만으로 종결됨")
        st.caption(f"종결 시각: {log_row['closed_at']}")

        note = st.text_input("감사 메모 (선택)", key=f"note_{log_row['id']}")
        confirm_col, missed_col = st.columns(2)
        if confirm_col.button("✅ 확인 완료 (제대로 종결됨)", key=f"confirm_{log_row['id']}", use_container_width=True):
            record_audit_result(conn, log_row["id"], AUDIT_STATUS_CONFIRMED, note or None)
            st.rerun()
        if missed_col.button("⚠ 누락 발견 (다시 봐야 함)", key=f"missed_{log_row['id']}", use_container_width=True):
            record_audit_result(conn, log_row["id"], AUDIT_STATUS_MISSED, note or None)
            st.rerun()


def main() -> None:
    st.set_page_config(page_title="자동 종결 표본 감사", page_icon="\U0001f50d", layout="wide")
    conn = _get_connection()

    st.title("자동 종결 표본 감사")
    st.caption(
        "무관으로 자동 종결된 사건·IP 자산 쌍을 무작위로 뽑아 사람이 다시 확인합니다. "
        "최종 판단은 항상 사람이 합니다."
    )

    all_logs = fetch_auto_close_logs(conn)
    pending_queue = fetch_audit_queue(conn)
    miss_rate = auto_close_miss_rate(conn)

    summary_cols = st.columns(3)
    summary_cols[0].metric("전체 자동 종결 건", f"{len(all_logs)}건")
    summary_cols[1].metric("감사 대기", f"{len(pending_queue)}건")
    summary_cols[2].metric("누락률 (감사 완료 기준)", f"{miss_rate:.1%}" if miss_rate is not None else "집계 전")

    st.divider()

    with st.form("sample_form"):
        sample_size = st.number_input(
            "새로 뽑을 표본 수", min_value=1, max_value=MAX_SAMPLE_SIZE, value=DEFAULT_SAMPLE_SIZE
        )
        drawn = st.form_submit_button("무작위 표본 뽑기", type="primary")
    if drawn:
        newly_sampled = select_audit_sample(conn, sample_size=int(sample_size))
        if newly_sampled:
            st.success(f"{len(newly_sampled)}건을 새로 뽑았습니다.")
        else:
            st.info("뽑을 수 있는, 아직 표본으로 뽑히지 않은 자동 종결 건이 없습니다.")
        st.rerun()

    if not pending_queue:
        st.info("감사 대기 중인 표본이 없습니다. 위에서 표본을 먼저 뽑아주세요.")
        return

    st.subheader(f"감사 대기 ({len(pending_queue)}건)")
    for log_row in pending_queue:
        _render_queue_item(conn, log_row)


if __name__ == "__main__":
    main()

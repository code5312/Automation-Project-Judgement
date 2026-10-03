"""게이트 A 화면 — 애매한 사건 확인 (docs/DESIGN.md "애매: 게이트 A로 보내 사람이 검토 여부를 정한다", 단계 3).

``ipauto.triage.routing.decide_triage``가 애매로 라우팅한 사건↔IP 자산 쌍을
사람이 다시 보고 관련 확정(판단 카드로 진행) 또는 무관 확정(기각)으로
확정한다. 애매 판정 근거(신호 불일치·중간 확신도·정보 누락·고위험 유형·과거
판단 충돌 중 해당하는 것)를 그대로 보여줘 사람이 왜 여기 왔는지 바로
알 수 있게 한다. 저장·조회는 ``ipauto.db.repositories``에 있고, 이 파일은
화면만 그린다.
"""

from __future__ import annotations

import streamlit as st

from ipauto.db.connection import connect, init_db
from ipauto.db.repositories import (
    GATE_A_STATUS_RELATED,
    GATE_A_STATUS_UNRELATED,
    fetch_event,
    fetch_gate_a_queue,
    fetch_ip_asset_by_id,
    gate_a_reasons,
    resolve_gate_a,
)


@st.cache_resource
def _get_connection():
    conn = connect()
    init_db(conn)
    return conn


def _render_queue_item(conn, queue_row) -> None:
    event = fetch_event(conn, queue_row["event_id"])
    asset = fetch_ip_asset_by_id(conn, queue_row["ip_asset_id"])

    with st.container(border=True):
        st.markdown(f"**사건:** {event['summary'] if event else '(삭제된 사건)'}")
        if event:
            st.caption(f"유형: {event['event_type']}  |  출처: {event['source']}")
        asset_title = asset["title"] if asset else "(삭제된 자산)"
        asset_app_no = asset["application_number"] if asset else "-"
        st.write(f"**IP 자산:** {asset_title} ({asset_app_no})")
        st.write(f"**키워드/IPC 점수 밴드:** {queue_row['keyword_priority']}")
        if queue_row["llm_label"]:
            st.write(f"**LLM 판정:** {queue_row['llm_label']} (확신도 {queue_row['llm_confidence']})")
        else:
            st.caption("LLM 판정 없이 키워드/IPC 신호만으로 라우팅됨")

        st.markdown("**왜 애매로 분류됐나요?**")
        for reason in gate_a_reasons(queue_row):
            st.warning(reason, icon="⚠")
        st.caption(f"대기열 등록 시각: {queue_row['queued_at']}")

        note = st.text_input("확인 메모 (선택)", key=f"note_{queue_row['id']}")
        related_col, unrelated_col = st.columns(2)
        if related_col.button(
            "✅ 관련으로 확정 (검토 진행)", key=f"related_{queue_row['id']}", use_container_width=True
        ):
            resolve_gate_a(conn, queue_row["id"], GATE_A_STATUS_RELATED, note or None)
            st.rerun()
        if unrelated_col.button(
            "🚫 무관으로 확정 (기각)", key=f"unrelated_{queue_row['id']}", use_container_width=True
        ):
            resolve_gate_a(conn, queue_row["id"], GATE_A_STATUS_UNRELATED, note or None)
            st.rerun()


def main() -> None:
    st.set_page_config(page_title="게이트 A: 애매한 사건 확인", page_icon="\U0001f6a6", layout="wide")
    conn = _get_connection()

    st.title("게이트 A — 애매한 사건 확인")
    st.caption(
        "자동으로 무관·관련을 가르기 애매한 사건·IP 자산 쌍을 사람이 직접 확인합니다. "
        "본 판정은 법률 자문이 아니며, 최종 IP 조치 결정은 게이트 B에서 사람이 내립니다."
    )

    pending_queue = fetch_gate_a_queue(conn)
    st.metric("확인 대기", f"{len(pending_queue)}건")
    st.divider()

    if not pending_queue:
        st.info("게이트 A 대기열이 비어 있습니다.")
        return

    st.subheader(f"확인 대기 ({len(pending_queue)}건)")
    for queue_row in pending_queue:
        _render_queue_item(conn, queue_row)


if __name__ == "__main__":
    main()

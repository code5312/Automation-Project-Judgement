"""Streamlit UI for the human-centered KIPRIS patent review MVP.

Search screen + 게이트 B 저장 폼 (docs/DESIGN.md IP 조치 결정), backed by the
SQLite ledger (docs/PIPELINE.md 단계 1). Judgment storage, validation, and
history comparison live in ``ipauto.judgments``/``ipauto.db``; this module is
presentation only.
"""

from __future__ import annotations

import datetime as dt

import streamlit as st

from ipauto.config import get_kipris_access_key, mask_secret
from ipauto.connectors.kipris import DEFAULT_MAX_PAGES_PER_QUERY, KiprisError, fetch_all
from ipauto.db.connection import connect, init_db
from ipauto.db.repositories import DECISION_CHOICES
from ipauto.judgments.compare import compare_with_premises
from ipauto.judgments.service import (
    APPLICANT_FIELD,
    APPLICATION_FIELD,
    IPC_FIELD,
    STATUS_FIELD,
    TITLE_FIELD,
    DuplicateJudgmentError,
    JudgmentValidationError,
    history_for_application,
    premises_for_judgment,
    save_gate_b_judgment,
)
from ipauto.scoring.bands import PRIORITY_HIGH, PRIORITY_LOW, PRIORITY_MEDIUM
from ipauto.scoring.keywords import (
    ANALYSIS_MODE_FIELD,
    GENERIC_FALLBACK_MESSAGE,
    MATCHED_FIELD,
    MODE_GENERIC_KEYWORD,
    PRIORITY_FIELD,
    REASON_FIELD,
    SCORE_FIELD,
    rank_records,
)

SEARCH_COUNT = 20
PREMISE_SLOT_COUNT = 3


@st.cache_resource
def _get_connection():
    conn = connect()
    init_db(conn)
    return conn


def _priority_badge(priority: str) -> str:
    colors = {
        PRIORITY_HIGH: "\U0001f534",
        PRIORITY_MEDIUM: "\U0001f7e0",
        PRIORITY_LOW: "\U0001f7e2",
    }
    return f"{colors.get(priority, '⚪')} {priority}"


def _default_premise_slots(record: dict[str, str | float]) -> list[tuple[str, str, str]]:
    """Pre-fill premise inputs from the current record; the user confirms or edits them."""
    return [
        ("KIPRIS 재조회", STATUS_FIELD, str(record.get(STATUS_FIELD) or "")),
        ("KIPRIS 재조회", APPLICANT_FIELD, str(record.get(APPLICANT_FIELD) or "")),
        ("KIPRIS 재조회", IPC_FIELD, str(record.get(IPC_FIELD) or "")),
    ]


def _render_record_card(
    conn,
    rank: int,
    record: dict[str, str | float],
    review_technology: str,
) -> None:
    title = record.get(TITLE_FIELD) or "명칭 없음"
    application_number = str(record.get(APPLICATION_FIELD) or "")
    priority = str(record.get(PRIORITY_FIELD) or "")

    with st.container(border=True):
        rank_col, title_col, score_col, priority_col = st.columns([0.55, 4.0, 1.0, 1.6])
        rank_col.markdown(f"**#{rank}**")
        title_col.markdown(f"**{title}**")
        score_col.metric("관련도", f"{record.get(SCORE_FIELD, 0)}/100")
        priority_col.markdown(f"**{_priority_badge(priority)}**")

        applicant_col, application_col, status_col = st.columns([2, 1.5, 1])
        applicant_col.write(f"**출원인:** {record.get(APPLICANT_FIELD) or '-'}")
        application_col.write(f"**출원번호:** {application_number or '-'}")
        status_col.write(f"**등록상태:** {record.get(STATUS_FIELD) or '-'}")

        st.markdown("**점수 이유**")
        st.info(record.get(REASON_FIELD) or "-")

        with st.expander("상세 특허 정보"):
            st.write(f"**IPC:** {record.get(IPC_FIELD) or '-'}")
            st.write(f"**matched_concepts:** {record.get(MATCHED_FIELD) or '-'}")
            st.write(f"**score_reason:** {record.get(REASON_FIELD) or '-'}")
            st.write(f"**초록:** {record.get('초록') or '-'}")

        history = history_for_application(conn, application_number) if application_number else []
        if history:
            st.caption("이 특허는 이전에 검토한 기록이 있습니다.")
            latest = history[0]
            differences = compare_with_premises(record, premises_for_judgment(conn, latest["id"]))
            if differences:
                st.warning("⚠ 재검토 필요")
                for check_key, previous, current in differences:
                    st.write(f"**{check_key}:** {previous or '(저장된 값 없음)'} → {current or '(저장된 값 없음)'}")
            else:
                st.success("현재 확인된 주요 특허정보 변화 없음")
            with st.expander(f"이전 판단 기록 {len(history)}건 확인"):
                for previous in history:
                    st.markdown(f"**{previous['decision']}** · {previous['created_at']}")
                    st.write(f"판단 이유: {previous['reason']}")
                    st.write(f"담당자: {previous['assignee']}  |  재검토 기한: {previous['review_deadline']}")
                    if previous["migrated_from_json"]:
                        st.caption(f"마이그레이션된 이전 기록입니다. {previous['legacy_note'] or ''}")

        st.markdown("#### 사람 판단 및 이유 기록 (게이트 B)")
        st.caption("최종 판단은 사용자가 직접 수행합니다. 본 도구의 추천은 법률 자문이 아닙니다.")
        form_key_suffix = application_number or str(rank)
        with st.form(f"judgment_form_{form_key_suffix}"):
            decision = st.selectbox("결정", options=DECISION_CHOICES, index=None, placeholder="결정을 선택하세요")
            reason = st.text_area("판단 이유", placeholder="사람이 판단한 근거를 직접 작성해주세요.")

            st.markdown("**전제** (최소 1개, 기대값이 비어 있는 줄은 무시됩니다)")
            premise_inputs = []
            for i, (default_source, default_key, default_value) in enumerate(_default_premise_slots(record), start=1):
                cols = st.columns([1.2, 1, 2])
                source = cols[0].text_input(
                    f"전제 {i} 출처", value=default_source, key=f"premise_source_{form_key_suffix}_{i}"
                )
                check_key = cols[1].text_input(
                    f"전제 {i} 확인 키", value=default_key, key=f"premise_key_{form_key_suffix}_{i}"
                )
                expected_value = cols[2].text_input(
                    f"전제 {i} 기대값", value=default_value, key=f"premise_value_{form_key_suffix}_{i}"
                )
                premise_inputs.append((source, check_key, expected_value))

            assignee_col, deadline_col = st.columns(2)
            assignee = assignee_col.text_input("담당자")
            review_deadline = deadline_col.date_input("재검토 기한", value=dt.date.today() + dt.timedelta(days=90))
            save_clicked = st.form_submit_button("판단 저장")

        if save_clicked:
            try:
                save_gate_b_judgment(
                    conn,
                    application_number=application_number,
                    review_technology=review_technology,
                    decision=decision or "",
                    reason=reason,
                    premises=premise_inputs,
                    assignee=assignee,
                    review_deadline=review_deadline.isoformat(),
                    analysis_mode=str(record.get(ANALYSIS_MODE_FIELD) or ""),
                    relevance_score=float(record.get(SCORE_FIELD) or 0),
                    review_priority=str(record.get(PRIORITY_FIELD) or ""),
                )
                st.success("판단 이력을 저장했습니다.")
                st.rerun()
            except (JudgmentValidationError, DuplicateJudgmentError) as exc:
                st.error(str(exc))


def main() -> None:
    st.set_page_config(
        page_title="사람 판단 중심 특허 검토",
        page_icon="\U0001f50e",
        layout="wide",
    )
    conn = _get_connection()

    st.title("사람 판단 중심 특허 검토 업무 자동화")
    st.write(
        "KIPRIS Plus의 실제 특허 데이터를 기반으로, 검색된 특허 중 사용자가 먼저 검토할 후보의 우선순위를 제공합니다."
    )
    st.info(
        "본 관련도 점수는 선행특허 여부, 등록 가능성, 침해 여부 등 법적 판단을 의미하지 않습니다.\n"
        "사람이 우선 검토할 특허를 정렬하기 위한 보조 지표이며, 법률 자문이 아닙니다."
    )
    st.caption("① 특허 검색 및 후보 확인  →  ② 사람 판단·이유 기록  →  ③ 이전 판단·재검토 확인")

    with st.form("patent_search_form"):
        search_col, technology_col = st.columns(2)
        search_query_raw = search_col.text_input(
            "KIPRIS 검색 범위",
            value="배터리",
            help="KIPRIS Plus API에 전달할 검색어입니다. 쉼표(,)로 여러 검색어를 입력하면 모두 검색해 합칩니다.",
        )
        technology = technology_col.text_input(
            "검토하려는 기술",
            value="전기차 배터리 냉각",
            help="수집한 실제 특허를 이 기술 개념에 따라 점수화합니다.",
        )
        submitted = st.form_submit_button(
            "특허 검색 및 분석",
            type="primary",
            use_container_width=True,
        )

    if submitted:
        st.session_state.pop("ranked_patents", None)
        search_queries = [term.strip() for term in search_query_raw.split(",") if term.strip()]
        if not search_queries or not technology.strip():
            st.error("KIPRIS 검색 범위와 검토 기술을 모두 입력해주세요.")
        else:
            access_key = get_kipris_access_key()
            if not access_key:
                st.error("KIPRIS_ACCESS_KEY 환경변수가 없습니다. 셸에서 접근키를 환경변수로 설정한 후 실행해주세요.")
            else:
                try:
                    with st.spinner("KIPRIS Plus에서 실제 특허 데이터를 가져오고 분석하는 중..."):
                        result = fetch_all(
                            search_queries,
                            access_key,
                            page_size=SEARCH_COUNT,
                            max_pages_per_query=DEFAULT_MAX_PAGES_PER_QUERY,
                        )
                        if result.records:
                            ranked = rank_records(technology.strip(), [r.fields for r in result.records])
                            st.session_state["ranked_patents"] = ranked
                            st.session_state["analysis_inputs"] = (", ".join(search_queries), technology.strip())
                            st.session_state["duplicate_count"] = result.duplicate_count
                        else:
                            st.warning(
                                "KIPRIS Plus 응답에서 특허 레코드를 찾지 못했습니다. "
                                "검색어를 확인하거나 다시 시도해주세요."
                            )
                except KiprisError as exc:
                    st.error(f"KIPRIS 검색 또는 분석 중 문제가 발생했습니다: {mask_secret(str(exc), access_key)}")

    ranked_patents = st.session_state.get("ranked_patents")
    if ranked_patents is None:
        return

    high_count = sum(row[PRIORITY_FIELD] == PRIORITY_HIGH for row in ranked_patents)
    medium_count = sum(row[PRIORITY_FIELD] == PRIORITY_MEDIUM for row in ranked_patents)
    low_count = sum(row[PRIORITY_FIELD] == PRIORITY_LOW for row in ranked_patents)
    review_technology = st.session_state["analysis_inputs"][1]
    st.subheader("분석 결과")
    st.caption(f"KIPRIS 검색: {st.session_state['analysis_inputs'][0]}  |  평가 기술: {review_technology}")
    duplicate_count = st.session_state.get("duplicate_count", 0)
    if duplicate_count:
        st.caption(f"동일 출원번호 중복 {duplicate_count}건 제거됨")
    summary_cols = st.columns(4)
    summary_cols[0].metric("검색된 특허", f"{len(ranked_patents)}건")
    summary_cols[1].metric("높음", f"{high_count}건")
    summary_cols[2].metric("보통", f"{medium_count}건")
    summary_cols[3].metric("낮음", f"{low_count}건")
    if ranked_patents and ranked_patents[0].get(ANALYSIS_MODE_FIELD) == MODE_GENERIC_KEYWORD:
        st.info(GENERIC_FALLBACK_MESSAGE)

    for rank, record in enumerate(ranked_patents, start=1):
        _render_record_card(conn, rank, record, review_technology)


if __name__ == "__main__":
    main()

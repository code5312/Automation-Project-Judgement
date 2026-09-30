"""Streamlit UI for the human-centered KIPRIS patent review MVP.

Search screen + 게이트 B 저장 폼 (docs/DESIGN.md IP 조치 결정). The full
게이트 B 결정 열거형/전제/담당자·기한 fields and the SQLite-backed store are
phase 1 work; this phase keeps the JSON-backed relevance judgment from the
prototype, translated to real Korean and with a blank-reason guard.
"""

from __future__ import annotations

import streamlit as st

from ipauto.config import get_kipris_access_key, mask_secret
from ipauto.connectors.kipris import KiprisError, fetch_page
from ipauto.judgments.compare import compare_with_latest
from ipauto.judgments.service import (
    APPLICANT_FIELD,
    APPLICATION_FIELD,
    IPC_FIELD,
    REVIEW_CHOICES,
    STATUS_FIELD,
    TITLE_FIELD,
    JudgmentStoreError,
    load_judgments,
    save_judgment,
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


def _priority_badge(priority: str) -> str:
    colors = {
        PRIORITY_HIGH: "\U0001f534",
        PRIORITY_MEDIUM: "\U0001f7e0",
        PRIORITY_LOW: "\U0001f7e2",
    }
    return f"{colors.get(priority, '⚪')} {priority}"


def _display_snapshot(value: str) -> str:
    return value if value else "(저장된 값 없음)"


def _render_record_card(
    rank: int,
    record: dict[str, str | float],
    histories: dict[str, list[dict[str, str | float]]],
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

        history = histories.get(application_number, [])
        if history:
            st.caption("이 특허는 이전에 검토한 기록이 있습니다.")
            differences = compare_with_latest(record, history)
            if differences:
                st.warning("⚠ 재검토 필요")
                for display_name, previous, current in differences:
                    st.write(f"**{display_name}:** {_display_snapshot(previous)} → {_display_snapshot(current)}")
            else:
                st.success("현재 확인된 주요 특허정보 변화 없음")
            with st.expander(f"이전 판단 기록 {len(history)}건 확인"):
                for previous in sorted(history, key=lambda entry: str(entry.get("decisionTime", "")), reverse=True):
                    st.markdown(f"**{previous.get('decision', '-')}** · {previous.get('decisionTime', '-')}")
                    st.write(f"판단 이유: {previous.get('decisionReason') or '-'}")
                    st.write(
                        f"판단 당시 등록상태: {previous.get('registerStatusAtDecision') or '-'}  |  "
                        f"출원인: {previous.get('applicantNameAtDecision') or '-'}  |  "
                        f"IPC: {previous.get('ipcNumberAtDecision') or '-'}"
                    )

        st.markdown("#### 사람 판단 및 이유 기록")
        st.caption("최종 판단은 사용자가 직접 수행합니다. 본 도구의 추천은 법률 자문이 아닙니다.")
        review_key = f"human_review_{application_number or rank}"
        reason_key = f"human_reason_{application_number or rank}"
        with st.form(f"judgment_form_{application_number or rank}"):
            decision = st.radio(
                "판단",
                options=REVIEW_CHOICES,
                index=None,
                horizontal=True,
                key=review_key,
            )
            decision_reason = st.text_area(
                "판단 이유",
                key=reason_key,
                placeholder="사람이 판단한 근거를 직접 작성해주세요.",
            )
            save_clicked = st.form_submit_button("판단 저장")
        if save_clicked:
            if not decision:
                st.error("판단을 선택한 후 저장해주세요.")
            elif not decision_reason.strip():
                st.error("판단 이유를 입력한 후 저장해주세요.")
            else:
                try:
                    saved = save_judgment(record, decision, decision_reason, SCORE_FIELD, PRIORITY_FIELD)
                    histories.setdefault(application_number, []).append(saved)
                    st.success("판단 이력을 data/judgments.json에 추가 저장했습니다.")
                except (OSError, ValueError, JudgmentStoreError) as exc:
                    st.error(f"판단 기록을 저장하지 못했습니다: {exc}")


def main() -> None:
    st.set_page_config(
        page_title="사람 판단 중심 특허 검토",
        page_icon="\U0001f50e",
        layout="wide",
    )
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
        search_query = search_col.text_input(
            "KIPRIS 검색 범위",
            value="배터리",
            help="KIPRIS Plus API에 전달할 검색어입니다.",
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
        if not search_query.strip() or not technology.strip():
            st.error("KIPRIS 검색 범위와 검토 기술을 모두 입력해주세요.")
        else:
            access_key = get_kipris_access_key()
            if not access_key:
                st.error("KIPRIS_ACCESS_KEY 환경변수가 없습니다. 셸에서 접근키를 환경변수로 설정한 후 실행해주세요.")
            else:
                try:
                    with st.spinner("KIPRIS Plus에서 실제 특허 데이터를 가져오고 분석하는 중..."):
                        page = fetch_page(search_query.strip(), access_key, count=SEARCH_COUNT)
                        if page.records:
                            ranked = rank_records(technology.strip(), [r.fields for r in page.records])
                            st.session_state["ranked_patents"] = ranked
                            st.session_state["analysis_inputs"] = (search_query.strip(), technology.strip())
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
    st.subheader("분석 결과")
    st.caption(
        f"KIPRIS 검색: {st.session_state['analysis_inputs'][0]}  |  평가 기술: {st.session_state['analysis_inputs'][1]}"
    )
    summary_cols = st.columns(4)
    summary_cols[0].metric("검색된 특허", f"{len(ranked_patents)}건")
    summary_cols[1].metric("높음", f"{high_count}건")
    summary_cols[2].metric("보통", f"{medium_count}건")
    summary_cols[3].metric("낮음", f"{low_count}건")
    if ranked_patents and ranked_patents[0].get(ANALYSIS_MODE_FIELD) == MODE_GENERIC_KEYWORD:
        st.info(GENERIC_FALLBACK_MESSAGE)

    try:
        history_entries = load_judgments()
    except JudgmentStoreError as exc:
        st.error(f"이전 판단 기록을 불러오지 못했습니다: {exc}")
        history_entries = []
    histories: dict[str, list[dict[str, str | float]]] = {}
    for entry in history_entries:
        application_number = str(entry.get("applicationNumber") or "")
        if application_number:
            histories.setdefault(application_number, []).append(entry)

    for rank, record in enumerate(ranked_patents, start=1):
        _render_record_card(rank, record, histories)


if __name__ == "__main__":
    main()

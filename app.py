"""Streamlit demo UI for the human-centered KIPRIS patent review MVP."""

from __future__ import annotations

import os
import json
import re
from datetime import datetime
from pathlib import Path

import streamlit as st

import main as patent_mvp


TITLE_FIELD = next(iter(patent_mvp.FIELDS))
APPLICATION_FIELD = list(patent_mvp.FIELDS)[1]
APPLICANT_FIELD = list(patent_mvp.FIELDS)[2]
IPC_FIELD = "IPC"
STATUS_FIELD = list(patent_mvp.FIELDS)[4]
ABSTRACT_FIELD = list(patent_mvp.FIELDS)[5]
REVIEW_CHOICES = (
    "\uad00\ub828 \uc788\uc74c",
    "\uad00\ub828 \uc5c6\uc74c",
    "\ucd94\uac00 \uac80\ud1a0",
)
DATA_DIR = Path(__file__).resolve().parent / "data"
JUDGMENTS_PATH = DATA_DIR / "judgments.json"
CHANGE_FIELDS = (
    ("registerStatusAtDecision", STATUS_FIELD, "\ub4f1\ub85d\uc0c1\ud0dc"),
    ("applicantNameAtDecision", APPLICANT_FIELD, "\ucd9c\uc6d0\uc778"),
    ("ipcNumberAtDecision", IPC_FIELD, "IPC"),
)


def load_judgments() -> list[dict[str, str | float]]:
    """Load append-only local decision history; do not silently replace a bad file."""
    if not JUDGMENTS_PATH.exists():
        return []
    try:
        with JUDGMENTS_PATH.open("r", encoding="utf-8") as source:
            data = json.load(source)
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError("data/judgments.json\uc744 \uc77d\uc9c0 \ubabb\ud588\uc2b5\ub2c8\ub2e4. \ud30c\uc77c\uc774 \uc190\uc0c1\ub418\uc9c0 \uc54a\uc558\ub294\uc9c0 \ud655\uc778\ud574\uc8fc\uc138\uc694.") from exc
    if not isinstance(data, list):
        raise RuntimeError("data/judgments.json \ud615\uc2dd\uc774 \uc62c\ubc14\ub974\uc9c0 \uc54a\uc2b5\ub2c8\ub2e4. \uae30\uc874 \ud310\ub2e8 \uae30\ub85d\uc744 \uc720\uc9c0\ud558\uae30 \uc704\ud574 \uc790\ub3d9 \uc800\uc7a5\uc744 \uc911\ub2e8\ud569\ub2c8\ub2e4.")
    return [entry for entry in data if isinstance(entry, dict)]


def save_judgment(record: dict[str, str | float], decision: str, reason: str) -> dict[str, str | float]:
    """Append a snapshot of a person's decision without deleting earlier entries."""
    history = load_judgments()
    entry: dict[str, str | float] = {
        "applicationNumber": str(record.get(APPLICATION_FIELD) or ""),
        "inventionTitle": str(record.get(TITLE_FIELD) or ""),
        "decision": decision,
        "decisionReason": reason.strip(),
        "decisionTime": datetime.now().astimezone().isoformat(timespec="seconds"),
        "registerStatusAtDecision": str(record.get(STATUS_FIELD) or ""),
        "applicantNameAtDecision": str(record.get(APPLICANT_FIELD) or ""),
        "ipcNumberAtDecision": str(record.get(IPC_FIELD) or ""),
        "relevanceScoreAtDecision": float(record.get(patent_mvp.SCORE_FIELD) or 0),
        "reviewPriorityAtDecision": str(record.get(patent_mvp.PRIORITY_FIELD) or ""),
    }
    history.append(entry)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    temporary_path = JUDGMENTS_PATH.with_suffix(".json.tmp")
    with temporary_path.open("w", encoding="utf-8") as destination:
        json.dump(history, destination, ensure_ascii=False, indent=2)
        destination.write("\n")
    temporary_path.replace(JUDGMENTS_PATH)
    return entry


def _normalized(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def compare_with_latest(record: dict[str, str | float], history: list[dict[str, str | float]]) -> list[tuple[str, str, str]]:
    """Compare current KIPRIS fields with the latest saved human-review snapshot."""
    if not history:
        return []
    latest = max(history, key=lambda entry: str(entry.get("decisionTime", "")))
    differences = []
    for stored_key, current_key, display_name in CHANGE_FIELDS:
        previous = _normalized(latest.get(stored_key))
        current = _normalized(record.get(current_key))
        if previous != current:
            differences.append((display_name, previous, current))
    return differences


def _display_snapshot(value: str) -> str:
    return value if value else "(\uc800\uc7a5\ub41c \uac12 \uc5c6\uc74c)"


def _priority_badge(priority: str) -> str:
    colors = {
        patent_mvp.PRIORITY_HIGH: "\U0001f534",
        patent_mvp.PRIORITY_MEDIUM: "\U0001f7e0",
        patent_mvp.PRIORITY_LOW: "\U0001f7e2",
    }
    return f"{colors.get(priority, '\u26aa')} {priority}"


def _render_record_card(
    rank: int,
    record: dict[str, str | float],
    histories: dict[str, list[dict[str, str | float]]],
) -> None:
    title = record.get(TITLE_FIELD) or "\uba85\uce6d \uc5c6\uc74c"
    application_number = str(record.get(APPLICATION_FIELD) or "")
    priority = str(record.get(patent_mvp.PRIORITY_FIELD) or "")

    with st.container(border=True):
        rank_col, title_col, score_col, priority_col = st.columns([0.55, 4.0, 1.0, 1.6])
        rank_col.markdown(f"**#{rank}**")
        title_col.markdown(f"**{title}**")
        score_col.metric("\uad00\ub828\ub3c4", f"{record.get(patent_mvp.SCORE_FIELD, 0)}/100")
        priority_col.markdown(f"**{_priority_badge(priority)}**")

        applicant_col, application_col, status_col = st.columns([2, 1.5, 1])
        applicant_col.write(f"**\ucd9c\uc6d0\uc778:** {record.get(APPLICANT_FIELD) or '-'}")
        application_col.write(f"**\ucd9c\uc6d0\ubc88\ud638:** {application_number or '-'}")
        status_col.write(f"**\ub4f1\ub85d\uc0c1\ud0dc:** {record.get(STATUS_FIELD) or '-'}")

        st.markdown("**\uc810\uc218 \uc774\uc720**")
        st.info(record.get(patent_mvp.REASON_FIELD) or "-")

        with st.expander("\uc0c1\uc138 \ud2b9\ud5c8 \uc815\ubcf4"):
            st.write(f"**IPC:** {record.get(IPC_FIELD) or '-'}")
            st.write(f"**matched_concepts:** {record.get(patent_mvp.MATCHED_FIELD) or '-'}")
            st.write(f"**score_reason:** {record.get(patent_mvp.REASON_FIELD) or '-'}")
            st.write(f"**\ucd08\ub85d:** {record.get(ABSTRACT_FIELD) or '-'}")

        history = histories.get(application_number, [])
        if history:
            st.caption("\uc774 \ud2b9\ud5c8\ub294 \uc774\uc804\uc5d0 \uac80\ud1a0\ud55c \uae30\ub85d\uc774 \uc788\uc2b5\ub2c8\ub2e4.")
            differences = compare_with_latest(record, history)
            if differences:
                st.warning("\u26a0 \uc7ac\uac80\ud1a0 \ud544\uc694")
                for display_name, previous, current in differences:
                    st.write(f"**{display_name}:** {_display_snapshot(previous)} \u2192 {_display_snapshot(current)}")
            else:
                st.success("\ud604\uc7ac \ud655\uc778\ub41c \uc8fc\uc694 \ud2b9\ud5c8\uc815\ubcf4 \ubcc0\ud654 \uc5c6\uc74c")
            with st.expander(f"\uc774\uc804 \ud310\ub2e8 \uae30\ub85d {len(history)}\uac74 \ud655\uc778"):
                for previous in sorted(history, key=lambda entry: str(entry.get("decisionTime", "")), reverse=True):
                    st.markdown(f"**{previous.get('decision', '-')}** \u00b7 {previous.get('decisionTime', '-')}")
                    st.write(f"\ud310\ub2e8 \uc774\uc720: {previous.get('decisionReason') or '-'}")
                    st.write(
                        f"\ud310\ub2e8 \ub2f9\uc2dc \ub4f1\ub85d\uc0c1\ud0dc: {previous.get('registerStatusAtDecision') or '-'}  |  "
                        f"\ucd9c\uc6d0\uc778: {previous.get('applicantNameAtDecision') or '-'}  |  "
                        f"IPC: {previous.get('ipcNumberAtDecision') or '-'}"
                    )

        st.markdown("#### \uc0ac\ub78c \ud310\ub2e8 \ubc0f \uc774\uc720 \uae30\ub85d")
        st.caption("\ucd5c\uc885 \ud310\ub2e8\uc740 \uc0ac\uc6a9\uc790\uac00 \uc9c1\uc811 \uc218\ud589\ud569\ub2c8\ub2e4.")
        review_key = f"human_review_{application_number or rank}"
        reason_key = f"human_reason_{application_number or rank}"
        with st.form(f"judgment_form_{application_number or rank}"):
            decision = st.radio(
                "\ud310\ub2e8",
                options=REVIEW_CHOICES,
                index=None,
                horizontal=True,
                key=review_key,
            )
            decision_reason = st.text_area(
                "\ud310\ub2e8 \uc774\uc720",
                key=reason_key,
                placeholder="\uc0ac\ub78c\uc774 \ud310\ub2e8\ud55c \uadfc\uac70\ub97c \uc9c1\uc811 \uc791\uc131\ud574\uc8fc\uc138\uc694.",
            )
            save_clicked = st.form_submit_button("\ud310\ub2e8 \uc800\uc7a5")
        if save_clicked:
            if not decision:
                st.error("\ud310\ub2e8\uc744 \uc120\ud0dd\ud55c \ud6c4 \uc800\uc7a5\ud574\uc8fc\uc138\uc694.")
            else:
                try:
                    saved = save_judgment(record, decision, decision_reason)
                    histories.setdefault(application_number, []).append(saved)
                    st.success("\ud310\ub2e8 \uc774\ub825\uc744 data/judgments.json\uc5d0 \ucd94\uac00 \uc800\uc7a5\ud588\uc2b5\ub2c8\ub2e4.")
                except (OSError, RuntimeError) as exc:
                    st.error(f"\ud310\ub2e8 \uae30\ub85d\uc744 \uc800\uc7a5\ud558\uc9c0 \ubabb\ud588\uc2b5\ub2c8\ub2e4: {exc}")


def main() -> None:
    st.set_page_config(
        page_title="\uc0ac\ub78c \ud310\ub2e8 \uc911\uc2ec \ud2b9\ud5c8 \uac80\ud1a0",
        page_icon="\U0001f50e",
        layout="wide",
    )
    st.title("\uc0ac\ub78c \ud310\ub2e8 \uc911\uc2ec \ud2b9\ud5c8 \uac80\ud1a0 \uc5c5\ubb34 \uc790\ub3d9\ud654")
    st.write(
        "KIPRIS Plus\uc758 \uc2e4\uc81c \ud2b9\ud5c8 \ub370\uc774\ud130\ub97c \uae30\ubc18\uc73c\ub85c, "
        "\uac80\uc0c9\ub41c \ud2b9\ud5c8 \uc911 \uc0ac\uc6a9\uc790\uac00 \uba3c\uc800 \uac80\ud1a0\ud560 \ud6c4\ubcf4\uc758 \uc6b0\uc120\uc21c\uc704\ub97c \uc81c\uacf5\ud569\ub2c8\ub2e4."
    )
    st.info(
        "\ubcf8 \uad00\ub828\ub3c4 \uc810\uc218\ub294 \uc120\ud589\ud2b9\ud5c8 \uc5ec\ubd80, \ub4f1\ub85d \uac00\ub2a5\uc131, \uce68\ud574 \uc5ec\ubd80 \ub4f1\n"
        "\ubc95\uc801 \ud310\ub2e8\uc744 \uc758\ubbf8\ud558\uc9c0 \uc54a\uc2b5\ub2c8\ub2e4.\n"
        "\uc0ac\ub78c\uc774 \uc6b0\uc120 \uac80\ud1a0\ud560 \ud2b9\ud5c8\ub97c \uc815\ub82c\ud558\uae30 \uc704\ud55c \ubcf4\uc870 \uc9c0\ud45c\uc785\ub2c8\ub2e4."
    )
    st.caption(
        "\u2460 \ud2b9\ud5c8 \uac80\uc0c9 \ubc0f \ud6c4\ubcf4 \ud655\uc778  \u2192  "
        "\u2461 \uc0ac\ub78c \ud310\ub2e8\u00b7\uc774\uc720 \uae30\ub85d  \u2192  "
        "\u2462 \uc774\uc804 \ud310\ub2e8\u00b7\uc7ac\uac80\ud1a0 \ud655\uc778"
    )

    with st.form("patent_search_form"):
        search_col, technology_col = st.columns(2)
        search_query = search_col.text_input(
            "KIPRIS \uac80\uc0c9 \ubc94\uc704",
            value="\ubc30\ud130\ub9ac",
            help="KIPRIS Plus API\uc5d0 \uc804\ub2ec\ud560 \uac80\uc0c9\uc5b4\uc785\ub2c8\ub2e4.",
        )
        technology = technology_col.text_input(
            "\uac80\ud1a0\ud558\ub824\ub294 \uae30\uc220",
            value="\uc804\uae30\ucc28 \ubc30\ud130\ub9ac \ub0c9\uac01",
            help="\uc218\uc9d1\ud55c \uc2e4\uc81c \ud2b9\ud5c8\ub97c \uc774 \uae30\uc220 \uac1c\ub150\uc5d0 \ub530\ub77c \uc810\uc218\ud654\ud569\ub2c8\ub2e4.",
        )
        submitted = st.form_submit_button(
            "\ud2b9\ud5c8 \uac80\uc0c9 \ubc0f \ubd84\uc11d",
            type="primary",
            use_container_width=True,
        )

    if submitted:
        st.session_state.pop("ranked_patents", None)
        if not search_query.strip() or not technology.strip():
            st.error("KIPRIS \uac80\uc0c9 \ubc94\uc704\uc640 \uac80\ud1a0 \uae30\uc220\uc744 \ubaa8\ub450 \uc785\ub825\ud574\uc8fc\uc138\uc694.")
        else:
            api_key = os.getenv("KIPRIS_API_KEY")
            if not api_key:
                st.error("KIPRIS_API_KEY \ud658\uacbd\ubcc0\uc218\uac00 \uc5c6\uc2b5\ub2c8\ub2e4. PowerShell\uc5d0\uc11c API \ud0a4\ub97c \ud658\uacbd\ubcc0\uc218\ub85c \uc124\uc815\ud55c \ud6c4 \uc2e4\ud589\ud574\uc8fc\uc138\uc694.")
            else:
                try:
                    with st.spinner("KIPRIS Plus\uc5d0\uc11c \uc2e4\uc81c \ud2b9\ud5c8 \ub370\uc774\ud130\ub97c \uac00\uc838\uc624\uace0 \ubd84\uc11d\ud558\ub294 \uc911..."):
                        records = patent_mvp.collect_kipris_data(search_query.strip(), api_key, count=20)
                        if records:
                            ranked = patent_mvp.rank_records(technology.strip(), records)
                            st.session_state["ranked_patents"] = ranked
                            st.session_state["analysis_inputs"] = (search_query.strip(), technology.strip())
                        else:
                            st.warning("KIPRIS Plus \uc751\ub2f5\uc5d0\uc11c \ud2b9\ud5c8 \ub808\ucf54\ub4dc\ub97c \ucc3e\uc9c0 \ubabb\ud588\uc2b5\ub2c8\ub2e4. \uac80\uc0c9\uc5b4\ub97c \ud655\uc778\ud558\uac70\ub098 \ub2e4\uc2dc \uc2dc\ub3c4\ud574\uc8fc\uc138\uc694.")
                except Exception as exc:
                    message = str(exc).replace(api_key, "[\uac00\ub9bc]")
                    st.error(f"KIPRIS \uac80\uc0c9 \ub610\ub294 \ubd84\uc11d \uc911 \ubb38\uc81c\uac00 \ubc1c\uc0dd\ud588\uc2b5\ub2c8\ub2e4: {message}")

    ranked_patents = st.session_state.get("ranked_patents")
    if ranked_patents is None:
        return

    high_count = sum(row[patent_mvp.PRIORITY_FIELD] == patent_mvp.PRIORITY_HIGH for row in ranked_patents)
    medium_count = sum(row[patent_mvp.PRIORITY_FIELD] == patent_mvp.PRIORITY_MEDIUM for row in ranked_patents)
    low_count = sum(row[patent_mvp.PRIORITY_FIELD] == patent_mvp.PRIORITY_LOW for row in ranked_patents)
    st.subheader("\ubd84\uc11d \uacb0\uacfc")
    st.caption(
        f"KIPRIS \uac80\uc0c9: {st.session_state['analysis_inputs'][0]}  |  "
        f"\ud3c9\uac00 \uae30\uc220: {st.session_state['analysis_inputs'][1]}"
    )
    summary_cols = st.columns(4)
    summary_cols[0].metric("\uac80\uc0c9\ub41c \ud2b9\ud5c8", f"{len(ranked_patents)}\uac74")
    summary_cols[1].metric("\ub192\uc74c", f"{high_count}\uac74")
    summary_cols[2].metric("\ubcf4\ud1b5", f"{medium_count}\uac74")
    summary_cols[3].metric("\ub0ae\uc74c", f"{low_count}\uac74")
    if ranked_patents and ranked_patents[0].get(patent_mvp.ANALYSIS_MODE_FIELD) == "generic_keyword":
        st.info(patent_mvp.GENERIC_FALLBACK_MESSAGE)

    try:
        history_entries = load_judgments()
    except RuntimeError as exc:
        st.error(f"\uc774\uc804 \ud310\ub2e8 \uae30\ub85d\uc744 \ubd88\ub7ec\uc624\uc9c0 \ubabb\ud588\uc2b5\ub2c8\ub2e4: {exc}")
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

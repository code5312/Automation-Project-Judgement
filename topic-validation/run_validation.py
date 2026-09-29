"""Controlled B-3/D topic probes; labels are read only after predictions.

These fixtures demonstrate testability and workflow gaps, not field accuracy.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PATENT_ROOT = HERE.parent / "patent-evidence-poc"
sys.path.insert(0, str(PATENT_ROOT))

from src.patent_evidence.bm25 import BM25Index


def precision_recall(predicted: set[str], gold: set[str]) -> dict:
    true_positive = predicted & gold
    return {
        "predicted": len(predicted),
        "gold": len(gold),
        "matched": len(true_positive),
        "precision": len(true_positive) / len(predicted) if predicted else 0.0,
        "recall": len(true_positive) / len(gold) if gold else 0.0,
        "false_positive_ids": sorted(predicted - gold),
        "missed_ids": sorted(gold - predicted),
    }


def change_probe(case: dict) -> dict:
    artifacts = case["artifacts"]
    documents = [
        {"doc_id": item["id"], "title": item["id"], "abstract": item["before"]}
        for item in artifacts
    ]
    ranked = BM25Index(documents).search(case["change"], top_k=6)
    proposed = {item.doc_id for item in ranked}
    # This simulates a reviewer who knows the labelled affected set. It is an
    # upper-bound workflow check, never an observed human performance result.
    affected = set(case["gold"]["affected_ids"])
    must_change = set(case["gold"]["must_change_ids"])
    stale = set(case["gold"]["stale_after_ids"])
    completion = {}
    for item in artifacts:
        if item["id"] not in must_change:
            continue
        after = item["after"]
        # Only the literal policy value is checked. The old synonym "일주일"
        # and code-level semantics are outside this small deterministic rule.
        completion[item["id"]] = (
            "stale" if case["old_value"] in after
            else "updated" if case["new_value"] in after or
            re.search(r"(?:window_days:|days_since_purchase=)\s*14", after)
            else "uncertain"
        )
    detected_stale = {item for item, state in completion.items() if state == "stale"}
    return {
        "ranked_ids": [item.doc_id for item in ranked],
        "retrieval": precision_recall(proposed, affected),
        "simulated_reviewer_additions": sorted(affected - proposed),
        "simulated_reviewer_deletions": sorted(proposed - affected),
        "completion_states": completion,
        "stale_detection": precision_recall(detected_stale, stale),
        "workflow_closed_after_initial_changes": not any(
            state != "updated" for state in completion.values()
        ),
    }


def expanded_change_probe(case: dict) -> dict:
    """Retrospective keyword/identifier expansion after observing first failures."""
    base = change_probe(case)
    proposed = set(base["ranked_ids"])
    if "환불" in case["change"]:
        hints = ("refund", "환불", "취소", "반품")
    elif "배송" in case["change"]:
        hints = ("shipping", "delivery", "배송비", "무료배송")
    else:
        hints = ()
    for item in case["artifacts"]:
        text = item["id"] + " " + item["before"]
        if any(hint in text for hint in hints):
            proposed.add(item["id"])
    return {"retrieval": precision_recall(proposed, set(case["gold"]["affected_ids"])),
            "candidate_ids": sorted(proposed)}


def ip_probe(case: dict, expanded: bool = False) -> dict:
    technical = ("엔진", "모델", "알고리즘", "기술")
    new = ("새로운", "신규", "새 ")
    exposure = ("외부", "SDK", "오픈소스")
    if expanded:
        technical += ("방법",)
        exposure += ("단말", "라이브러리", "플러그인", "공개 API")
    decisions = []
    review_required = set()
    premise_alert = set()
    for event in case["events"]:
        text = event["text"]
        record = event["review_record"]
        new_technical = record == "none" and any(x in text for x in new) and any(
            x in text for x in technical
        )
        exposed_secret = record == "trade_secret" and any(x in text for x in exposure)
        if new_technical or exposed_secret:
            review_required.add(event["id"])
        if exposed_secret:
            premise_alert.add(event["id"])
        decisions.append({"id": event["id"], "review_candidate": new_technical or exposed_secret,
                          "premise_change_candidate": exposed_secret,
                          "evidence": event["text"], "prior_premise": event["prior_premise"]})
    return {
        "review_candidates": decisions,
        "review_detection": precision_recall(
            review_required, set(case["gold"]["review_required_ids"])
        ),
        "premise_detection": precision_recall(
            premise_alert, set(case["gold"]["premise_change_ids"])
        ),
    }


def main() -> None:
    fixtures = {name: json.loads((HERE / name).read_text(encoding="utf-8"))
                for name in ("fixtures.json", "fixtures_followup.json")}
    runs = {}
    for name, fixture in fixtures.items():
        runs[name] = {
            "provenance": fixture["provenance"],
            "change_completion": change_probe(fixture["change_completion"]),
            "change_expanded": expanded_change_probe(fixture["change_completion"]),
            "ip_review": ip_probe(fixture["ip_review"]),
            "ip_expanded": ip_probe(fixture["ip_review"], expanded=True),
        }
    report = {"runs": runs}
    output = HERE / "output"
    output.mkdir(exist_ok=True)
    (output / "results.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    lines = ["# 사람판단 주제 최소 검증 결과", "",
             "> 팀이 만든 통제 사례의 기준선 결과다. 현업 성능, 사람 검토 시간, 법적 판단 정확도가 아니다.", "",
             "두 번째 사례는 첫 기준선 실패를 본 뒤 만들었으므로 독립 보류셋이 아니다. 확장 규칙도 두 사례를 본 뒤 작성한 **회고적 확인**이다.", "",
             "| 사례 | B-3 단어 BM25 영향 후보 P/R | B-3 확장 후보 P/R | D 규칙 판단 요청 P/R | D 확장 규칙 P/R |",
             "| --- | ---: | ---: | ---: | ---: |"]
    for name, item in runs.items():
        a = item["change_completion"]["retrieval"]
        b = item["change_expanded"]["retrieval"]
        c = item["ip_review"]["review_detection"]
        d = item["ip_expanded"]["review_detection"]
        lines.append(f"| {name} | {a['precision']:.2f}/{a['recall']:.2f} | "
                     f"{b['precision']:.2f}/{b['recall']:.2f} | "
                     f"{c['precision']:.2f}/{c['recall']:.2f} | "
                     f"{d['precision']:.2f}/{d['recall']:.2f} |")
    first = runs["fixtures.json"]
    second = runs["fixtures_followup.json"]
    lines += ["", "## 관찰된 실패", "",
             f"- B-3 첫 사례 누락: {', '.join(first['change_completion']['retrieval']['missed_ids'])}. "
             "영문 설정·테스트 이름과 표현 차이가 주요 원인이다.",
             f"- B-3 둘째 사례 수정 누락 감지 실패: "
             f"{', '.join(second['change_completion']['stale_detection']['missed_ids'])}. "
             "`5만원`과 코드의 `50000`을 동일 값으로 보지 못한다.",
             f"- D 첫 사례 판단 요청 누락: {', '.join(first['ip_review']['review_detection']['missed_ids'])}; "
             f"둘째 사례 누락: {', '.join(second['ip_review']['review_detection']['missed_ids'])}. "
             "외부 공개와 기술의 표현을 한정해 놓은 규칙이 원인이다.",
             "- B-3 첫 사례에서는 CS 문구를 7일로 남겨 완료 불가를 확인했다. "
             "사람 보정은 실제 사람이 아니라 정답표를 대입한 상한 시뮬레이션이다.", "",
             "## 해석 경계", "",
             "- 정답표는 기준선 실행 전에 작성했지만 모두 팀 제작 예시다. 의미 기반 개선 효과와 실무 수요는 확인하지 못했다.",
             "- 사람 보정은 정답표를 대입한 상한 시뮬레이션이다. 실제 검토자가 얼마나 고칠지는 별도 관찰이 필요하다.",
             "- D의 판단 요청은 IP 검토 대상 후보일 뿐 발명·특허·영업비밀에 관한 결론이 아니다.",
             "- 확장 규칙 결과는 두 사례를 본 뒤 작성했으므로 개선 성능 근거가 아니다. 다음 비교는 새 사례를 고정한 뒤 진행해야 한다."]
    (output / "results.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({name: {
        "change": run["change_completion"]["retrieval"],
        "change_expanded": run["change_expanded"]["retrieval"],
        "stale": run["change_completion"]["stale_detection"],
        "ip_review": run["ip_review"]["review_detection"],
        "ip_expanded": run["ip_expanded"]["review_detection"],
        "ip_premise": run["ip_review"]["premise_detection"]}
        for name, run in runs.items()}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

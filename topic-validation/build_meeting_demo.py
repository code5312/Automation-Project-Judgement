"""Build the self-contained meeting MVP data without exposing gold labels or keys."""

from __future__ import annotations

import json
from pathlib import Path

from run_validation import HERE, change_probe, ip_probe


def main() -> None:
    cases = []
    for filename in ("fixtures.json", "fixtures_followup.json"):
        fixture = json.loads((HERE / filename).read_text(encoding="utf-8"))
        change, ip = fixture["change_completion"], fixture["ip_review"]
        change_suggestions = set(change_probe(change)["ranked_ids"])
        ip_suggestions = {
            row["id"]: row["review_candidate"]
            for row in ip_probe(ip)["review_candidates"]
        }
        cases.append({
            "name": "환불 기간 7일→14일" if filename == "fixtures.json"
                    else "무료배송 기준 5만→3만원",
            "change": change["change"],
            "artifacts": [{
                "id": row["id"], "kind": row["kind"], "before": row["before"],
                "after": row["after"], "suggested": row["id"] in change_suggestions,
            } for row in change["artifacts"]],
            "release": ip["release_event"],
            "events": [{
                "id": row["id"], "text": row["text"], "record": row["review_record"],
                "premise": row["prior_premise"], "suggested": ip_suggestions[row["id"]],
            } for row in ip["events"]],
        })

    # These two cases are already described in the committed personal worklog.
    # Only identifying query and rank data are included. The raw KIPRIS corpus,
    # citation labels, and the API key remain outside the deployed site.
    patent = [
        {"query": "자연어 단어를 데이터베이스의 컬럼 및 테이블과 연결하는 방법",
         "application": "1020190174967", "candidate_count": 468,
         "ranked": ["1020090060314", "1020150100531", "1020070043760",
                    "1020170182571", "1020070046711"],
         "note": "탐색 평가에서 인용 proxy 2건이 각각 2위·4위에 있었다. 정답 문헌이 후보집에 포함된 평가다."},
        {"query": "데이터 분석 장치 및 방법", "application": "1020130062415",
         "candidate_count": None, "ranked": ["1020007004339"],
         "note": "탐색 평가에서 연결된 인용 proxy 문헌이 단어 BM25 54위였다. 화면의 번호는 이 실패 사례의 문헌만 표시한다."},
    ]
    payload = {"cases": cases, "patent": patent}
    output = HERE / "meeting-demo" / "data.js"
    output.parent.mkdir(exist_ok=True)
    safe = json.dumps(payload, ensure_ascii=False).replace("<", "\\u003c")
    output.write_text("window.DEMO_DATA = " + safe + ";\n", encoding="utf-8")
    print(output)


if __name__ == "__main__":
    main()

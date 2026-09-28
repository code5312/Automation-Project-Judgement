"""Measure real candidate coverage and end-to-end ranking without gold injection.

Each query uses only its cached title-word KIPRIS searches. Missing cited
documents count as misses at every rank. E0802/E0805 remain citation proxies.
"""

from __future__ import annotations

import json
import statistics
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.evaluate_real_pilot import normalized_document
from src.patent_evidence.bm25 import BM25Index, tokenize, tokenize_korean_ngrams
from src.patent_evidence.metrics import evaluate_cases
from src.patent_evidence.xmlutil import parse_items


def main() -> int:
    raw_dir = ROOT / "data" / "raw"
    output_dir = ROOT / "output"
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest = json.loads((raw_dir / "query_candidate_manifest.json").read_text(encoding="utf-8"))
    policies = ("pilot", "holdout")
    gold_by_query = {}
    group_by_query = {}
    for split in policies:
        linkage = json.loads((raw_dir / f"{split}_document_linkage.json").read_text(encoding="utf-8"))
        sampling = json.loads((raw_dir / f"{split}_case_sampling.json").read_text(encoding="utf-8"))
        for group, details in sampling["groups"].items():
            for number in details["selected"]:
                group_by_query[number] = (split, group)
        for row in linkage["linkage"]:
            if row["match_count"] != 1 or not row["published_before_query_filing"]:
                raise ValueError(f"Invalid gold link: {row['query_application_number']}")
            gold_by_query.setdefault(row["query_application_number"], set()).add(
                row["matched_application_number"]
            )
    if set(manifest["cases"]) != set(gold_by_query):
        raise ValueError("Manifest and evaluated query sets differ")

    raw_cases = []
    ranking_inputs = {"word": [], "korean_ngram": []}
    for number, query_manifest in manifest["cases"].items():
        query_rows = parse_items((raw_dir / f"{number}.publication.xml").read_text(encoding="utf-8"))
        if len(query_rows) != 1:
            raise ValueError(f"Query lookup failed: {number}")
        query = query_rows[0]
        filing_date = query.get("ApplicationDate", "")
        if not filing_date:
            raise ValueError(f"Missing query filing date: {number}")
        documents = {}
        raw_rows = 0
        for search in query_manifest["searches"]:
            rows = parse_items((raw_dir / search["cache"]).read_text(encoding="utf-8"))
            if len(rows) != search["rows"]:
                raise ValueError(f"Search cache changed: {search['cache']}")
            raw_rows += len(rows)
            for row in rows:
                doc = normalized_document(row)
                if doc["doc_id"] and doc["doc_id"] != number:
                    documents[doc["doc_id"]] = doc
        eligible = [doc for doc in documents.values()
                    if doc["first_public_date"] and doc["first_public_date"] <= filing_date]
        rankable = [doc for doc in eligible if doc["title"] and doc["abstract"]]
        gold = gold_by_query[number]
        covered = gold & {doc["doc_id"] for doc in eligible}
        rankable_gold = gold & {doc["doc_id"] for doc in rankable}
        split, group = group_by_query[number]
        case = {"case_id": number, "split": split, "ipc_group": group,
                "query_application_date": filing_date,
                "search_terms": [item["word"] for item in query_manifest["searches"]],
                "search_rows": raw_rows, "unique_search_applications": len(documents),
                "time_eligible_candidates": len(eligible), "rankable_candidates": len(rankable),
                "gold_doc_ids": sorted(gold), "covered_gold_doc_ids": sorted(covered),
                "rankable_gold_doc_ids": sorted(rankable_gold),
                "candidate_coverage": len(covered) / len(gold)}
        raw_cases.append(case)
        query_text = query["InventionName"] + " " + query.get("Abstract", "")
        for name, tokenizer in (("word", tokenize), ("korean_ngram", tokenize_korean_ngrams)):
            ranked_ids = ([item.doc_id for item in BM25Index(rankable, tokenizer=tokenizer).search(query_text)]
                          if rankable else [])
            ranking_inputs[name].append({"case_id": number, "query": query["InventionName"],
                                         "gold_doc_ids": sorted(gold), "ranked_ids": ranked_ids})

    evaluations = {name: evaluate_cases(rows, ks=(10, 20, 50))
                   for name, rows in ranking_inputs.items()}
    for name, evaluation in evaluations.items():
        for result in evaluation["cases"]:
            result.pop("query", None)
            result.pop("gold_doc_ids", None)
            result.pop("top_ids", None)
    for case in raw_cases:
        idx = list(manifest["cases"]).index(case["case_id"])
        case["ranking"] = {name: evaluations[name]["cases"][idx]["metrics"]
                           for name in evaluations}

    summary = {}
    for split in ("pilot", "holdout", "all"):
        cases = [case for case in raw_cases if split == "all" or case["split"] == split]
        gold_pairs = sum(len(case["gold_doc_ids"]) for case in cases)
        covered_pairs = sum(len(case["covered_gold_doc_ids"]) for case in cases)
        summary[split] = {
            "queries": len(cases),
            "gold_pairs": gold_pairs,
            "covered_gold_pairs": covered_pairs,
            "pair_coverage": covered_pairs / gold_pairs,
            "queries_with_any_covered_gold": sum(bool(case["covered_gold_doc_ids"]) for case in cases),
            "time_eligible_candidates_median": statistics.median(
                case["time_eligible_candidates"] for case in cases
            ),
            "mean_case_coverage": statistics.mean(case["candidate_coverage"] for case in cases),
            "ranking": {name: {metric: statistics.mean(case["ranking"][name][metric] for case in cases)
                               for metric in ("recall@10", "recall@20", "recall@50", "rr")}
                        for name in evaluations},
        }
    report = {"protocol": {"candidate_source": manifest["policy"],
                           "max_results_per_term": manifest["docs_count"],
                           "positive_injection": False,
                           "time_filter": "first public date <= query filing date",
                           "label": "domestic E0802/E0805 citation proxy"},
              "summary": summary, "cases": raw_cases}
    (output_dir / "candidate_generation.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    lines = ["# 정답 주입 없는 질의별 후보 검색 점검", "",
             "질의 제목에서 최대 두 검색어를 정해 KIPRIS 검색 결과를 각 500행까지 수집했다. "
             "인용 문헌은 후보에 추가하지 않았다. 출원일 이후 공개 문헌과 자기 문헌은 제외했다.", "",
             "| 구간 | 질의 | 정답 쌍 중 후보 포함 | 후보 포함 질의 | 후보 중앙값 | 단어 R@10 | n-gram R@10 |",
             "| --- | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for split, label in (("pilot", "탐색"), ("holdout", "별도 9건"), ("all", "전체")):
        item = summary[split]
        lines.append(f"| {label} | {item['queries']} | {item['covered_gold_pairs']}/{item['gold_pairs']} "
                     f"({item['pair_coverage']:.1%}) | {item['queries_with_any_covered_gold']}/{item['queries']} "
                     f"| {item['time_eligible_candidates_median']:g} | "
                     f"{item['ranking']['word']['recall@10']:.3f} | "
                     f"{item['ranking']['korean_ngram']['recall@10']:.3f} |")
    lines += ["", "R@10은 질의별 인용 문헌 회수율의 평균이다. 후보에 없는 인용 문헌은 0으로 계산한다. "
              "인용 양성 질의 선택과 단순한 제목 검색어 규칙 때문에 제품 성능 추정치가 아니다.", "",
              "| 질의 출원번호 | 구간 | 검색어 | 시점 적격 후보 | 인용 포함/전체 | 단어 R@10 | n-gram R@10 |",
              "| --- | --- | --- | ---: | ---: | ---: | ---: |"]
    for case in raw_cases:
        lines.append(f"| {case['case_id']} | {case['split']} | {', '.join(case['search_terms'])} | "
                     f"{case['time_eligible_candidates']} | "
                     f"{len(case['covered_gold_doc_ids'])}/{len(case['gold_doc_ids'])} | "
                     f"{case['ranking']['word']['recall@10']:.3f} | "
                     f"{case['ranking']['korean_ngram']['recall@10']:.3f} |")
    (output_dir / "candidate_generation.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

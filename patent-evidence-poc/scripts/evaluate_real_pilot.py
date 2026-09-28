"""Evaluate title/abstract BM25 on the cached 21-case exploratory pilot.

The 3 keyword searches and all known positives form a deliberately biased
candidate pool. E0802/E0805 are search-report citation proxies, not final
examiner relevance labels. Output stays under gitignored output/.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.patent_evidence.bm25 import BM25Index, tokenize, tokenize_korean_ngrams
from src.patent_evidence.metrics import evaluate_cases
from src.patent_evidence.xmlutil import parse_items


def first_public_date(row: dict) -> str:
    dates = [row.get(key, "") for key in ("OpeningDate", "PublicDate")]
    return min(date for date in dates if date) if any(dates) else ""


def normalized_document(row: dict) -> dict:
    return {
        "doc_id": row.get("ApplicationNumber", ""),
        "title": row.get("InventionName", ""),
        "abstract": row.get("Abstract", ""),
        "first_public_date": first_public_date(row),
    }


def load_corpus(raw_dir: Path, linkage: list[dict]) -> tuple[dict[str, dict], dict]:
    documents: dict[str, dict] = {}
    search_rows = 0
    for label in ("data", "semiconductor", "measurement"):
        for start in (1, 101, 201):
            cache = raw_dir / f"candidate_search_{label}_100_start{start}.xml"
            rows = parse_items(cache.read_text(encoding="utf-8"))
            search_rows += len(rows)
            for row in rows:
                doc = normalized_document(row)
                if doc["doc_id"]:
                    documents[doc["doc_id"]] = doc
    search_unique = len(documents)
    for citation in linkage:
        kind, value = citation["lookup_kind"], citation["lookup_value"]
        cache = raw_dir / f"cited_{kind}_{value}.xml"
        rows = parse_items(cache.read_text(encoding="utf-8"))
        if len(rows) != 1:
            raise ValueError(f"Cited document did not resolve uniquely: {kind}/{value}")
        doc = normalized_document(rows[0])
        if not doc["doc_id"] or not doc["title"] or not doc["abstract"]:
            raise ValueError(f"Cited document lacks text or ID: {kind}/{value}")
        documents[doc["doc_id"]] = doc
    return documents, {"search_rows": search_rows, "search_unique_applications": search_unique,
                       "combined_unique_applications": len(documents)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tokenizer", choices=("word", "korean-ngram", "hybrid"), default="word")
    args = parser.parse_args()
    tokenizers = {"word": tokenize, "korean-ngram": tokenize_korean_ngrams}
    tokenizer = tokenizers.get(args.tokenizer)
    raw_dir = ROOT / "data" / "raw"
    output_dir = ROOT / "output"
    output_dir.mkdir(parents=True, exist_ok=True)
    source = json.loads((raw_dir / "pilot_document_linkage.json").read_text(encoding="utf-8"))
    sampling = json.loads((raw_dir / "pilot_case_sampling.json").read_text(encoding="utf-8"))
    group_by_number = {
        number: group for group, details in sampling["groups"].items()
        for number in details["selected"]
    }
    if source["citation_type_codes"] != ["E0802", "E0805"]:
        raise ValueError("This evaluation requires the E0802/E0805 proxy policy")
    linkage = source["linkage"]
    corpus, corpus_stats = load_corpus(raw_dir, linkage)
    gold_by_query: dict[str, set[str]] = defaultdict(set)
    for row in linkage:
        if row["match_count"] != 1 or not row["published_before_query_filing"]:
            raise ValueError(f"Invalid citation link for {row['query_application_number']}")
        gold_by_query[row["query_application_number"]].add(row["matched_application_number"])

    results = []
    candidate_counts = []
    gold_counts = []
    for number in source["query_application_numbers"]:
        rows = parse_items((raw_dir / f"{number}.publication.xml").read_text(encoding="utf-8"))
        if len(rows) != 1:
            raise ValueError(f"Query publication did not resolve uniquely: {number}")
        query_doc = normalized_document(rows[0])
        query_date = rows[0].get("ApplicationDate", "")
        if not query_date or not query_doc["title"] or not query_doc["abstract"]:
            raise ValueError(f"Query lacks filing date or text: {number}")
        candidates = [doc for doc in corpus.values()
                      if doc["doc_id"] != number
                      and doc["first_public_date"]
                      and doc["first_public_date"] <= query_date
                      and doc["title"] and doc["abstract"]]
        candidate_ids = {doc["doc_id"] for doc in candidates}
        gold = gold_by_query[number]
        if not gold or not gold <= candidate_ids:
            raise ValueError(f"Missing time-eligible gold for {number}: {sorted(gold - candidate_ids)}")
        query_text = query_doc["title"] + " " + query_doc["abstract"]
        if args.tokenizer == "hybrid":
            word_ranked = BM25Index(candidates, tokenizer=tokenize).search(query_text)
            char_ranked = BM25Index(candidates, tokenizer=tokenize_korean_ngrams).search(query_text)
            fusion = defaultdict(float)
            for ranking in (word_ranked, char_ranked):
                for position, item in enumerate(ranking, 1):
                    fusion[item.doc_id] += 1 / (60 + position)
            ranked_ids = sorted(fusion, key=lambda doc_id: (-fusion[doc_id], doc_id))
        else:
            ranked = BM25Index(candidates, tokenizer=tokenizer).search(query_text)
            ranked_ids = [item.doc_id for item in ranked]
        results.append({"case_id": number, "query": query_doc["title"],
                        "gold_doc_ids": sorted(gold),
                        "ranked_ids": ranked_ids,
                        "candidate_count": len(candidates), "query_application_date": query_date})
        candidate_counts.append(len(candidates))
        gold_counts.append(len(gold))

    evaluation = evaluate_cases(results, ks=(10, 20, 50))
    evaluation["protocol"] = {
        "candidate_source": "first 300 results each for 데이터, 반도체, 측정 + known positive documents",
        "selection": "7 citation-positive cases in each of G06, H01/H10, G01; fixed seed 20260928",
        "label": "domestic E0802/E0805 search-report citation proxy; final examiner relevance unverified",
        "retrieval": f"B0 title+abstract {args.tokenizer} BM25"
                     + (" with equal-weight RRF(k=60)" if args.tokenizer == "hybrid" else ""),
        "time_filter": "earliest of OpeningDate and PublicDate <= query ApplicationDate",
        "limitations": ["positive injection", "keyword-seeded corpus", "citation-positive case selection",
                        "not a representative performance estimate"],
    }
    evaluation["corpus"] = corpus_stats
    evaluation["summary"] = {
        "cases": len(results), "citation_rows": len(linkage),
        "unique_case_gold_pairs": sum(gold_counts),
        "candidate_count_min": min(candidate_counts),
        "candidate_count_median": statistics.median(candidate_counts),
        "candidate_count_max": max(candidate_counts),
        "gold_count_min": min(gold_counts), "gold_count_median": statistics.median(gold_counts),
        "gold_count_max": max(gold_counts),
    }
    for case, raw in zip(evaluation["cases"], results):
        case["candidate_count"] = raw["candidate_count"]
        case["query_application_date"] = raw["query_application_date"]
        case["ipc_group"] = group_by_number[case["case_id"]]
        case["first_gold_rank"] = next(
            idx for idx, doc_id in enumerate(raw["ranked_ids"], 1)
            if doc_id in raw["gold_doc_ids"]
        )
    suffix = {"word": "", "korean-ngram": "_korean_ngram", "hybrid": "_hybrid"}[args.tokenizer]
    path = output_dir / f"real_pilot_b0{suffix}.json"
    path.write_text(json.dumps(evaluation, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = [
        f"# KIPRIS 21건 탐색 파일럿 · B0 {args.tokenizer} 결과",
        "",
        "- 질의: G06·H01/H10·G01 각 7건, 총 21건. 인용이 있는 사례만 선택.",
        "- 후보: `데이터`·`반도체`·`측정` 검색 각 300행, 중복 제거 후 인용 정답 문헌 주입.",
        "- 정답 대용: 국내 E0802·E0805 인용, 출원일 이전 공개 확인. 심사관 최종 판단과 무관성 정답은 미확인.",
        f"- 검색: 제목+초록 {args.tokenizer} BM25. 질의 출원일 이후 공개 문헌과 자기 문헌 제외.",
        "- 제한: 검색어 중심 후보군·정답 주입·인용 양성 사례 선택. 아래 수치는 대표 성능이 아닌 파이프라인 탐색 결과.",
        "",
        "| 항목 | 값 |", "| --- | ---: |",
        f"| 검색 결과 원행 | {corpus_stats['search_rows']} |",
        f"| 검색 결과 고유 출원번호 | {corpus_stats['search_unique_applications']} |",
        f"| 인용 문헌 추가 후 고유 출원번호 | {corpus_stats['combined_unique_applications']} |",
        f"| 질의별 시간 적격 후보 수 (최소/중앙/최대) | {min(candidate_counts)} / {statistics.median(candidate_counts):g} / {max(candidate_counts)} |",
        f"| 인용행 / 질의·문헌 고유 쌍 | {len(linkage)} / {sum(gold_counts)} |",
    ]
    for metric, value in evaluation["aggregate"].items():
        lines.append(f"| {metric.upper()} | {value:.3f} |")
    lines.extend(["", "## 사례별 결과", "", "| IPC군 | 출원번호 | 후보 수 | 정답 수 | 첫 정답 순위 | R@10 | R@20 | R@50 |",
                  "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |"])
    for case in evaluation["cases"]:
        metrics = case["metrics"]
        lines.append(
            f"| {case['ipc_group']} | {case['case_id']} | {case['candidate_count']} | "
            f"{len(case['gold_doc_ids'])} | {case['first_gold_rank']} | "
            f"{metrics['recall@10']:.2f} | {metrics['recall@20']:.2f} | {metrics['recall@50']:.2f} |"
        )
    (output_dir / f"real_pilot_b0{suffix}.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"corpus": corpus_stats, "summary": evaluation["summary"],
                      "aggregate": evaluation["aggregate"], "report": str(path)},
                     ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

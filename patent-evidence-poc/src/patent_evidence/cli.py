from __future__ import annotations

import argparse
import json
from pathlib import Path

from .bm25 import BM25Index
from .metrics import evaluate_cases


def load_jsonl(path: Path) -> list[dict]:
    rows = []
    with path.open("r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            if not line.strip():
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{line_no}: invalid JSON") from exc
    return rows


def validate_corpus(rows: list[dict]) -> None:
    seen = set()
    for row in rows:
        doc_id = row.get("doc_id")
        if not doc_id:
            raise ValueError("every corpus row needs doc_id")
        if doc_id in seen:
            raise ValueError(f"duplicate doc_id: {doc_id}")
        seen.add(doc_id)


def validate_eval(rows: list[dict], corpus_ids: set[str]) -> None:
    for row in rows:
        if not row.get("case_id") or not row.get("query"):
            raise ValueError("every eval row needs case_id and query")
        gold = row.get("gold_doc_ids", [])
        if not gold:
            raise ValueError(f"{row['case_id']}: gold_doc_ids must not be empty")
        missing = sorted(set(gold) - corpus_ids)
        if missing:
            raise ValueError(f"{row['case_id']}: gold ids missing from corpus: {missing}")


def render_markdown(result: dict) -> str:
    agg = result["aggregate"]
    lines = [
        "# BM25 baseline report",
        "",
        "> Fixture 결과는 파이프라인 동작 검증용이며 실제 특허 검색 성능이 아닙니다.",
        "",
        "## Aggregate",
        "",
        "| metric | value |",
        "| --- | ---: |",
    ]
    for key, value in agg.items():
        lines.append(f"| {key} | {value:.4f} |")

    lines.extend(["", "## Cases", ""])
    for case in result["cases"]:
        lines.extend([
            f"### {case['case_id']}",
            f"- query: {case['query']}",
            f"- gold: {', '.join(case['gold_doc_ids'])}",
            f"- top5: {', '.join(case['top_ids'][:5])}",
            f"- RR: {case['metrics']['rr']:.4f}",
            "",
        ])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run deterministic BM25 prior-art baseline")
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--eval", dest="eval_path", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    corpus = load_jsonl(args.corpus)
    eval_rows = load_jsonl(args.eval_path)
    validate_corpus(corpus)
    validate_eval(eval_rows, {row["doc_id"] for row in corpus})

    index = BM25Index(corpus)
    raw_results = []
    for case in eval_rows:
        ranked = index.search(case["query"])
        raw_results.append({
            "case_id": case["case_id"],
            "query": case["query"],
            "gold_doc_ids": case["gold_doc_ids"],
            "ranked_ids": [item.doc_id for item in ranked],
        })

    result = evaluate_cases(raw_results)
    result["metadata"] = {
        "corpus_size": len(corpus),
        "case_count": len(eval_rows),
        "baseline": "bm25",
        "fixture": all(row.get("is_fixture", False) for row in corpus),
    }

    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "baseline_results.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (args.out / "baseline_report.md").write_text(render_markdown(result), encoding="utf-8")

    print(json.dumps(result["aggregate"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Evaluate the frozen BM25 retrieval baseline on public LibEST trace links.

Download source separately; the third-party corpus is never committed here.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from run_validation import HERE, PATENT_ROOT

sys.path.insert(0, str(PATENT_ROOT))
from src.patent_evidence.bm25 import BM25Index


DEFAULT_ROOT = HERE / "output/external/finegrained-traceability/datasets/LibEST"


def evaluate(root: Path) -> dict:
    code_dir, req_dir = root / "code", root / "req"
    links = {}
    for line in (root / "req_to_code_ground.txt").read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        requirement, filenames = line.split(":", 1)
        links[requirement.strip()] = set(filenames.split())
    documents = [
        {"doc_id": path.name, "title": path.name,
         "abstract": path.read_text(encoding="utf-8", errors="replace")}
        for path in sorted(code_dir.iterdir()) if path.is_file()
    ]
    index = BM25Index(documents)
    rows = []
    for requirement in sorted(links):
        gold = links[requirement]
        if not gold:
            continue
        unknown = gold - {doc["doc_id"] for doc in documents}
        if unknown:
            raise ValueError(f"Missing code files for {requirement}: {sorted(unknown)}")
        query = (req_dir / requirement).read_text(encoding="utf-8", errors="replace")
        ranking = [hit.doc_id for hit in index.search(query)]
        rows.append({
            "requirement": requirement,
            "gold_count": len(gold),
            "recall_at_3": len(gold.intersection(ranking[:3])) / len(gold),
            "recall_at_6": len(gold.intersection(ranking[:6])) / len(gold),
            "precision_at_6": len(gold.intersection(ranking[:6])) / 6,
            "first_relevant_rank": next(i for i, doc in enumerate(ranking, 1) if doc in gold),
            "missed_at_6": sorted(gold - set(ranking[:6])),
        })
    return {
        "source": "https://github.com/tobhey/finegrained-traceability/tree/197cf2f395e9e90636436f30d6383465cb9e9f63/datasets/LibEST",
        "scope": "requirement-to-code retrieval proxy; not change completion or IP review",
        "requirements_with_gold": len(rows),
        "code_files": len(documents),
        "gold_links": sum(row["gold_count"] for row in rows),
        "mean_recall_at_3": sum(row["recall_at_3"] for row in rows) / len(rows),
        "mean_recall_at_6": sum(row["recall_at_6"] for row in rows) / len(rows),
        "mean_precision_at_6": sum(row["precision_at_6"] for row in rows) / len(rows),
        "mrr": sum(1 / row["first_relevant_rank"] for row in rows) / len(rows),
        "requirements_with_missed_links_at_6": sum(bool(row["missed_at_6"]) for row in rows),
        "rows": rows,
    }


def main() -> None:
    root = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_ROOT
    result = evaluate(root)
    output = HERE / "output/external-trace-results.json"
    output.parent.mkdir(exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({key: value for key, value in result.items() if key != "rows"}, indent=2))


if __name__ == "__main__":
    main()

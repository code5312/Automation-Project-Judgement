"""Fetch query-specific KIPRIS candidates without consulting citation labels.

For each cached query title, select up to two least common non-generic words
among the 30 query titles. Fetch up to 500 results per word. Search results
and the term-selection audit stay under gitignored data/raw/.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.patent_evidence.bm25 import tokenize
from src.patent_evidence.kipris import KiprisClient
from src.patent_evidence.xmlutil import parse_items


GENERIC = {"장치", "방법", "시스템", "및", "이를", "제어", "데이터", "기반", "제조",
           "제조방법", "포함", "이용", "생성", "제공", "관리", "사용", "위한", "통한",
           "대한", "가능", "저장", "입력", "처리", "향상", "갖는", "안정적인",
           "대해", "저장할", "설치", "지원", "서비스"}
SUFFIXES = ("으로부터", "시키기", "시키는", "시키다", "들에게", "들을", "에서", "으로",
            "하는", "하여", "하기", "되는", "되어", "에게", "까지", "처럼",
            "를", "을", "의", "이", "가", "은", "는", "와", "과", "에", "로", "도")
SAMPLINGS = ("pilot_case_sampling.json", "holdout_case_sampling.json")


def selected_queries(raw_dir: Path) -> list[str]:
    numbers = []
    for filename in SAMPLINGS:
        audit = json.loads((raw_dir / filename).read_text(encoding="utf-8"))
        numbers.extend(number for group in audit["groups"].values() for number in group["selected"])
    if len(numbers) != len(set(numbers)):
        raise ValueError("Development and holdout cases overlap")
    return numbers


def normalize_term(term: str) -> str:
    for suffix in SUFFIXES:
        if term.endswith(suffix) and len(term) - len(suffix) >= 2:
            return term[:-len(suffix)]
    return term


def title_terms(titles: dict[str, str]) -> dict[str, list[str]]:
    words = {number: [term for term in {normalize_term(word) for word in tokenize(title)}
                      if len(term) >= 2 and term not in GENERIC and not term.isdigit()]
             for number, title in titles.items()}
    frequency = Counter(term for terms in words.values() for term in terms)
    return {number: sorted(terms, key=lambda term: (frequency[term], -len(term), term))[:2]
            for number, terms in words.items()}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--max-queries", type=int, help="Optional smoke-test cap")
    args = parser.parse_args()
    raw_dir = ROOT / "data" / "raw"
    numbers = selected_queries(raw_dir)
    titles = {}
    for number in numbers:
        rows = parse_items((raw_dir / f"{number}.publication.xml").read_text(encoding="utf-8"))
        if len(rows) != 1:
            raise ValueError(f"Expected one query publication: {number}")
        titles[number] = rows[0]["InventionName"]
    terms = title_terms(titles)
    if any(not values for values in terms.values()):
        raise ValueError("Each query must provide a non-generic title word")
    client = KiprisClient.from_env()
    audit = {"policy": "up to two rare non-generic title words; no citation labels",
             "docs_start": 1, "docs_count": 500, "cases": {}}
    called = 0
    for number in numbers[:args.max_queries] if args.max_queries else numbers:
        searches = []
        for idx, word in enumerate(terms[number], 1):
            digest = hashlib.sha256(word.encode("utf-8")).hexdigest()[:10]
            cache = raw_dir / f"query_candidate_{number}_{idx}_{digest}.xml"
            if cache.exists():
                xml = cache.read_text(encoding="utf-8")
            else:
                xml = client._publication_call(
                    "freeSearchInfo", word=word, patent="true", utility="true",
                    docsStart="1", docsCount="500",
                )
                cache.write_text(xml, encoding="utf-8")
                called += 1
                time.sleep(0.1)
            rows = parse_items(xml)
            searches.append({"word": word, "cache": cache.name, "rows": len(rows)})
        audit["cases"][number] = {"title": titles[number], "searches": searches}
        print(number, [f"{item['word']}:{item['rows']}" for item in searches])
    audit["new_api_calls"] = called
    output = raw_dir / "query_candidate_manifest.json"
    output.write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")
    print("queries", len(audit["cases"]), "new_api_calls", called, "manifest", output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

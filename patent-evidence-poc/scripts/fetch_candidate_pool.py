"""Cache three KIPRIS free-search result pages per exploratory search term.

KIPRIS docsStart is a one-based result offset, not a page number. Raw XML stays
under gitignored data/raw/. Repeating this script reuses existing cache files.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.patent_evidence.kipris import KiprisClient
from src.patent_evidence.xmlutil import parse_items


SEARCHES = {"data": "데이터", "semiconductor": "반도체", "measurement": "측정"}
STARTS = (1, 101, 201)


def main() -> int:
    raw_dir = ROOT / "data" / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    client = KiprisClient.from_env()
    audit = {"docs_count": 100, "docs_start": list(STARTS), "terms": {}}
    for label, word in SEARCHES.items():
        pages = []
        for start in STARTS:
            cache = raw_dir / f"candidate_search_{label}_100_start{start}.xml"
            if cache.exists():
                xml = cache.read_text(encoding="utf-8")
            else:
                xml = client._publication_call(
                    "freeSearchInfo", word=word, patent="true", utility="false",
                    docsStart=str(start), docsCount="100",
                )
                cache.write_text(xml, encoding="utf-8")
            rows = parse_items(xml)
            if len(rows) != 100:
                raise ValueError(f"Expected 100 results in {cache.name}; got {len(rows)}")
            pages.append({row["ApplicationNumber"] for row in rows})
        audit["terms"][label] = {
            "page_sizes": [len(page) for page in pages],
            "unique_applications": len(set.union(*pages)),
            "overlap_1_2": len(pages[0] & pages[1]),
            "overlap_1_3": len(pages[0] & pages[2]),
            "overlap_2_3": len(pages[1] & pages[2]),
        }
    print(json.dumps(audit, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

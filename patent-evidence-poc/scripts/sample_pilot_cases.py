"""Select a reproducible, stratified exploratory set from cached KIPRIS searches.

Search terms and IPC groups are intentionally narrow; this is not a random
sample of Korean patents. All API XML is cached under gitignored data/raw/.
"""

from __future__ import annotations

import argparse
import json
import random
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.patent_evidence.dataset import parse_domestic_citation_lookups
from src.patent_evidence.kipris import KiprisClient
from src.patent_evidence.xmlutil import parse_items


GROUPS = {
    "G06_data": ("data", ("G06",)),
    "H01_H10_semiconductor": ("semiconductor", ("H01", "H10")),
    "G01_measurement": ("measurement", ("G01",)),
}
PROXY_TYPES = {"E0802", "E0805"}


def candidates(raw_dir: Path, label: str, prefixes: tuple[str, ...], seed: int) -> list[dict]:
    rows = parse_items((raw_dir / f"candidate_search_{label}_100_start1.xml").read_text(encoding="utf-8"))
    eligible = [
        row for row in rows
        if row.get("InternationalpatentclassificationNumber", "").startswith(prefixes)
        and row.get("ApplicationDate", "")[:4].isdigit()
        and 2010 <= int(row["ApplicationDate"][:4]) <= 2021
        and row.get("ApplicationNumber")
        and row.get("InventionName", "").strip()
        and row.get("Abstract", "").strip()
    ]
    unique = {row["ApplicationNumber"]: row for row in eligible}
    result = list(unique.values())
    random.Random(seed).shuffle(result)
    return result


def cached_citation(client: KiprisClient, raw_dir: Path, number: str) -> tuple[str, bool]:
    cache = raw_dir / f"{number}.citation.xml"
    if cache.exists():
        return cache.read_text(encoding="utf-8"), False
    xml = client.citation_xml(number)
    cache.write_text(xml, encoding="utf-8")
    time.sleep(0.1)
    return xml, True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target-per-group", type=int, default=7)
    parser.add_argument("--max-inspect-per-group", type=int, default=25)
    parser.add_argument("--seed", type=int, default=20260928)
    parser.add_argument("--raw-dir", type=Path, default=ROOT / "data" / "raw")
    args = parser.parse_args()
    if args.target_per_group < 1 or args.max_inspect_per_group < 1:
        parser.error("Targets and inspection caps must be positive")

    client = KiprisClient.from_env()
    audit = {"seed": args.seed, "groups": {}}
    new_calls = 0
    for group, (label, prefixes) in GROUPS.items():
        selected = []
        inspected = []
        pool = candidates(args.raw_dir, label, prefixes, args.seed)
        for row in pool[:args.max_inspect_per_group]:
            if len(selected) >= args.target_per_group:
                break
            number = row["ApplicationNumber"]
            try:
                xml, called = cached_citation(client, args.raw_dir, number)
                new_calls += int(called)
                citations = parse_domestic_citation_lookups(xml)
                proxy = sorted({
                    (item["lookup_kind"], item["lookup_value"])
                    for item in citations if item["citation_division_code"] in PROXY_TYPES
                })
                status = "selected" if proxy else "no_domestic_proxy"
                if proxy:
                    pub_cache = args.raw_dir / f"{number}.publication.xml"
                    if not pub_cache.exists():
                        pub_cache.write_text(client.search_application_xml(number), encoding="utf-8")
                        new_calls += 1
                        time.sleep(0.1)
                    if len(parse_items(pub_cache.read_text(encoding="utf-8"))) != 1:
                        status = "publication_lookup_failed"
                    else:
                        selected.append(number)
                inspected.append({"application_number": number, "status": status, "proxy_documents": len(proxy)})
            except Exception as exc:
                inspected.append({"application_number": number, "status": f"error:{type(exc).__name__}"})
        audit["groups"][group] = {
            "search_pool": len(pool),
            "inspected": inspected,
            "selected": selected,
        }
        print(group, "pool", len(pool), "inspected", len(inspected), "selected", len(selected))

    audit["new_api_calls"] = new_calls
    output = args.raw_dir / "pilot_case_sampling.json"
    output.write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")
    print("new_api_calls", new_calls, "report", output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

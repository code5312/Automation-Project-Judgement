"""Fetch and inspect cited KR publications for a small feasibility pilot.

The selected citation types are a research proxy, not examiner-final gold labels.
Raw XML and the linkage report stay under gitignored data/raw/.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.patent_evidence.dataset import parse_domestic_citation_lookups
from src.patent_evidence.kipris import KiprisClient
from src.patent_evidence.xmlutil import parse_items


def source_rows(raw_dir: Path, application_numbers: list[str], codes: set[str]) -> list[dict]:
    rows = []
    for application_number in application_numbers:
        publication = parse_items(
            (raw_dir / f"{application_number}.publication.xml").read_text(encoding="utf-8")
        )
        if len(publication) != 1:
            raise ValueError(f"Expected one query publication for {application_number}")
        citations = parse_domestic_citation_lookups(
            (raw_dir / f"{application_number}.citation.xml").read_text(encoding="utf-8")
        )
        for citation in citations:
            if citation["citation_division_code"] in codes:
                rows.append({
                    "query_application_number": application_number,
                    "query_application_date": publication[0].get("ApplicationDate", ""),
                    **citation,
                })
    return rows


def build_linkage(rows: list[dict], documents: dict[tuple[str, str], list[dict]]) -> list[dict]:
    linked = []
    for row in rows:
        matches = documents[(row["lookup_kind"], row["lookup_value"])]
        document = matches[0] if len(matches) == 1 else {}
        opening_date = document.get("OpeningDate", "")
        registration_publication_date = document.get("PublicDate", "")
        public_dates = [date for date in (opening_date, registration_publication_date) if date]
        first_public_date = min(public_dates) if public_dates else ""
        query_date = row["query_application_date"]
        linked.append({
            **row,
            "match_count": len(matches),
            "matched_application_number": document.get("ApplicationNumber", ""),
            "matched_opening_number": document.get("OpeningNumber", ""),
            "matched_opening_date": opening_date,
            "matched_registration_publication_date": registration_publication_date,
            "matched_first_public_date": first_public_date,
            "title_characters": len(document.get("InventionName", "")),
            "abstract_characters": len(document.get("Abstract", "")),
            "published_before_query_filing": bool(first_public_date and query_date and first_public_date <= query_date),
        })
    return linked


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("application_numbers", nargs="*", help="Already cached query cases")
    parser.add_argument("--from-sampling", action="store_true", help="Use cases in pilot_case_sampling.json")
    parser.add_argument("--raw-dir", type=Path, default=ROOT / "data" / "raw")
    parser.add_argument("--citation-types", default="E0802,E0805")
    args = parser.parse_args()
    codes = {value.strip() for value in args.citation_types.split(",") if value.strip()}
    if not codes:
        parser.error("At least one citation type code is required")
    if args.from_sampling:
        if args.application_numbers:
            parser.error("Use either application numbers or --from-sampling")
        sampling = json.loads((args.raw_dir / "pilot_case_sampling.json").read_text(encoding="utf-8"))
        args.application_numbers = [
            number for group in sampling["groups"].values() for number in group["selected"]
        ]
    if not args.application_numbers:
        parser.error("Provide application numbers or --from-sampling")

    rows = source_rows(args.raw_dir, args.application_numbers, codes)
    lookup_keys = sorted({(row["lookup_kind"], row["lookup_value"]) for row in rows})
    client = KiprisClient.from_env()
    documents = {}
    fetched = 0
    for kind, value in lookup_keys:
        cache = args.raw_dir / f"cited_{kind}_{value}.xml"
        if cache.exists():
            xml = cache.read_text(encoding="utf-8")
        else:
            xml = (
                client.open_number_search_xml(value)
                if kind == "open_number"
                else client.registration_number_search_xml(value)
            )
            cache.write_text(xml, encoding="utf-8")
            fetched += 1
        documents[(kind, value)] = parse_items(xml)

    linked = build_linkage(rows, documents)
    report = {
        "label_policy": f"{','.join(sorted(codes))} citation proxy; examiner-final status unverified",
        "query_application_numbers": args.application_numbers,
        "citation_type_codes": sorted(codes),
        "unique_cited_documents": len(lookup_keys),
        "new_api_lookups": fetched,
        "linkage": linked,
    }
    output = args.raw_dir / "pilot_document_linkage.json"
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "queries": len(args.application_numbers),
        "citation_rows": len(rows),
        "unique_cited_documents": len(lookup_keys),
        "new_api_lookups": fetched,
        "linked_rows": sum(row["match_count"] == 1 for row in linked),
        "published_before_query_filing_rows": sum(row["published_before_query_filing"] for row in linked),
        "report": str(output),
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

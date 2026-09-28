from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.patent_evidence.dataset import parse_domestic_citation_lookups
from src.patent_evidence.kipris import KiprisClient, KiprisConfigError
from src.patent_evidence.xmlutil import parse_items


def summarize_citations(xml_text: str) -> dict:
    items = parse_items(xml_text)
    domestic = parse_domestic_citation_lookups(xml_text)
    return {
        "citation_item_count": len(items),
        "citation_field_names": sorted({key for item in items for key in item}),
        "citation_divisions": [
            {"code": code, "name": name, "count": count}
            for (code, name), count in sorted(Counter(
                (row["citation_division_code"], row["citation_division_name"])
                for row in domestic
            ).items())
        ],
        "domestic_citation_lookups": domestic,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Inspect one KIPRIS application and its domestic citation lookup keys"
    )
    parser.add_argument("application_number")
    parser.add_argument(
        "--citation-xml",
        type=Path,
        help="Inspect a previously saved citation XML without an API key.",
    )
    parser.add_argument(
        "--raw-dir",
        type=Path,
        default=ROOT / "data" / "raw",
        help="Directory for raw API XML (gitignored by default).",
    )
    parser.add_argument(
        "--citation-operation",
        default="citationInfoV3",
        help="Confirm the active CitationService operation in your KIPRISPlus account/spec.",
    )
    args = parser.parse_args()

    if args.citation_xml:
        search_rows = []
        citation_xml = args.citation_xml.read_text(encoding="utf-8")
    else:
        client = KiprisClient.from_env()
        try:
            search_rows = client.search_application(args.application_number)
            citation_xml = client.citation_xml(
                args.application_number,
                operation=args.citation_operation,
            )
        except (KiprisConfigError, RuntimeError) as exc:
            print(f"KIPRIS ERROR: {exc}", file=sys.stderr)
            return 2
        args.raw_dir.mkdir(parents=True, exist_ok=True)
        (args.raw_dir / f"{args.application_number}.citation.xml").write_text(
            citation_xml, encoding="utf-8"
        )

    result = {
        "application_number": args.application_number,
        "publication_search": search_rows,
        **summarize_citations(citation_xml),
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.patent_evidence.dataset import parse_domestic_citation_lookups
from src.patent_evidence.kipris import KiprisClient, KiprisConfigError


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Inspect one KIPRIS application and its domestic citation lookup keys"
    )
    parser.add_argument("application_number")
    parser.add_argument(
        "--citation-operation",
        default="citationInfoV3",
        help="Confirm the active CitationService operation in your KIPRISPlus account/spec.",
    )
    args = parser.parse_args()

    client = KiprisClient.from_env()
    try:
        search_rows = client.search_application(args.application_number)
        citation_xml = client.citation_xml(
            args.application_number,
            operation=args.citation_operation,
        )
    except KiprisConfigError as exc:
        print(f"CONFIG ERROR: {exc}", file=sys.stderr)
        return 2

    result = {
        "application_number": args.application_number,
        "publication_search": search_rows,
        "domestic_citation_lookups": parse_domestic_citation_lookups(citation_xml),
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

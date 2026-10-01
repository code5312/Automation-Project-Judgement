"""Command-line entry point.

``python -m ipauto.cli search "battery" --technology "..."`` fans the search
out over one or more query terms (paginating each, deduping by 출원번호),
scores the combined records, prints a ranked summary, and saves a debug CSV
under outputs/. This is kept for debugging (docs/DESIGN.md 기존 코드의 새
구조 매핑); the SQLite-backed Judgment flow lives behind the Streamlit UI,
not this CLI.
"""

from __future__ import annotations

import argparse
import csv
import sys
from datetime import datetime
from pathlib import Path

from ipauto.config import get_kipris_access_key, mask_secret
from ipauto.connectors.kipris import (
    DEFAULT_MAX_PAGES_PER_QUERY,
    FIELDS,
    KiprisError,
    fetch_all,
    fetch_by_application_number,
)
from ipauto.scoring.keywords import (
    ANALYSIS_MODE_FIELD,
    MATCHED_FIELD,
    PRIORITY_FIELD,
    REASON_FIELD,
    SCORE_FIELD,
    rank_records,
)


def _save_csv(records: list[dict[str, str | float]]) -> Path:
    output_dir = Path(__file__).resolve().parents[2] / "outputs"
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"kipris_patents_{datetime.now():%Y%m%d_%H%M%S}.csv"
    with path.open("w", newline="", encoding="utf-8-sig") as csv_file:
        writer = csv.DictWriter(
            csv_file,
            fieldnames=[*FIELDS, SCORE_FIELD, PRIORITY_FIELD, MATCHED_FIELD, REASON_FIELD, ANALYSIS_MODE_FIELD],
        )
        writer.writeheader()
        writer.writerows(records)
    return path


def _run_search(args: argparse.Namespace) -> int:
    access_key = get_kipris_access_key()
    if not access_key:
        print("Error: KIPRIS_ACCESS_KEY environment variable is not set.", file=sys.stderr)
        return 1

    try:
        result = fetch_all(
            args.search_query, access_key, page_size=args.count, max_pages_per_query=args.max_pages
        )
    except KiprisError as exc:
        print(f"Error: {mask_secret(str(exc), access_key)}", file=sys.stderr)
        return 1

    if args.debug:
        for query, pages in result.query_page_counts.items():
            print(f"[DEBUG] Query '{query}': {pages} page(s) fetched")
        print(f"[DEBUG] Duplicate records removed (동일 출원번호): {result.duplicate_count}")

    if not result.records:
        print("No patent records were found. No CSV was created.", file=sys.stderr)
        return 1

    ranked = rank_records(args.technology, [record.fields for record in result.records])
    output_path = _save_csv(ranked)

    print(f"KIPRIS broad search: {', '.join(args.search_query)}")
    print(f"Relevance target: {args.technology}")
    print(f"Received {len(ranked)} actual records from KIPRIS Plus, sorted by relevance.")
    for index, record in enumerate(ranked, start=1):
        print(
            f"{index}. {record['발명의 명칭']} | "
            f"{record['출원번호']} | {record['출원인']} | "
            f"{SCORE_FIELD}={record[SCORE_FIELD]} | {record[PRIORITY_FIELD]} | "
            f"{MATCHED_FIELD}={record[MATCHED_FIELD]} | {record[REASON_FIELD]}"
        )
    print(f"CSV saved: {output_path}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ipauto", description="IP judgment automation CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    search = subparsers.add_parser("search", help="Search real KIPRIS Plus records and rank them")
    search.add_argument(
        "search_query",
        nargs="+",
        help="One or more broad KIPRIS API search terms, for example: battery cooling",
    )
    search.add_argument(
        "--technology",
        required=True,
        help="Focused technology to score against, for example: electric vehicle battery cooling",
    )
    search.add_argument("--count", type=int, default=20, help="Results per page (1-20, default: 20)")
    search.add_argument(
        "--max-pages",
        type=int,
        default=DEFAULT_MAX_PAGES_PER_QUERY,
        help=f"Max pages fetched per search term (default: {DEFAULT_MAX_PAGES_PER_QUERY})",
    )
    search.add_argument("--debug", action="store_true", help="Print HTTP/XML diagnostics; access key is redacted")
    search.set_defaults(func=_run_search)

    lookup = subparsers.add_parser(
        "lookup", help="Re-query KIPRIS for one application number (premise reconfirmation/관심목록)"
    )
    lookup.add_argument("application_number", help="예: 10-2020-1234567")
    lookup.set_defaults(func=_run_lookup)

    migrate = subparsers.add_parser(
        "migrate-judgments", help="Migrate legacy data/judgments.json rows into the SQLite ledger"
    )
    migrate.set_defaults(func=_run_migrate_judgments)

    return parser


def _run_lookup(args: argparse.Namespace) -> int:
    access_key = get_kipris_access_key()
    if not access_key:
        print("Error: KIPRIS_ACCESS_KEY environment variable is not set.", file=sys.stderr)
        return 1

    try:
        record = fetch_by_application_number(args.application_number, access_key)
    except KiprisError as exc:
        print(f"Error: {mask_secret(str(exc), access_key)}", file=sys.stderr)
        return 1

    if record is None:
        print(
            "KIPRIS 재검색에서 이 출원번호를 다시 찾지 못했습니다. "
            "자유검색 색인이 출원번호를 포함하지 않을 수 있어 이 결과만으로 '존재하지 않음'을 단정할 수 없습니다.",
            file=sys.stderr,
        )
        return 1

    for label in FIELDS:
        print(f"{label}: {record.get(label) or '-'}")
    return 0


def _run_migrate_judgments(_args: argparse.Namespace) -> int:
    from ipauto.judgments.migrate_json import main as migrate_main

    return migrate_main()


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())

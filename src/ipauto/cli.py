"""Command-line entry point.

``python -m ipauto.cli search "battery" --technology "..."`` reproduces the
original prototype's CLI: fetch one page from KIPRIS, score it, print a
ranked summary, and save a debug CSV under outputs/. This is kept for
debugging (docs/DESIGN.md 기존 코드의 새 구조 매핑); the SQLite-backed
Judgment flow lives behind the Streamlit UI, not this CLI.
"""

from __future__ import annotations

import argparse
import csv
import sys
from datetime import datetime
from pathlib import Path

from ipauto.config import get_kipris_access_key, mask_secret
from ipauto.connectors.kipris import FIELDS, KiprisError, fetch_page
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
        page = fetch_page(args.search_query, access_key, count=args.count)
    except KiprisError as exc:
        print(f"Error: {mask_secret(str(exc), access_key)}", file=sys.stderr)
        return 1

    if args.debug:
        print(f"[DEBUG] HTTP status: {page.http_status}")
        print(f"[DEBUG] KIPRIS resultCode: {page.result_code}")
        print(f"[DEBUG] KIPRIS resultMsg: {page.result_msg}")
        print(f"[DEBUG] KIPRIS successYN: {page.success_yn}")
        print(f"[DEBUG] Discovered <PatentUtilityInfo> count: {page.patent_node_count}")
        print(f"[DEBUG] Discovered <item> count: {page.item_node_count}")
        print(f"[DEBUG] First record child tags: {', '.join(page.first_record_fields)}")

    if not page.records:
        print("No patent records were found. No CSV was created.", file=sys.stderr)
        return 1

    ranked = rank_records(args.technology, [record.fields for record in page.records])
    output_path = _save_csv(ranked)

    print(f"KIPRIS broad search: {args.search_query}")
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
    search.add_argument("search_query", help="Broad KIPRIS API search term, for example: battery")
    search.add_argument(
        "--technology",
        required=True,
        help="Focused technology to score against, for example: electric vehicle battery cooling",
    )
    search.add_argument("--count", type=int, default=20, help="Number of results (1-20, default: 20)")
    search.add_argument("--debug", action="store_true", help="Print HTTP/XML diagnostics; access key is redacted")
    search.set_defaults(func=_run_search)

    migrate = subparsers.add_parser(
        "migrate-judgments", help="Migrate legacy data/judgments.json rows into the SQLite ledger"
    )
    migrate.set_defaults(func=_run_migrate_judgments)

    return parser


def _run_migrate_judgments(_args: argparse.Namespace) -> int:
    from ipauto.judgments.migrate_json import main as migrate_main

    return migrate_main()


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())

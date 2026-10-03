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
import json
import sys
from datetime import datetime
from pathlib import Path

from ipauto.config import get_kipris_access_key, get_llm_api_key, mask_secret
from ipauto.connectors.kipris import (
    DEFAULT_MAX_PAGES_PER_QUERY,
    FIELDS,
    KiprisError,
    fetch_all,
    fetch_by_application_number,
)
from ipauto.db.repositories import ASSET_KIND_CHOICES, ASSET_KIND_OWN
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

    evaluate = subparsers.add_parser(
        "evaluate", help="Measure scoring accuracy against a labeled evaluation set (docs/PIPELINE.md 단계 2)"
    )
    evaluate.add_argument(
        "eval_set_path",
        nargs="?",
        default=str(Path(__file__).resolve().parents[2] / "data" / "eval" / "ev_battery_cooling_v1.json"),
        help="평가 세트 JSON 경로 (기본값: data/eval/ev_battery_cooling_v1.json)",
    )
    evaluate.set_defaults(func=_run_evaluate)

    portfolio = subparsers.add_parser(
        "portfolio-load", help="Load KIPRIS-shaped records (JSON) into the ip_asset portfolio table (단계 3)"
    )
    portfolio.add_argument("records_path", help="출원번호·명칭 등 KIPRIS 필드를 담은 JSON 배열 파일")
    portfolio.add_argument(
        "--asset-kind", default=ASSET_KIND_OWN, choices=ASSET_KIND_CHOICES, help="자사 또는 외부 (기본값: 자사)"
    )
    portfolio.set_defaults(func=_run_portfolio_load)

    github_events = subparsers.add_parser(
        "ingest-github-releases",
        help="Fetch a public GitHub repo's releases and normalize them into Event rows (단계 3 MVP: 오픈소스 공개)",
    )
    github_events.add_argument("owner", help="예: cli")
    github_events.add_argument("repo", help="예: cli")
    github_events.add_argument("--per-page", type=int, default=30, help="가져올 릴리스 수 (1-100, 기본값: 30)")
    github_events.set_defaults(func=_run_ingest_github_releases)

    link_event = subparsers.add_parser(
        "link-event",
        help="Propose Link rows from one Event to the IP asset portfolio by relevance (단계 3)",
    )
    link_event.add_argument("event_id", type=int)
    link_event.set_defaults(func=_run_link_event)

    confirm_link_parser = subparsers.add_parser(
        "confirm-link", help="Mark one proposed Link as confirmed by a human (게이트 A, 단계 3)"
    )
    confirm_link_parser.add_argument("link_id", type=int)
    confirm_link_parser.set_defaults(func=_run_confirm_link)

    classify_parser = subparsers.add_parser(
        "classify-link",
        help="Ask an LLM to classify one Event/IPAsset pair's relevance (단계 3, requires ANTHROPIC_API_KEY)",
    )
    classify_parser.add_argument("event_id", type=int)
    classify_parser.add_argument("ip_asset_id", type=int)
    classify_parser.set_defaults(func=_run_classify_link)

    triage_parser = subparsers.add_parser(
        "triage",
        help="Route one Event/IPAsset pair to 무관/관련/애매 (단계 3; uses the LLM signal if ANTHROPIC_API_KEY is set)",
    )
    triage_parser.add_argument("event_id", type=int)
    triage_parser.add_argument("ip_asset_id", type=int)
    triage_parser.set_defaults(func=_run_triage)

    card_parser = subparsers.add_parser(
        "judgment-card",
        help="Assemble and print the 판단 카드 for one Event/IPAsset pair (단계 3, no LLM call made here)",
    )
    card_parser.add_argument("event_id", type=int)
    card_parser.add_argument("ip_asset_id", type=int)
    card_parser.set_defaults(func=_run_judgment_card)

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


def _run_evaluate(args: argparse.Namespace) -> int:
    from ipauto.evaluation import load_eval_set, measure_accuracy

    path = Path(args.eval_set_path)
    if not path.exists():
        print(f"Error: evaluation set not found: {path}", file=sys.stderr)
        return 1

    items = load_eval_set(path)
    result = measure_accuracy(items)

    print(f"평가 세트: {path} ({result.total}건)")
    print(f"정확도: {result.correct}/{result.total} ({result.accuracy:.1%})")
    print("\n혼동행렬 (사람 라벨 -> 시스템 예측):")
    for (human, predicted), count in sorted(result.confusion.items()):
        marker = "" if human == predicted else "  <- 불일치"
        print(f"  {human} -> {predicted}: {count}건{marker}")

    if result.mismatches:
        print(f"\n불일치 사례 ({len(result.mismatches)}건):")
        for item, predicted in result.mismatches:
            print(f"  [{item.application_number}] {item.title}")
            print(f"    사람: {item.human_label} / 시스템: {predicted} (사람 근거: {item.rationale})")
    return 0


def _run_portfolio_load(args: argparse.Namespace) -> int:
    from ipauto.db.connection import connect, init_db
    from ipauto.portfolio import ingest_records

    path = Path(args.records_path)
    if not path.exists():
        print(f"Error: records file not found: {path}", file=sys.stderr)
        return 1

    records = json.loads(path.read_text(encoding="utf-8"))
    conn = connect()
    init_db(conn)
    try:
        ids = ingest_records(conn, records, asset_kind=args.asset_kind)
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print(f"{path}에서 {len(ids)}건을 ip_asset({args.asset_kind})에 적재했습니다.")
    return 0


def _run_ingest_github_releases(args: argparse.Namespace) -> int:
    from ipauto.connectors.github import GitHubError
    from ipauto.db.connection import connect, init_db
    from ipauto.events import ingest_github_releases

    conn = connect()
    init_db(conn)
    try:
        created, skipped = ingest_github_releases(conn, args.owner, args.repo, per_page=args.per_page)
    except GitHubError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print(f"{args.owner}/{args.repo}: 새 이벤트 {created}건, 이미 있던 이벤트 {skipped}건")
    return 0


def _run_link_event(args: argparse.Namespace) -> int:
    from ipauto.db.connection import connect, init_db
    from ipauto.db.repositories import fetch_event
    from ipauto.linking import link_event_to_ip_assets

    conn = connect()
    init_db(conn)
    event = fetch_event(conn, args.event_id)
    if event is None:
        print(f"Error: event id {args.event_id} not found.", file=sys.stderr)
        return 1

    created_ids = link_event_to_ip_assets(conn, args.event_id, event["summary"] or "")
    print(f"사건 #{args.event_id} ({event['summary']}): 새 Link {len(created_ids)}건 제안됨 (사람 확인 전)")
    return 0


def _run_confirm_link(args: argparse.Namespace) -> int:
    from ipauto.db.connection import connect, init_db
    from ipauto.db.repositories import confirm_link

    conn = connect()
    init_db(conn)
    try:
        confirm_link(conn, args.link_id)
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print(f"Link #{args.link_id}: 사람 확인으로 표시했습니다.")
    return 0


def _run_classify_link(args: argparse.Namespace) -> int:
    from ipauto.connectors.llm import LLMError
    from ipauto.db.connection import connect, init_db
    from ipauto.db.repositories import fetch_event, fetch_ip_asset_by_id
    from ipauto.triage.llm_classifier import ClassificationFormatError, classify

    api_key = get_llm_api_key()
    if not api_key:
        print("Error: ANTHROPIC_API_KEY environment variable is not set.", file=sys.stderr)
        return 1

    conn = connect()
    init_db(conn)
    event = fetch_event(conn, args.event_id)
    if event is None:
        print(f"Error: event id {args.event_id} not found.", file=sys.stderr)
        return 1
    asset = fetch_ip_asset_by_id(conn, args.ip_asset_id)
    if asset is None:
        print(f"Error: ip_asset id {args.ip_asset_id} not found.", file=sys.stderr)
        return 1

    try:
        result = classify(event["summary"] or "", asset["title"] or "", asset["ipc_codes"] or "", api_key=api_key)
    except LLMError as exc:
        print(f"Error: {mask_secret(str(exc), api_key)}", file=sys.stderr)
        return 1
    except ClassificationFormatError as exc:
        print(f"Error: LLM 응답 형식이 올바르지 않습니다: {exc}", file=sys.stderr)
        return 1

    print(f"label: {result.label}")
    print(f"confidence: {result.confidence}")
    print(f"evidence: {result.evidence}")
    print(f"missing_info: {result.missing_info}")
    return 0


def _run_triage(args: argparse.Namespace) -> int:
    from ipauto.connectors.llm import LLMError
    from ipauto.db.connection import connect, init_db
    from ipauto.db.repositories import fetch_event, fetch_ip_asset_by_id
    from ipauto.triage.llm_classifier import ClassificationFormatError, classify
    from ipauto.triage.routing import TRIAGE_AMBIGUOUS, TRIAGE_RELATED, TRIAGE_UNRELATED, decide_triage

    conn = connect()
    init_db(conn)
    event = fetch_event(conn, args.event_id)
    if event is None:
        print(f"Error: event id {args.event_id} not found.", file=sys.stderr)
        return 1
    asset = fetch_ip_asset_by_id(conn, args.ip_asset_id)
    if asset is None:
        print(f"Error: ip_asset id {args.ip_asset_id} not found.", file=sys.stderr)
        return 1

    llm_result = None
    api_key = get_llm_api_key()
    fallback_note = "키워드/IPC 신호만으로 라우팅합니다"
    if api_key:
        event_summary = event["summary"] or ""
        asset_title = asset["title"] or ""
        asset_ipc = asset["ipc_codes"] or ""
        try:
            llm_result = classify(event_summary, asset_title, asset_ipc, api_key=api_key)
        except LLMError as exc:
            print(f"[경고] LLM 호출 실패, {fallback_note}: {mask_secret(str(exc), api_key)}", file=sys.stderr)
        except ClassificationFormatError as exc:
            print(f"[경고] LLM 응답 형식 오류, {fallback_note}: {exc}", file=sys.stderr)
    else:
        print(f"[안내] ANTHROPIC_API_KEY가 없어 {fallback_note}.", file=sys.stderr)

    decision = decide_triage(
        conn,
        event_type=event["event_type"],
        event_summary=event["summary"] or "",
        event_occurred_at=event["occurred_at"],
        asset_title=asset["title"] or "",
        asset_ipc=asset["ipc_codes"] or "",
        application_number=asset["application_number"],
        llm_result=llm_result,
    )

    print(f"outcome: {decision.outcome}")
    for reason in decision.reasons:
        print(f"  - {reason}")

    if decision.outcome == TRIAGE_UNRELATED:
        from ipauto.db.repositories import AutoCloseLogInput, log_auto_close

        _log_id, created = log_auto_close(
            conn,
            AutoCloseLogInput(
                event_id=args.event_id,
                ip_asset_id=args.ip_asset_id,
                keyword_priority=decision.keyword_priority,
                llm_label=llm_result.label if llm_result else None,
                llm_confidence=llm_result.confidence if llm_result else None,
            ),
        )
        print("자동 종결 로그 기록함" if created else "이미 자동 종결 로그에 있음 (중복 기록 안 함)")
    elif decision.outcome == TRIAGE_AMBIGUOUS:
        from ipauto.db.repositories import GateAQueueInput, enqueue_gate_a

        _queue_id, created = enqueue_gate_a(
            conn,
            GateAQueueInput(
                event_id=args.event_id,
                ip_asset_id=args.ip_asset_id,
                keyword_priority=decision.keyword_priority,
                reasons=decision.reasons,
                llm_label=llm_result.label if llm_result else None,
                llm_confidence=llm_result.confidence if llm_result else None,
            ),
        )
        print("게이트 A 대기열에 올림" if created else "이미 게이트 A 대기열에 있음 (중복 기록 안 함)")
    elif decision.outcome == TRIAGE_RELATED:
        from ipauto.cards.judgment_card import build_judgment_card, format_card_text

        card = build_judgment_card(conn, event, asset, llm_result=llm_result)
        print()
        print(format_card_text(card))
    return 0


def _run_judgment_card(args: argparse.Namespace) -> int:
    from ipauto.cards.judgment_card import build_judgment_card, format_card_text
    from ipauto.db.connection import connect, init_db
    from ipauto.db.repositories import fetch_event, fetch_ip_asset_by_id

    conn = connect()
    init_db(conn)
    event = fetch_event(conn, args.event_id)
    if event is None:
        print(f"Error: event id {args.event_id} not found.", file=sys.stderr)
        return 1
    asset = fetch_ip_asset_by_id(conn, args.ip_asset_id)
    if asset is None:
        print(f"Error: ip_asset id {args.ip_asset_id} not found.", file=sys.stderr)
        return 1

    card = build_judgment_card(conn, event, asset)
    print(format_card_text(card))
    return 0


def _run_migrate_judgments(_args: argparse.Namespace) -> int:
    from ipauto.judgments.migrate_json import main as migrate_main

    return migrate_main()


def main(argv: list[str] | None = None) -> int:
    # Korean text printed here (titles, abstracts, rationale notes) isn't
    # guaranteed to be representable in the legacy cp949 codepage that
    # Windows consoles default stdout/stderr to; force UTF-8 so an
    # unrepresentable character (e.g. an em dash) doesn't crash the CLI
    # mid-run instead of just printing correctly or, worst case, mangled.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")

    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())

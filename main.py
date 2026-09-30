"""Fetch real KIPRIS Plus patent records and save them as CSV."""

from __future__ import annotations

import argparse
import csv
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path


# This is the official KIPRIS Plus freeSearchInfo REST endpoint.
API_URL = "http://plus.kipris.or.kr/openapi/rest/patUtiModInfoSearchSevice/freeSearchInfo"
# These XML names are from the official freeSearchInfo response schema.
# The first name in each tuple is the name seen in the user's real response.
FIELDS = {
    "\ubc1c\uba85\uc758 \uba85\uce6d": ("InventionName", "inventionTitle"),
    "\ucd9c\uc6d0\ubc88\ud638": ("ApplicationNumber", "applicationNumber"),
    "\ucd9c\uc6d0\uc778": ("Applicant", "applicantName"),
    "IPC": ("InternationalpatentclassificationNumber", "ipcNumber"),
    "\ub4f1\ub85d\uc0c1\ud0dc": ("RegistrationStatus", "registerStatus"),
    "\ucd08\ub85d": ("Abstract", "astrtCont"),
}
SCORE_FIELD = "relevance_score"
PRIORITY_FIELD = "review_priority"
MATCHED_FIELD = "matched_concepts"
REASON_FIELD = "score_reason"
ANALYSIS_MODE_FIELD = "analysis_mode"
GENERIC_FALLBACK_MESSAGE = (
    "\uc0ac\uc804 \uc815\uc758\ub41c \uae30\uc220 \uac1c\ub150 \uadf8\ub8f9\uc774 \uc5c6\uc5b4 "
    "\uc785\ub825\ub41c \ud3c9\uac00 \uae30\uc220\uc5b4\ub97c \uae30\ubc18\uc73c\ub85c "
    "\ubc94\uc6a9 \ud0a4\uc6cc\ub4dc \ubd84\uc11d\uc744 \uc218\ud589\ud588\uc2b5\ub2c8\ub2e4."
)
PRIORITY_HIGH = "\uac80\ud1a0 \uc6b0\uc120\uc21c\uc704 \ub192\uc74c"
PRIORITY_MEDIUM = "\uac80\ud1a0 \uc6b0\uc120\uc21c\uc704 \ubcf4\ud1b5"
PRIORITY_LOW = "\uac80\ud1a0 \uc6b0\uc120\uc21c\uc704 \ub0ae\uc74c"

# Easily adjustable review bands and transparent concept-score weights.
PRIORITY_HIGH_MIN = 70
PRIORITY_MEDIUM_MIN = 40
CONCEPT_GROUPS = {
    "vehicle": ("\uc804\uae30\ucc28", "\uc804\uae30 \uc790\ub3d9\ucc28", "\ucc28\ub7c9", "\uc790\ub3d9\ucc28"),
    "battery": ("\ubc30\ud130\ub9ac",),
    "cooling": (
        "\ub0c9\uac01", "\uc5f4\uad00\ub9ac", "\uc628\ub3c4\uad00\ub9ac", "\uc218\ub0c9",
        "\ub0c9\uac01\uc218", "\ub0c9\ub9e4", "\uc5f4\uad50\ud658",
    ),
}
# Points per concept mention. Title evidence is worth more than abstract evidence.
TITLE_WEIGHTS = {"vehicle": 3, "battery": 4, "cooling": 6}
ABSTRACT_WEIGHTS = {"vehicle": 2, "battery": 2, "cooling": 3}
CORE_BOTH_BONUS = 65  # battery and cooling both found
SINGLE_CORE_BONUS = 25  # only battery or only cooling found
VEHICLE_PRESENCE_BONUS = 5
IPC_CODE_BONUS = 2  # small supplement only: H01M and/or B60L
GENERIC_TITLE_WEIGHT = 4
GENERIC_ABSTRACT_WEIGHT = 2
GENERIC_MULTI_KEYWORD_BONUS = 3
GENERIC_IPC_WEIGHT = 1
KOREAN_PARTICLES = (
    "\uc73c\ub85c\ubd80\ud130", "\uc5d0\uac8c\uc11c", "\uc5d0\uc11c\ub294", "\uc73c\ub85c", "\uc5d0\uac8c",
    "\ud55c\ud14c", "\ubd80\ud130", "\uae4c\uc9c0", "\ucc98\ub7fc", "\ubcf4\ub2e4", "\uc774\ub791", "\ud558\uace0",
    "\uc774\ub098", "\ub77c\ub3c4", "\ub9c8\uc800", "\uc870\ucc28", "\uc740", "\ub294", "\uc774", "\uac00",
    "\uc744", "\ub97c", "\uc758", "\uc5d0", "\ub85c", "\uc640", "\uacfc", "\ub3c4", "\ub9cc", "\ub791", "\uaed8",
)
KOREAN_VERB_ENDINGS = (
    "\ud558\uc5ec\uc11c", "\ud558\uba74\uc11c", "\ud558\ub294", "\ud558\uae30", "\ud558\uba70", "\ud558\uace0",
    "\ud55c\ub2e4", "\ub41c\ub2e4", "\ub418\ub294", "\ub418\uace0", "\ud558\uc5ec", "\ud568",
)
GENERIC_STOPWORDS = {
    "\uae30\uc220", "\ubc29\ubc95", "\uc2dc\uc2a4\ud15c", "\uc7a5\uce58", "\uad6c\uc870", "\uad00\ub828",
    "\ubd84\uc57c", "\uc704\ud55c", "\ub300\ud55c", "\ud1b5\ud55c", "\ud2b9\ud5c8", "\ubc0f", "\ub610\ub294",
    "\uadf8\ub9ac\uace0", "\ub4f1", "\uac01", "\ubcf8", "\uc5ec\ub7ec",
}


def local_name(tag: str) -> str:
    """Return an XML tag without its optional namespace."""
    return tag.rsplit("}", 1)[-1]


def text_of(parent: ET.Element, names: tuple[str, ...] | str) -> str:
    if isinstance(names, str):
        names = (names,)
    for node in parent.iter():
        if local_name(node.tag) in names:
            return " ".join("".join(node.itertext()).split())
    return ""


def classify_priority(score: float) -> str:
    """Map a 0-100 review score to the configurable human-review band."""
    if score >= PRIORITY_HIGH_MIN:
        return PRIORITY_HIGH
    if score >= PRIORITY_MEDIUM_MIN:
        return PRIORITY_MEDIUM
    return PRIORITY_LOW


def _has_phrase(text: str, phrase: str) -> bool:
    """Match a listed concept phrase literally; no fuzzy/partial-character matching."""
    return phrase.casefold() in text.casefold()


def _ipc_families(ipc_value: str) -> list[str]:
    """Recognize only the two configured IPC code families, not Korean keywords."""
    compact = re.sub(r"\s+", "", ipc_value.upper())
    return [
        code
        for code in ("H01M", "B60L")
        if re.search(rf"(?<![A-Z0-9]){code}(?=\d|/|$)", compact)
    ]


def extract_generic_keywords(technology: str) -> list[str]:
    """Extract distinct, useful literal terms when no configured group applies."""
    raw_terms = re.findall(r"[\w]+", technology.casefold(), flags=re.UNICODE)
    keywords = []
    for raw in raw_terms:
        term = raw
        for suffix in (*KOREAN_VERB_ENDINGS, *KOREAN_PARTICLES):
            if term.endswith(suffix) and len(term) - len(suffix) >= 2:
                term = term[: -len(suffix)]
                break
        if len(term) < 2 or term in GENERIC_STOPWORDS:
            continue
        if not re.search(r"[A-Za-z\uac00-\ud7a3]", term, flags=re.UNICODE):
            continue
        if term not in keywords:
            keywords.append(term)
    return keywords


def _calculate_generic_relevance(
    technology: str, title: str, abstract: str, ipc_value: str
) -> dict[str, str | float]:
    keywords = extract_generic_keywords(technology)
    if not keywords:
        return {
            SCORE_FIELD: 0.0,
            PRIORITY_FIELD: classify_priority(0),
            MATCHED_FIELD: "",
            REASON_FIELD: "\uc758\ubbf8 \uc788\ub294 \ud0a4\uc6cc\ub4dc\ub97c \ucd94\ucd9c\ud558\uc9c0 \ubabb\ud574 0\uc810 \ucc98\ub9ac",
            ANALYSIS_MODE_FIELD: "generic_keyword",
        }

    folded_title = title.casefold()
    folded_abstract = abstract.casefold()
    title_hits = [word for word in keywords if word in folded_title]
    abstract_hits = [word for word in keywords if word in folded_abstract]
    found = list(dict.fromkeys([*title_hits, *abstract_hits]))
    ipc_hits = _ipc_families(ipc_value)

    points = len(title_hits) * GENERIC_TITLE_WEIGHT
    points += len(abstract_hits) * GENERIC_ABSTRACT_WEIGHT
    multi_bonus = GENERIC_MULTI_KEYWORD_BONUS if len(found) >= 2 else 0
    points += multi_bonus
    ipc_points = len(ipc_hits) * GENERIC_IPC_WEIGHT
    points += ipc_points
    maximum = len(keywords) * (GENERIC_TITLE_WEIGHT + GENERIC_ABSTRACT_WEIGHT)
    maximum += GENERIC_MULTI_KEYWORD_BONUS if len(keywords) >= 2 else 0
    maximum += 2 * GENERIC_IPC_WEIGHT
    score = round(100 * points / maximum, 1) if maximum else 0.0

    reasons = []
    if title_hits:
        reasons.append("\uc81c\ubaa9 \ud0a4\uc6cc\ub4dc: " + "\u00b7".join(title_hits))
    if abstract_hits:
        reasons.append("\ucd08\ub85d \ud0a4\uc6cc\ub4dc: " + "\u00b7".join(abstract_hits))
    if multi_bonus:
        reasons.append("\ubcf5\uc218 \ud0a4\uc6cc\ub4dc \ub3d9\uc2dc \ubc1c\uacac (+3\uc810)")
    if ipc_hits:
        reasons.append("IPC \ubcf4\uc870 \ud655\uc778: " + "/".join(ipc_hits))
    if not reasons:
        reasons.append("\uc81c\ubaa9\u00b7\ucd08\ub85d\uc5d0\uc11c \ud0a4\uc6cc\ub4dc\ub97c \ucc3e\uc9c0 \ubabb\ud568")
    return {
        SCORE_FIELD: score,
        PRIORITY_FIELD: classify_priority(score),
        MATCHED_FIELD: ";".join(found),
        REASON_FIELD: ", ".join(reasons),
        ANALYSIS_MODE_FIELD: "generic_keyword",
    }


def calculate_relevance(technology: str, record: dict[str, str]) -> dict[str, str | float]:
    """Return score, priority, matched concepts, and a human-readable explanation."""
    target_concepts = {
        concept
        for concept, phrases in CONCEPT_GROUPS.items()
        if any(_has_phrase(technology, phrase) for phrase in phrases)
    }
    title = record.get("\ubc1c\uba85\uc758 \uba85\uce6d", "") or ""
    abstract = record.get("\ucd08\ub85d", "") or ""
    ipc_value = record.get("IPC", "") or ""
    title_hits: set[str] = set()
    abstract_hits: set[str] = set()
    for concept, phrases in CONCEPT_GROUPS.items():
        if concept not in target_concepts:
            continue
        if any(_has_phrase(title, phrase) for phrase in phrases):
            title_hits.add(concept)
        if any(_has_phrase(abstract, phrase) for phrase in phrases):
            abstract_hits.add(concept)

    found_concepts = title_hits | abstract_hits
    if not target_concepts:
        return _calculate_generic_relevance(technology, title, abstract, ipc_value)

    detected_ipc = _ipc_families(ipc_value)
    ipc_hits = [
        code for code in detected_ipc
        if (code == "H01M" and "battery" in target_concepts)
        or (code == "B60L" and "vehicle" in target_concepts)
    ]
    score = sum(TITLE_WEIGHTS[c] for c in title_hits)
    score += sum(ABSTRACT_WEIGHTS[c] for c in abstract_hits)
    has_battery = "battery" in found_concepts
    has_cooling = "cooling" in found_concepts
    has_vehicle = "vehicle" in found_concepts
    if has_battery and has_cooling:
        score += CORE_BOTH_BONUS
    elif has_battery or has_cooling:
        score += SINGLE_CORE_BONUS
    if has_vehicle:
        score += VEHICLE_PRESENCE_BONUS
    score += IPC_CODE_BONUS * len(ipc_hits)
    score = float(min(score, 100))

    concept_order = ("vehicle", "battery", "cooling")
    matched = [concept for concept in concept_order if concept in found_concepts]
    matched.extend(f"IPC:{code}" for code in ipc_hits)
    reasons = []
    if has_battery and has_cooling:
        reasons.append("\ubc30\ud130\ub9ac\u00b7\ub0c9\uac01 \uac1c\ub150 \ubaa8\ub450 \ud655\uc778")
    elif has_battery:
        reasons.append("\ubc30\ud130\ub9ac \uac1c\ub150 \ud655\uc778")
    elif has_cooling:
        reasons.append("\ub0c9\uac01 \uac1c\ub150 \ud655\uc778")
    if has_vehicle:
        reasons.append("\ucc28\ub7c9 \uac1c\ub150 \ud655\uc778")
    title_names = [name for name, key in (("\ucc28\ub7c9", "vehicle"), ("\ubc30\ud130\ub9ac", "battery"), ("\ub0c9\uac01", "cooling")) if key in title_hits]
    abstract_names = [name for name, key in (("\ucc28\ub7c9", "vehicle"), ("\ubc30\ud130\ub9ac", "battery"), ("\ub0c9\uac01", "cooling")) if key in abstract_hits]
    if title_names:
        reasons.append("\uc81c\ubaa9\uc5d0\uc11c " + "\u00b7".join(title_names) + " \ubc1c\uacac")
    if abstract_names:
        reasons.append("\ucd08\ub85d\uc5d0\uc11c " + "\u00b7".join(abstract_names) + " \ubc1c\uacac")
    if ipc_hits:
        reasons.append("/".join(ipc_hits) + " IPC \ud655\uc778")
    if not reasons:
        reasons.append("\ud3c9\uac00 \uac1c\ub150\uc744 \uc81c\ubaa9\u00b7\ucd08\ub85d\u00b7IPC\uc5d0\uc11c \ucc3e\uc9c0 \ubabb\ud568")

    return {
        SCORE_FIELD: score,
        PRIORITY_FIELD: classify_priority(score),
        MATCHED_FIELD: ";".join(matched),
        REASON_FIELD: ", ".join(reasons),
        ANALYSIS_MODE_FIELD: "concept_group",
    }


def rank_records(technology: str, records: list[dict[str, str]]) -> list[dict[str, str | float]]:
    """Add assessment fields and sort by score descending (stable ties)."""
    ranked = []
    for record in records:
        result = dict(record)
        result.update(calculate_relevance(technology, result))
        ranked.append(result)
    return sorted(ranked, key=lambda record: float(record[SCORE_FIELD]), reverse=True)


def parse_response(
    xml_data: bytes,
) -> tuple[list[dict[str, str]], dict[str, str], int, int, list[str]]:
    try:
        root = ET.fromstring(xml_data)
    except ET.ParseError as exc:
        raise ValueError("KIPRIS response is not valid XML.") from exc

    metadata = {
        "resultCode": text_of(root, "resultCode"),
        "resultMsg": text_of(root, "resultMsg"),
        "successYN": text_of(root, "successYN"),
    }

    # Match both the documented PatentUtilityInfo group and legacy <item> rows.
    # local_name() also handles namespaced XML tags such as {namespace}PatentUtilityInfo.
    patent_nodes = [node for node in root.iter() if local_name(node.tag) == "PatentUtilityInfo"]
    item_nodes = [node for node in root.iter() if local_name(node.tag) == "item"]
    record_nodes = patent_nodes + item_nodes
    first_record_fields = (
        [local_name(child.tag) for child in list(record_nodes[0])]
        if record_nodes
        else []
    )
    records = []
    for item in record_nodes:
        record = {label: text_of(item, xml_names) for label, xml_names in FIELDS.items()}
        # Do not turn metadata/empty nodes into patent records.
        if record["\ubc1c\uba85\uc758 \uba85\uce6d"] or record["\ucd9c\uc6d0\ubc88\ud638"]:
            records.append(record)
    return records, metadata, len(patent_nodes), len(item_nodes), first_record_fields


def fetch_records(
    query: str, api_key: str, count: int
) -> tuple[list[dict[str, str]], dict[str, str], int, int, list[str], int, bytes]:
    # Parameter names and endpoint follow the official freeSearchInfo example.
    params = {
        "word": query,
        "patent": "true",
        "utility": "true",
        "docsStart": "1",
        "docsCount": str(count),
        "lastvalue": "",
        "accessKey": api_key,
    }
    url = f"{API_URL}?{urllib.parse.urlencode(params)}"
    request = urllib.request.Request(url, headers={"User-Agent": "KIPRIS-Patent-Review-MVP/0.1"})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            http_status = response.status
            body = response.read()
    except urllib.error.HTTPError as exc:
        body = exc.read()
        # Keep error response diagnostics available, including a possible XML body.
        try:
            records, metadata, patent_count, item_count, first_fields = parse_response(body)
        except ValueError:
            records, patent_count, item_count, first_fields = [], 0, 0, []
            metadata = {"resultCode": "", "resultMsg": "", "successYN": ""}
        return records, metadata, patent_count, item_count, first_fields, exc.code, body
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Could not connect to KIPRIS Plus: {exc.reason}") from exc
    except TimeoutError as exc:
        raise RuntimeError("KIPRIS Plus request timed out.") from exc

    records, metadata, patent_count, item_count, first_fields = parse_response(body)
    return records, metadata, patent_count, item_count, first_fields, http_status, body


def collect_kipris_data(search_query: str, api_key: str, count: int = 20) -> list[dict[str, str]]:
    """Reusable public API for collecting real KIPRIS records without CLI/debug output."""
    if not api_key:
        raise ValueError("KIPRIS API key is required.")
    if not 1 <= count <= 20:
        raise ValueError("count must be between 1 and 20.")
    records, _metadata, _patent_count, _item_count, _fields, _status, _body = fetch_records(
        search_query, api_key, count
    )
    return records


def save_csv(records: list[dict[str, str]]) -> Path:
    output_dir = Path(__file__).resolve().parent / "outputs"
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


def print_debug(
    http_status: int,
    metadata: dict[str, str],
    body: bytes,
    api_key: str,
    patent_count: int,
    item_count: int,
    first_record_fields: list[str],
) -> None:
    preview = body[:1200].decode("utf-8-sig", errors="replace")
    if api_key:
        preview = preview.replace(api_key, "[REDACTED]")
    preview = re.sub(r"(?i)(accessKey|serviceKey)(\s*[=:]\s*)[^&\s<>\"']+", r"\1\2[REDACTED]", preview)
    print(f"[DEBUG] HTTP status: {http_status}")
    print(f"[DEBUG] KIPRIS resultCode: {metadata.get('resultCode', '')}")
    print(f"[DEBUG] KIPRIS resultMsg: {metadata.get('resultMsg', '')}")
    print(f"[DEBUG] KIPRIS successYN: {metadata.get('successYN', '')}")
    print(f"[DEBUG] Discovered <PatentUtilityInfo> count: {patent_count}")
    print(f"[DEBUG] Discovered <item> count: {item_count}")
    print(f"[DEBUG] First record child tags: {', '.join(first_record_fields)}")
    print("[DEBUG] Response XML preview (first 1200 bytes; API key redacted):")
    print(preview)


def main() -> int:
    parser = argparse.ArgumentParser(description="Search real KIPRIS Plus patent records and save CSV")
    parser.add_argument("search_query", help="Broad KIPRIS API search term, for example: battery")
    parser.add_argument(
        "--technology",
        required=True,
        help="Focused technology to score against, for example: electric vehicle battery cooling",
    )
    parser.add_argument("--count", type=int, default=20, help="Number of results (1-20, default: 20)")
    parser.add_argument("--debug", action="store_true", help="Print HTTP/XML diagnostics; API key is redacted")
    args = parser.parse_args()

    api_key = os.getenv("KIPRIS_API_KEY")
    if not api_key:
        print("Error: KIPRIS_API_KEY environment variable is not set.", file=sys.stderr)
        return 1
    if not 1 <= args.count <= 20:
        print("Error: --count must be between 1 and 20.", file=sys.stderr)
        return 1

    try:
        records, metadata, patent_count, item_count, first_fields, http_status, body = fetch_records(
            args.search_query, api_key, args.count
        )
        if args.debug:
            print_debug(http_status, metadata, body, api_key, patent_count, item_count, first_fields)
        if not records:
            print("No patent records were found. No CSV was created.", file=sys.stderr)
            return 1
        ranked_records = rank_records(args.technology, records)
        output_path = save_csv(ranked_records)
    except (ValueError, RuntimeError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print(f"KIPRIS broad search: {args.search_query}")
    print(f"Relevance target: {args.technology}")
    print(f"Received {len(ranked_records)} actual records from KIPRIS Plus, sorted by relevance.")
    for index, record in enumerate(ranked_records, start=1):
        print(
            f"{index}. {record['\ubc1c\uba85\uc758 \uba85\uce6d']} | "
            f"{record['\ucd9c\uc6d0\ubc88\ud638']} | {record['\ucd9c\uc6d0\uc778']} | "
            f"{SCORE_FIELD}={record[SCORE_FIELD]} | {record[PRIORITY_FIELD]} | "
            f"{MATCHED_FIELD}={record[MATCHED_FIELD]} | {record[REASON_FIELD]}"
        )
    print(f"CSV saved: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

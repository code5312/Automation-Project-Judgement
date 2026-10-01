"""KIPRIS Plus freeSearchInfo connector.

Calls the official freeSearchInfo REST endpoint, parses the response with
``defusedxml`` (untrusted external XML), and raises a typed exception for
each distinguishable failure mode instead of returning ambiguous results.
"HTTP call failed" and "the call succeeded but found zero records" are never
confused: the former raises, the latter returns an empty list.

``fetch_page`` fetches a single page. ``fetch_all`` (단계 2) fans a search out
over multiple query terms, paginates each one until KIPRIS returns a short
page, and dedupes the combined records by 출원번호.
"""

from __future__ import annotations

import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from xml.etree.ElementTree import Element

from defusedxml.ElementTree import ParseError, fromstring

from ipauto.config import get_kipris_base_url, mask_secret

# These XML element names follow the official freeSearchInfo response schema.
# The first name in each tuple is the name observed in a real response; the
# second is the documented alternate seen on some KIPRIS endpoints.
FIELDS: dict[str, tuple[str, str]] = {
    "발명의 명칭": ("InventionName", "inventionTitle"),
    "출원번호": ("ApplicationNumber", "applicationNumber"),
    "출원인": ("Applicant", "applicantName"),
    "IPC": ("InternationalpatentclassificationNumber", "ipcNumber"),
    "등록상태": ("RegistrationStatus", "registerStatus"),
    "초록": ("Abstract", "astrtCont"),
}

MIN_COUNT = 1
MAX_COUNT = 20  # KIPRIS docsCount upper bound, per the API's documented behavior.

_USER_AGENT = "ipauto-kipris-connector/0.1"


class KiprisError(Exception):
    """Base class for all KIPRIS connector failures."""


class KiprisAuthError(KiprisError):
    """The access key was rejected (HTTP 401/403)."""


class KiprisQuotaError(KiprisError):
    """The call was throttled or the quota was exhausted (HTTP 429)."""


class KiprisNetworkError(KiprisError):
    """The request could not reach KIPRIS Plus, or it timed out."""


class KiprisResponseError(KiprisError):
    """KIPRIS returned a response it marked as unsuccessful (successYN != 'Y')."""


@dataclass(frozen=True)
class KiprisRecord:
    """One patent/utility-model row, keyed by the same Korean field names as FIELDS."""

    fields: dict[str, str]

    def get(self, label: str) -> str:
        return self.fields.get(label, "")


@dataclass(frozen=True)
class KiprisPage:
    """One page of a KIPRIS freeSearchInfo call."""

    records: list[KiprisRecord]
    result_code: str
    result_msg: str
    success_yn: str
    http_status: int
    patent_node_count: int
    item_node_count: int
    first_record_fields: list[str] = field(default_factory=list)


def _local_name(tag: str) -> str:
    """Strip an optional XML namespace from a tag name."""
    return tag.rsplit("}", 1)[-1]


def _text_of(parent: Element, names: tuple[str, ...] | str) -> str:
    if isinstance(names, str):
        names = (names,)
    for node in parent.iter():
        if _local_name(node.tag) in names:
            return " ".join("".join(node.itertext()).split())
    return ""


def parse_response(xml_data: bytes) -> KiprisPage:
    """Parse a raw freeSearchInfo XML body. Exposed for tests and offline replay."""
    try:
        root = fromstring(xml_data)
    except ParseError as exc:
        raise KiprisResponseError("KIPRIS response is not valid XML.") from exc

    result_code = _text_of(root, "resultCode")
    result_msg = _text_of(root, "resultMsg")
    success_yn = _text_of(root, "successYN")

    # Both the documented PatentUtilityInfo group and the legacy <item> rows
    # are matched; _local_name also handles namespaced tags.
    patent_nodes = [node for node in root.iter() if _local_name(node.tag) == "PatentUtilityInfo"]
    item_nodes = [node for node in root.iter() if _local_name(node.tag) == "item"]
    record_nodes = patent_nodes + item_nodes
    first_record_fields = [_local_name(child.tag) for child in list(record_nodes[0])] if record_nodes else []

    records: list[KiprisRecord] = []
    for node in record_nodes:
        row = {label: _text_of(node, xml_names) for label, xml_names in FIELDS.items()}
        # Skip metadata/empty nodes that are not actual patent records.
        if row["발명의 명칭"] or row["출원번호"]:
            records.append(KiprisRecord(fields=row))

    return KiprisPage(
        records=records,
        result_code=result_code,
        result_msg=result_msg,
        success_yn=success_yn,
        http_status=0,  # filled in by the caller
        patent_node_count=len(patent_nodes),
        item_node_count=len(item_nodes),
        first_record_fields=first_record_fields,
    )


def fetch_page(query: str, access_key: str, count: int = MAX_COUNT, start: int = 1) -> KiprisPage:
    """Fetch one page of results. Raises a typed KiprisError on any failure.

    An empty ``records`` list with no exception means the call succeeded and
    found zero matches; it is never used to signal a failed call.
    """
    if not access_key:
        raise ValueError("KIPRIS access key is required.")
    if not MIN_COUNT <= count <= MAX_COUNT:
        raise ValueError(f"count must be between {MIN_COUNT} and {MAX_COUNT}.")

    params = {
        "word": query,
        "patent": "true",
        "utility": "true",
        "docsStart": str(start),
        "docsCount": str(count),
        "lastvalue": "",
        "accessKey": access_key,
    }
    url = f"{get_kipris_base_url()}?{urllib.parse.urlencode(params)}"
    request = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})

    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            http_status = response.status
            body = response.read()
    except urllib.error.HTTPError as exc:
        if exc.code in (401, 403):
            raise KiprisAuthError(f"KIPRIS rejected the access key (HTTP {exc.code}).") from exc
        if exc.code == 429:
            raise KiprisQuotaError("KIPRIS quota exceeded or request throttled (HTTP 429).") from exc
        message = mask_secret(f"KIPRIS returned HTTP {exc.code}.", access_key)
        raise KiprisError(message) from exc
    except TimeoutError as exc:
        raise KiprisNetworkError("KIPRIS Plus request timed out.") from exc
    except urllib.error.URLError as exc:
        raise KiprisNetworkError(mask_secret(f"Could not connect to KIPRIS Plus: {exc.reason}", access_key)) from exc

    page = parse_response(body)
    page = KiprisPage(
        records=page.records,
        result_code=page.result_code,
        result_msg=page.result_msg,
        success_yn=page.success_yn,
        http_status=http_status,
        patent_node_count=page.patent_node_count,
        item_node_count=page.item_node_count,
        first_record_fields=page.first_record_fields,
    )
    raise_if_unsuccessful(page, access_key)
    return page


DEFAULT_MAX_PAGES_PER_QUERY = 10  # safety cap: 10 * MAX_COUNT = 200 records per query


@dataclass(frozen=True)
class MultiQueryResult:
    """Combined, deduplicated result of fanning a search out over several queries."""

    records: list[KiprisRecord]
    duplicate_count: int
    query_page_counts: dict[str, int]


def dedupe_by_application_number(records: list[KiprisRecord]) -> tuple[list[KiprisRecord], int]:
    """Drop records sharing a non-empty 출원번호, keeping the first occurrence.

    Records with no 출원번호 can't be deduplicated reliably and are all kept.
    """
    seen: set[str] = set()
    deduped: list[KiprisRecord] = []
    duplicate_count = 0
    for record in records:
        application_number = record.get("출원번호")
        if application_number:
            if application_number in seen:
                duplicate_count += 1
                continue
            seen.add(application_number)
        deduped.append(record)
    return deduped, duplicate_count


def fetch_all(
    queries: list[str],
    access_key: str,
    page_size: int = MAX_COUNT,
    max_pages_per_query: int = DEFAULT_MAX_PAGES_PER_QUERY,
) -> MultiQueryResult:
    """Fan a search out over multiple query terms with pagination, then dedupe.

    Each query is paginated until KIPRIS returns a page shorter than
    ``page_size`` (no more results) or ``max_pages_per_query`` is reached.
    Raises a typed KiprisError on the first failing call, same as fetch_page.
    """
    if not queries:
        raise ValueError("At least one search query is required.")

    all_records: list[KiprisRecord] = []
    query_page_counts: dict[str, int] = {}
    for query in queries:
        start = 1
        pages_fetched = 0
        for _ in range(max_pages_per_query):
            page = fetch_page(query, access_key, count=page_size, start=start)
            pages_fetched += 1
            all_records.extend(page.records)
            if len(page.records) < page_size:
                break
            start += page_size
        query_page_counts[query] = pages_fetched

    deduped, duplicate_count = dedupe_by_application_number(all_records)
    return MultiQueryResult(records=deduped, duplicate_count=duplicate_count, query_page_counts=query_page_counts)


def raise_if_unsuccessful(page: KiprisPage, access_key: str | None = None) -> None:
    """Raise KiprisResponseError when a parsed page reports successYN != 'Y'.

    Split out from fetch_page so the "0 results" vs "call failure" branch can
    be exercised in tests without a real network call.
    """
    if page.success_yn and page.success_yn.upper() != "Y":
        message = mask_secret(page.result_msg or "KIPRIS reported an unsuccessful call.", access_key)
        raise KiprisResponseError(message)

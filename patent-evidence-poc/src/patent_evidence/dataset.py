from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from .citations import citation_to_lookup
from .xmlutil import parse_items


CITATION_FIELD_ALIASES = {
    "country": (
        "StandardCitationLiteratureCountryCode",
        "standardCitationLiteratureCountryCode",
        "standardCitationLiteratureNationCode",
        "STAND_LTRTRE_NAT_CODE",
    ),
    "ident": (
        "StandardCitationIdentificationCode",
        "standardCitationIdentificationCode",
        "standardCitationIdntfcCode",
        "STAND_LTRTRE_IDNTFC_CODE",
    ),
    "number": (
        "StandardCitationLiteraturenumber",
        "standardCitationLiteraturenumber",
        "standardCitationLiteratureNumber",
        "standardCitationLiteratureNum",
        "STAND_LTRTRE_NUM",
    ),
    "division_code": (
        "CitationLiteratureTypeCode",
        "standardCitationLiteratureDivisionCode",
        "standardCitationDivisionCode",
        "STAND_LTRTRE_DIV_CODE",
    ),
    "division_name": (
        "CitationLiteratureTypeCodeName",
        "standardCitationLiteratureDivisionCodeName",
        "standardCitationDivisionCodeName",
        "STAND_LTRTRE_DIV_CODE_NM",
    ),
}


def _pick(row: dict[str, str], names: tuple[str, ...]) -> str:
    for name in names:
        if row.get(name):
            return row[name]
    return ""


def parse_domestic_citation_lookups(xml_text: str) -> list[dict]:
    """Parse KR A/U/B/Y citations.

    Important: these are citation records, NOT automatically gold labels.
    KIPRISPlus citation data can include multiple citation origins. Keep the
    division code/name so a benchmark can explicitly select its gold policy.
    """
    unique = {}
    for item in parse_items(xml_text):
        lookup = citation_to_lookup(
            _pick(item, CITATION_FIELD_ALIASES["country"]),
            _pick(item, CITATION_FIELD_ALIASES["ident"]),
            _pick(item, CITATION_FIELD_ALIASES["number"]),
        )
        if lookup is None:
            continue

        division_code = _pick(item, CITATION_FIELD_ALIASES["division_code"])
        division_name = _pick(item, CITATION_FIELD_ALIASES["division_name"])
        key = (
            lookup.lookup_kind,
            lookup.lookup_value,
            division_code,
            division_name,
        )
        unique[key] = {
            "country_code": lookup.country_code,
            "identification_code": lookup.identification_code,
            "literature_number": lookup.literature_number,
            "lookup_kind": lookup.lookup_kind,
            "lookup_value": lookup.lookup_value,
            "citation_division_code": division_code,
            "citation_division_name": division_name,
        }
    return [unique[key] for key in sorted(unique)]


def citation_division_counts(records: list[dict]) -> dict[str, int]:
    counts = Counter((r.get("citation_division_name") or "(missing)") for r in records)
    return dict(sorted(counts.items()))


def select_gold_candidates(
    records: list[dict],
    *,
    allowed_division_names: set[str] | None = None,
    allowed_division_codes: set[str] | None = None,
) -> list[dict]:
    """Select benchmark gold only after an explicit citation-origin policy.

    We intentionally require a non-empty whitelist. KIPRISPlus states that the
    citation product contains more than one citation source, so treating every
    row as an examiner relevance label would overclaim the benchmark.
    """
    if not allowed_division_names and not allowed_division_codes:
        raise ValueError("citation division whitelist must be explicitly defined")
    return [
        row
        for row in records
        if row.get("citation_division_name") in (allowed_division_names or set())
        or row.get("citation_division_code") in (allowed_division_codes or set())
    ]


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")

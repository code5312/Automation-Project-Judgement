from __future__ import annotations

import json
from pathlib import Path

from .citations import citation_to_lookup
from .xmlutil import parse_items


CITATION_FIELD_ALIASES = {
    "country": (
        "standardCitationLiteratureCountryCode",
        "standardCitationLiteratureNationCode",
    ),
    "ident": (
        "standardCitationIdentificationCode",
        "standardCitationIdntfcCode",
    ),
    "number": (
        "standardCitationLiteraturenumber",
        "standardCitationLiteratureNumber",
        "standardCitationLiteratureNum",
    ),
}


def _pick(row: dict[str, str], names: tuple[str, ...]) -> str:
    for name in names:
        if row.get(name):
            return row[name]
    return ""


def parse_domestic_citation_lookups(xml_text: str) -> list[dict]:
    unique = {}
    for item in parse_items(xml_text):
        lookup = citation_to_lookup(
            _pick(item, CITATION_FIELD_ALIASES["country"]),
            _pick(item, CITATION_FIELD_ALIASES["ident"]),
            _pick(item, CITATION_FIELD_ALIASES["number"]),
        )
        if lookup is None:
            continue
        key = (lookup.lookup_kind, lookup.lookup_value)
        unique[key] = {
            "country_code": lookup.country_code,
            "identification_code": lookup.identification_code,
            "literature_number": lookup.literature_number,
            "lookup_kind": lookup.lookup_kind,
            "lookup_value": lookup.lookup_value,
        }
    return [unique[key] for key in sorted(unique)]


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")

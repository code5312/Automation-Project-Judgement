from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CitationLookup:
    country_code: str
    identification_code: str
    literature_number: str
    lookup_kind: str
    lookup_value: str


def normalize_number(value: str | None) -> str:
    if not value:
        return ""
    return "".join(ch for ch in value.strip() if ch.isalnum())


def citation_to_lookup(
    country_code: str | None,
    identification_code: str | None,
    literature_number: str | None,
) -> CitationLookup | None:
    country = (country_code or "").strip().upper()
    ident = (identification_code or "").strip().upper()
    number = normalize_number(literature_number)

    if not number or country != "KR" or not ident:
        return None

    first = ident[0]
    if first in {"A", "U"}:
        return CitationLookup(country, ident, number, "open_number", number)
    if first in {"B", "Y"}:
        return CitationLookup(country, ident, number, "registration_number", number)
    return None

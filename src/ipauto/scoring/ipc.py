"""IPC-code signal.

Two layers: a coarse family-level signal from ``detected_families()`` (any
configured family such as H01M/B60L present anywhere in the field), and a
confirmed precise signal from ``detected_primary_signals()`` — the exact
H01M 10/60-10/667 battery temperature-control subrange, cross-checked
against the WIPO IPC 2026.01 scheme and USPTO's CPC definition for H01M10/60
("Heating or cooling; Temperature control") through H01M10/667, the last
code before the next group (H01M12/00) starts; see docs/OPEN_QUESTIONS.md
for the sources and the 2026-10-01 confirmation. Both layers are configured
in config/ipc_rules.yaml, not hardcoded here.

IPC/CPC subgroup digits after the slash are compared as a decimal fraction,
which is how the classification itself orders subgroups: "613" -> 0.613,
"6235" -> 0.6235 (so it correctly sorts between "623" and "625").
"""

from __future__ import annotations

import re
from functools import cache

from ipauto.scoring import rules

_CODE_PATTERN = re.compile(r"([A-Z]\d{2}[A-Z])(\d+)/(\d+)")


@cache
def _family_pattern(code: str) -> re.Pattern[str]:
    return re.compile(rf"(?<![A-Z0-9]){code}(?=\d|/|$)")


def detected_families(ipc_value: str) -> list[str]:
    """Return which configured IPC families appear in a raw IPC field value."""
    compact = re.sub(r"\s+", "", ipc_value.upper())
    return [code for code in rules.get_ipc_rules().families if _family_pattern(code).search(compact)]


def detected_primary_signals(ipc_value: str) -> list[tuple[str, str]]:
    """Return (raw_code, concept) pairs for codes inside a confirmed precise subrange."""
    compact = re.sub(r"\s+", "", ipc_value.upper())
    hits: list[tuple[str, str]] = []
    for family, group, subgroup in _CODE_PATTERN.findall(compact):
        fraction = float(f"0.{subgroup}")
        for signal in rules.get_ipc_rules().primary_signals:
            if signal.matches(family, group, fraction):
                hits.append((f"{family}{group}/{subgroup}", signal.concept))
                break
    return hits

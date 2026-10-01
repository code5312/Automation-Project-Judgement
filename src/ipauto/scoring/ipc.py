"""IPC-code signal.

The exact IPC range for thermal management (design doc mentions H01M
10/60-10/667 as an unconfirmed starting point) is not verified against the
official IPC table yet; see docs/OPEN_QUESTIONS.md. Until confirmed, this
module only recognizes IPC *families* (configured in config/ipc_rules.yaml,
default H01M, B60L), which is a coarser and safer signal than a specific
subrange.
"""

from __future__ import annotations

import re
from functools import cache

from ipauto.scoring import rules


@cache
def _family_pattern(code: str) -> re.Pattern[str]:
    return re.compile(rf"(?<![A-Z0-9]){code}(?=\d|/|$)")


def detected_families(ipc_value: str) -> list[str]:
    """Return which configured IPC families appear in a raw IPC field value."""
    compact = re.sub(r"\s+", "", ipc_value.upper())
    return [code for code in rules.get_ipc_rules().families if _family_pattern(code).search(compact)]

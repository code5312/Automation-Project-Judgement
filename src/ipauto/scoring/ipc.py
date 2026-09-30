"""IPC-code signal.

The exact IPC range for thermal management (design doc mentions H01M
10/60-10/667 as an unconfirmed starting point) is not verified against the
official IPC table yet; see docs/OPEN_QUESTIONS.md. Until confirmed, this
module only recognizes IPC *families* (H01M, B60L), which is a coarser and
safer signal than a specific subrange.
"""

from __future__ import annotations

import re

# Family codes this MVP currently understands. Moving this to
# config/ipc_rules.yaml is phase 2 work.
IPC_FAMILIES = ("H01M", "B60L")

_FAMILY_PATTERN = {code: re.compile(rf"(?<![A-Z0-9]){code}(?=\d|/|$)") for code in IPC_FAMILIES}


def detected_families(ipc_value: str) -> list[str]:
    """Return which configured IPC families appear in a raw IPC field value."""
    compact = re.sub(r"\s+", "", ipc_value.upper())
    return [code for code in IPC_FAMILIES if _FAMILY_PATTERN[code].search(compact)]

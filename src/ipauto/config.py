"""Environment configuration and secret masking.

The KIPRIS access key must only ever be read from the environment. Nothing in
this module prints, logs, or returns the raw key; callers that need it for a
request must read it themselves and pass it through ``mask_secret`` before it
touches any log line, UI message, or exception text.
"""

from __future__ import annotations

import os
import re
import urllib.parse

KIPRIS_ACCESS_KEY_ENV = "KIPRIS_ACCESS_KEY"

# HTTPS support is unconfirmed for the KIPRIS Plus endpoint (see
# docs/OPEN_QUESTIONS.md). The base URL is a setting, not a hardcoded
# assumption, so it can be flipped to https:// once confirmed without a code
# change.
DEFAULT_KIPRIS_BASE_URL = "http://plus.kipris.or.kr/openapi/rest/patUtiModInfoSearchSevice/freeSearchInfo"
KIPRIS_BASE_URL_ENV = "KIPRIS_BASE_URL"

_ACCESS_KEY_PARAM_PATTERN = re.compile(r"(?i)(accessKey|serviceKey)(\s*[=:]\s*)[^&\s<>\"']+")


def get_kipris_access_key() -> str | None:
    """Read the KIPRIS access key from the environment only."""
    return os.getenv(KIPRIS_ACCESS_KEY_ENV) or None


def get_kipris_base_url() -> str:
    """Return the configured KIPRIS endpoint, defaulting to the known-working one."""
    return os.getenv(KIPRIS_BASE_URL_ENV, DEFAULT_KIPRIS_BASE_URL)


def mask_secret(text: str, secret: str | None) -> str:
    """Redact a secret from ``text``, including its URL-encoded form.

    Also redacts any ``accessKey=...`` / ``serviceKey=...`` parameter value as
    a fallback, so a key that reaches this function only through a query
    string is still caught even if the caller did not have the raw value on
    hand.
    """
    masked = text
    if secret:
        encoded = urllib.parse.quote(secret, safe="")
        for value in (secret, encoded):
            if value:
                masked = masked.replace(value, "[REDACTED]")
    return _ACCESS_KEY_PARAM_PATTERN.sub(r"\1\2[REDACTED]", masked)

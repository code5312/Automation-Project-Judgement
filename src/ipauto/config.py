"""Environment configuration and secret masking.

The KIPRIS access key and LLM API key must only ever be read from the
environment. Nothing in this module prints, logs, or returns a raw key;
callers that need one for a request must read it themselves and pass it
through ``mask_secret`` before it touches any log line, UI message, or
exception text (docs/PIPELINE.md 단계 3 블로커: LLM 사용 정책 — 외부 API
호출은 허용하되 접근키는 기존 KIPRIS 컨벤션대로 마스킹한다).
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

ANTHROPIC_API_KEY_ENV = "ANTHROPIC_API_KEY"

_ACCESS_KEY_PARAM_PATTERN = re.compile(r"(?i)(accessKey|serviceKey)(\s*[=:]\s*)[^&\s<>\"']+")


def get_kipris_access_key() -> str | None:
    """Read the KIPRIS access key from the environment only."""
    return os.getenv(KIPRIS_ACCESS_KEY_ENV) or None


def get_llm_api_key() -> str | None:
    """Read the Anthropic API key from the environment only."""
    return os.getenv(ANTHROPIC_API_KEY_ENV) or None


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

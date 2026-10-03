"""Anthropic Messages API connector (docs/DESIGN.md LLM 구조화 판정, 단계 3).

Calls Claude directly via stdlib ``urllib`` over HTTPS — same no-extra-HTTP
-dependency convention as ``connectors/kipris.py`` and ``connectors/github.py``,
not the ``anthropic`` SDK. The API key is read from the environment by the
caller (``ipauto.config.get_llm_api_key``) and must be masked with
``ipauto.config.mask_secret`` before it touches any log line or exception
text, same convention as ``KIPRIS_ACCESS_KEY`` (docs/PIPELINE.md 단계 3
블로커: LLM 사용 정책 — 외부 API 호출 허용).

This module only sends one message and returns Claude's raw text reply; it
has no opinion about prompt content or response format — that is
``ipauto.triage.llm_classifier``'s job.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request

_API_URL = "https://api.anthropic.com/v1/messages"
_API_VERSION = "2023-06-01"
_USER_AGENT = "ipauto-llm-connector/0.1"

DEFAULT_MODEL = "claude-haiku-4-5-20251001"
DEFAULT_MAX_TOKENS = 1024


class LLMError(Exception):
    """Base class for all LLM connector failures."""


class LLMAuthError(LLMError):
    """The API key was rejected (HTTP 401/403)."""


class LLMRateLimitError(LLMError):
    """The call was throttled or the quota was exhausted (HTTP 429)."""


class LLMNetworkError(LLMError):
    """The request could not reach the API, or it timed out."""


class LLMResponseError(LLMError):
    """The API returned an error payload, or the response shape was unexpected."""


def parse_message_response(body: bytes) -> str:
    """Parse a raw Messages API JSON body into its concatenated text reply.

    Exposed separately from ``complete`` so the response shape can be unit
    tested without a real network call, same pattern as
    ``connectors/kipris.py``'s ``parse_response``.
    """
    try:
        data = json.loads(body)
    except json.JSONDecodeError as exc:
        raise LLMResponseError("LLM API response is not valid JSON.") from exc

    try:
        text_parts = [block["text"] for block in data["content"] if block.get("type") == "text"]
    except (KeyError, TypeError) as exc:
        raise LLMResponseError(f"Unexpected LLM API response shape: {data!r}") from exc

    if not text_parts:
        raise LLMResponseError("LLM API response had no text content.")

    return "".join(text_parts)


def complete(
    prompt: str,
    *,
    api_key: str,
    system: str | None = None,
    model: str = DEFAULT_MODEL,
    max_tokens: int = DEFAULT_MAX_TOKENS,
) -> str:
    """Send one user message to Claude and return its concatenated text reply.

    Raises a typed LLMError on any failure. Does not retry.
    """
    if not api_key:
        raise ValueError("LLM API key is required.")

    payload: dict = {
        "model": model,
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": prompt}],
    }
    if system is not None:
        payload["system"] = system

    request = urllib.request.Request(
        _API_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "User-Agent": _USER_AGENT,
            "Content-Type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": _API_VERSION,
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            body = response.read()
    except urllib.error.HTTPError as exc:
        if exc.code in (401, 403):
            raise LLMAuthError(f"LLM API rejected the access key (HTTP {exc.code}).") from exc
        if exc.code == 429:
            raise LLMRateLimitError("LLM API quota exceeded or request throttled (HTTP 429).") from exc
        raise LLMError(f"LLM API returned HTTP {exc.code}.") from exc
    except TimeoutError as exc:
        raise LLMNetworkError("LLM API request timed out.") from exc
    except urllib.error.URLError as exc:
        raise LLMNetworkError(f"Could not connect to LLM API: {exc.reason}") from exc

    return parse_message_response(body)

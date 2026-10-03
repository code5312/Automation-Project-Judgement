"""Tests for the Anthropic Messages API connector (docs/PIPELINE.md 단계 3).

No real network calls or real API keys here — ``parse_message_response``
is pure and testable offline, same pattern as connectors/kipris.py's
``parse_response``.
"""

from __future__ import annotations

import json

import pytest

from ipauto.connectors.llm import LLMResponseError, parse_message_response


def _body(payload: dict) -> bytes:
    return json.dumps(payload).encode("utf-8")


def test_parse_message_response_concatenates_text_blocks():
    body = _body({"content": [{"type": "text", "text": "안녕"}, {"type": "text", "text": "하세요"}]})

    assert parse_message_response(body) == "안녕하세요"


def test_parse_message_response_ignores_non_text_blocks():
    body = _body({"content": [{"type": "tool_use", "text": "무시"}, {"type": "text", "text": "응답"}]})

    assert parse_message_response(body) == "응답"


def test_parse_message_response_rejects_invalid_json():
    with pytest.raises(LLMResponseError):
        parse_message_response(b"not json")


def test_parse_message_response_rejects_unexpected_shape():
    with pytest.raises(LLMResponseError):
        parse_message_response(_body({"unexpected": "shape"}))


def test_parse_message_response_rejects_no_text_content():
    with pytest.raises(LLMResponseError):
        parse_message_response(_body({"content": [{"type": "tool_use"}]}))

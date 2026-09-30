"""Tests for access-key masking, including URL-encoded and query-param forms."""

from __future__ import annotations

from ipauto.config import mask_secret


def test_mask_secret_redacts_raw_value():
    assert mask_secret("key=abc123&word=battery", "abc123") == "key=[REDACTED]&word=battery"


def test_mask_secret_redacts_url_encoded_value():
    secret = "abc/123+xyz"
    text = f"url?accessKey={secret.replace('/', '%2F').replace('+', '%2B')}"
    masked = mask_secret(text, secret)
    assert secret not in masked
    assert "%2F" not in masked


def test_mask_secret_redacts_access_key_param_even_without_the_raw_secret():
    text = "Could not connect: url?accessKey=unknownvalue&docsCount=20"
    masked = mask_secret(text, secret=None)
    assert "unknownvalue" not in masked
    assert "[REDACTED]" in masked


def test_mask_secret_leaves_unrelated_text_untouched():
    assert mask_secret("no secret here", "abc123") == "no secret here"

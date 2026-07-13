"""Versioned output formatters shared with Daily Problems PR #69.

The server stores only a hash, so the meaning of each identifier must stay
stable.  These functions deliberately mirror ``static/output-formatter.js``.
"""
from __future__ import annotations

import re


OUTPUT_FORMATTERS = (
    "identity-v1",
    "newlines-v1",
    "tokens-v1",
    "tokens-case-insensitive-v1",
    "yesno-v1",
)

_ASCII_WHITESPACE = re.compile(r"[ \t\n\r\f\v]+")
_JS_TRIM_CHARS = "\u0009\u000a\u000b\u000c\u000d\u0020\u00a0\u1680\u2000\u2001\u2002\u2003\u2004\u2005\u2006\u2007\u2008\u2009\u200a\u2028\u2029\u202f\u205f\u3000\ufeff"


def _tokens(value: str) -> list[str]:
    """Match JavaScript's ``value.trim().split(/[ \\t\\n\\r\\f\\v]+/)``."""
    value = value.strip(_JS_TRIM_CHARS)
    return _ASCII_WHITESPACE.split(value) if value else []


def format_output_for_hash(content: bytes, formatter: str) -> bytes:
    """Return bytes to hash after applying a supported output formatter.

    Non-identity formatters require valid UTF-8 just as the browser's fatal
    ``TextDecoder`` does.
    """
    if formatter == "identity-v1":
        return content
    if formatter not in OUTPUT_FORMATTERS:
        raise ValueError(f"未対応の出力フォーマッタです: {formatter}")

    value = content.decode("utf-8")
    if formatter == "newlines-v1":
        return re.sub(r"\r\n|\r", "\n", value).encode()

    tokens = _tokens(value)
    if formatter == "tokens-v1":
        return " ".join(tokens).encode()
    if formatter == "tokens-case-insensitive-v1":
        return " ".join(tokens).lower().encode()
    if any(token.lower() not in {"yes", "no"} for token in tokens):
        raise ValueError("yesno-v1 では Yes / No 以外のトークンは使えません。")
    return " ".join(token.lower() for token in tokens).encode()

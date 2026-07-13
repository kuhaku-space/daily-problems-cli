"""Parity tests for the browser output formatters introduced in PR #69."""
from __future__ import annotations

import pytest

from daily_problems_cli.output_formatters import format_output_for_hash


@pytest.mark.parametrize(
    ("formatter", "source", "expected"),
    [
        ("identity-v1", b" A\r\nB ", b" A\r\nB "),
        ("newlines-v1", b"A\rB\r\nC\n", b"A\nB\nC\n"),
        ("tokens-v1", b"\xc2\xa0 A\tB\r\nC \xe3\x80\x80", b"A B C"),
        ("tokens-case-insensitive-v1", b" A\tBeTa\n", b"a beta"),
        ("yesno-v1", b" YES\r\nno ", b"yes no"),
    ],
)
def test_format_output_for_hash_matches_browser(formatter, source, expected):
    assert format_output_for_hash(source, formatter) == expected


def test_yesno_rejects_other_tokens():
    with pytest.raises(ValueError, match="Yes / No"):
        format_output_for_hash(b"maybe", "yesno-v1")


def test_text_formatter_requires_utf8():
    with pytest.raises(UnicodeDecodeError):
        format_output_for_hash(b"\xff", "tokens-v1")

# tests/test_tui_highlight.py
from __future__ import annotations

from rich.text import Text

from toolchain.tui.highlight import highlight_match


def test_empty_needle_returns_the_plain_string_unchanged():
    result = highlight_match("tail/44", "")
    assert result == "tail/44"
    assert not isinstance(result, Text)


def test_a_match_is_styled_at_its_exact_position():
    result = highlight_match("tail/44", "44")
    assert isinstance(result, Text)
    assert result.plain == "tail/44"
    assert len(result.spans) == 1
    span = result.spans[0]
    assert (span.start, span.end, span.style) == (5, 7, "bold reverse")


def test_matching_is_case_insensitive():
    result = highlight_match("Nmap", "nmap")
    assert isinstance(result, Text)
    span = result.spans[0]
    assert (span.start, span.end) == (0, 4)


def test_every_occurrence_is_styled_not_just_the_first():
    result = highlight_match("tail/tail/42", "tail")
    assert len(result.spans) == 2
    assert (result.spans[0].start, result.spans[0].end) == (0, 4)
    assert (result.spans[1].start, result.spans[1].end) == (5, 9)


def test_no_match_returns_text_with_no_spans():
    result = highlight_match("tail/44", "zzz")
    assert isinstance(result, Text)
    assert result.spans == []

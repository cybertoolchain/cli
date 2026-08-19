# src/toolchain/tui/highlight.py
from __future__ import annotations

from rich.text import Text


def highlight_match(value: str, needle: str) -> Text | str:
    """Returns `value` with every case-insensitive occurrence of `needle`
    styled, so a filter match is visible in the surviving rows instead of
    only being inferable from the fact that they survived. Plain `value` is
    returned unchanged when there's nothing to search for."""
    if not needle:
        return value
    text = Text(value)
    lower = value.lower()
    start = 0
    while (idx := lower.find(needle, start)) != -1:
        text.stylize("bold reverse", idx, idx + len(needle))
        start = idx + len(needle)
    return text

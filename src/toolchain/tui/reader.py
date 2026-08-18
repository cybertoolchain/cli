# src/toolchain/tui/reader.py
from __future__ import annotations

from io import StringIO
from typing import Any

from rich.console import Console
from rich.markdown import Markdown


def _to_markdown(entries: list[dict[str, Any]]) -> str:
    if not entries:
        return "_No entries._\n"
    lines: list[str] = []
    for entry in entries:
        lines.append(f"## {entry.get('tool', 'Unknown tool')}")
        if entry.get("version"):
            lines.append(f"*{entry['version']}*")
        lines.append("")
        if entry.get("summary"):
            lines.append(entry["summary"])
            lines.append("")
        for bullet in entry.get("feature_bullets", []):
            lines.append(f"- {bullet}")
        if entry.get("feature_bullets"):
            lines.append("")
        for example in entry.get("usage_examples", []):
            if example.get("description"):
                lines.append(example["description"])
            lines.append("```shell")
            lines.append(example.get("command", ""))
            lines.append("```")
            lines.append("")
        if entry.get("url"):
            lines.append(f"[{entry['url']}]({entry['url']})")
        lines.append("")
    return "\n".join(lines)


def render_issue(entries: list[dict[str, Any]]) -> str:
    """Renders a list of issue entries (the same shape `issues get` emits)
    as syntax-highlighted, formatted text suitable for a terminal or a
    pager. Pure function — no I/O, so it's testable without a real
    terminal."""
    markdown_text = _to_markdown(entries)
    buffer = StringIO()
    console = Console(file=buffer, force_terminal=True, width=100)
    console.print(Markdown(markdown_text))
    return buffer.getvalue()

# tests/test_tui_reader.py
from __future__ import annotations

import re

from toolchain.tui.reader import render_issue

_ANSI = re.compile(r"\x1b\[[0-9;]*[a-zA-Z]")


def _strip_ansi(text: str) -> str:
    return _ANSI.sub("", text)


ENTRIES = [
    {
        "tool": "Nmap",
        "category": "reconnaissance",
        "version": "commits-2026-07-11",
        "url": "https://github.com/nmap/nmap/compare/49a85f9c3c11...115af39aacf9",
        "summary": "Nmap gains TLS close_notify tolerance and signal propagation with `-k`.",
        "feature_bullets": ["Adds `-k` signal propagation."],
        "usage_examples": [
            {
                "description": "Bind an interface and source address.",
                "command": "nmap -e eth1 -S 192.168.1.50 <target>",
                "language": "",
                "kind": "shell",
            }
        ],
    }
]


def test_render_issue_includes_tool_name():
    assert "Nmap" in render_issue(ENTRIES)


def test_render_issue_includes_summary():
    assert "TLS close_notify tolerance" in render_issue(ENTRIES)


def test_render_issue_includes_feature_bullets():
    assert "signal propagation" in render_issue(ENTRIES)


def test_render_issue_includes_the_command_example():
    # Rich syntax-highlights a ```shell fence token-by-token, inserting ANSI
    # escapes BETWEEN tokens — so the raw rendered string never contains the
    # command as one contiguous substring even though it's all there and
    # correctly highlighted. Strip ANSI escapes before asserting, rather
    # than dropping the shell lexer (which would silently turn off exactly
    # the highlighting this reader exists to provide).
    plain = _strip_ansi(render_issue(ENTRIES))
    assert "nmap -e eth1 -S 192.168.1.50" in plain


def test_render_issue_handles_empty_list():
    assert render_issue([]) == "" or "no entries" in render_issue([]).lower()


def test_render_issue_handles_missing_optional_fields():
    minimal = [{"tool": "Falco", "summary": "Falco shipped something."}]
    out = render_issue(minimal)
    assert "Falco" in out
    assert "Falco shipped something." in out

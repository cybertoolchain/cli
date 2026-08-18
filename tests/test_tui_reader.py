# tests/test_tui_reader.py
from __future__ import annotations

from toolchain.tui.reader import render_issue

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
    assert "nmap -e eth1 -S 192.168.1.50" in render_issue(ENTRIES)


def test_render_issue_handles_empty_list():
    assert render_issue([]) == "" or "no entries" in render_issue([]).lower()


def test_render_issue_handles_missing_optional_fields():
    minimal = [{"tool": "Falco", "summary": "Falco shipped something."}]
    out = render_issue(minimal)
    assert "Falco" in out
    assert "Falco shipped something." in out

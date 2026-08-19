# tests/test_tui_issues_browse.py
from __future__ import annotations

import pytest

from toolchain.tui.issues_browse import IssueBrowserApp

ISSUES = [
    {"issue_slug": "tail/44", "published_at": "2026-08-10", "tools": ["Nmap"]},
    {"issue_slug": "tail/42", "published_at": "2026-08-08", "tools": ["Zeek"]},
    {"issue_slug": "head/12", "published_at": "2026-08-07", "tools": ["Falco"]},
]


def _entries_fetcher(slug: str) -> list[dict]:
    return [{"tool": "Nmap", "summary": "did a thing", "issue_slug": slug}]


@pytest.mark.asyncio
async def test_all_issues_listed_on_start():
    app = IssueBrowserApp(ISSUES, _entries_fetcher)
    async with app.run_test() as pilot:
        table = app.query_one("#issue-table")
        assert table.row_count == 3


@pytest.mark.asyncio
async def test_filter_narrows_the_list():
    app = IssueBrowserApp(ISSUES, _entries_fetcher)
    async with app.run_test() as pilot:
        await pilot.click("#filter")
        for char in "tail":
            await pilot.press(char)
        table = app.query_one("#issue-table")
        assert table.row_count == 2


@pytest.mark.asyncio
async def test_filter_highlights_the_matched_text():
    app = IssueBrowserApp(ISSUES, _entries_fetcher)
    async with app.run_test() as pilot:
        await pilot.click("#filter")
        for char in "44":
            await pilot.press(char)
        table = app.query_one("#issue-table")
        cell = table.get_cell_at((0, 0))
        assert cell.plain == "tail/44"
        assert any(span.style == "bold reverse" for span in cell.spans)

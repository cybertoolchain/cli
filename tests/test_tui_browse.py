# tests/test_tui_browse.py
from __future__ import annotations

import pytest

from toolchain.tui.browse import ToolBrowserApp

TOOLS = [
    {"tool": "Nmap", "category": "reconnaissance", "version": "commits-2026-07-11"},
    {"tool": "Falco", "category": "runtime-security", "version": "v0.40.0"},
    {"tool": "Trivy", "category": "container-security", "version": "v0.55.0"},
]


@pytest.mark.asyncio
async def test_all_tools_listed_on_start():
    app = ToolBrowserApp(TOOLS)
    async with app.run_test() as pilot:
        table = app.query_one("#tool-table")
        assert table.row_count == 3


@pytest.mark.asyncio
async def test_filter_narrows_the_list():
    app = ToolBrowserApp(TOOLS)
    async with app.run_test() as pilot:
        await pilot.click("#filter")
        for char in "falco":
            await pilot.press(char)
        table = app.query_one("#tool-table")
        assert table.row_count == 1


@pytest.mark.asyncio
async def test_filter_highlights_the_matched_text():
    app = ToolBrowserApp(TOOLS)
    async with app.run_test() as pilot:
        await pilot.click("#filter")
        for char in "falco":
            await pilot.press(char)
        table = app.query_one("#tool-table")
        cell = table.get_cell_at((0, 0))
        assert cell.plain == "Falco"
        assert any(span.style == "bold reverse" for span in cell.spans)


@pytest.mark.asyncio
async def test_selecting_a_row_sets_selected_tool():
    app = ToolBrowserApp(TOOLS)
    async with app.run_test() as pilot:
        table = app.query_one("#tool-table")
        table.focus()
        await pilot.press("enter")
        assert app.selected_tool == TOOLS[0]
        assert app.return_value == TOOLS[0]

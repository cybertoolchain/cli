# src/toolchain/tui/browse.py
from __future__ import annotations

from typing import Any

from textual.app import App, ComposeResult
from textual.containers import Vertical
from textual.widgets import DataTable, Footer, Header, Input

from .highlight import highlight_match


class ToolBrowserApp(App):
    """Fuzzy search + select over the tools list. Returns the selected
    tool's raw record when the app exits (Enter on a row, or 'q'/Ctrl+C
    to cancel with no selection). Filter with '/', navigate with the
    arrow keys or vim's j/k."""

    CSS = """
    #filter { dock: top; }
    #tool-table { height: 1fr; }
    """
    BINDINGS = [
        ("q", "quit", "Quit"),
        ("ctrl+c", "quit", "Quit"),
        ("/", "focus_filter", "Search"),
        ("escape", "focus_table", "Back to list"),
        ("j", "table_cursor_down", "Down"),
        ("k", "table_cursor_up", "Up"),
    ]

    def __init__(self, tools: list[dict[str, Any]]) -> None:
        super().__init__()
        self._all_tools = tools
        self._visible_rows: list[dict[str, Any]] = []
        self.selected_tool: dict[str, Any] | None = None

    def compose(self) -> ComposeResult:
        yield Header()
        yield Vertical(
            Input(placeholder="Filter tools… ('/' to search)", id="filter"),
            DataTable(id="tool-table", cursor_type="row"),
        )
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#tool-table", DataTable)
        table.add_columns("tool", "category", "version")
        self._render_rows(self._all_tools)
        table.focus()

    def _render_rows(self, rows: list[dict[str, Any]], needle: str = "") -> None:
        table = self.query_one("#tool-table", DataTable)
        table.clear()
        for row in rows:
            table.add_row(
                highlight_match(row.get("tool", ""), needle),
                row.get("category", ""),
                row.get("version", ""),
            )
        self._visible_rows = rows

    def on_input_changed(self, event: Input.Changed) -> None:
        needle = event.value.lower()
        filtered = [
            row for row in self._all_tools if needle in str(row.get("tool", "")).lower()
        ]
        self._render_rows(filtered, needle)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self.query_one("#tool-table", DataTable).focus()

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        self._select_current_row()

    def _select_current_row(self) -> None:
        table = self.query_one("#tool-table", DataTable)
        if not self._visible_rows or table.cursor_row is None:
            return
        self.selected_tool = self._visible_rows[table.cursor_row]
        self.exit(self.selected_tool)

    def action_focus_filter(self) -> None:
        self.query_one("#filter", Input).focus()

    def action_focus_table(self) -> None:
        self.query_one("#tool-table", DataTable).focus()

    def action_table_cursor_up(self) -> None:
        self.query_one("#tool-table", DataTable).action_cursor_up()

    def action_table_cursor_down(self) -> None:
        self.query_one("#tool-table", DataTable).action_cursor_down()

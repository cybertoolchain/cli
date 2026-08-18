# src/toolchain/tui/browse.py
from __future__ import annotations

from typing import Any

from textual.app import App, ComposeResult
from textual.containers import Vertical
from textual.widgets import DataTable, Footer, Header, Input


class ToolBrowserApp(App):
    """Fuzzy search + select over the tools list. Returns the selected
    tool's raw record when the app exits (Enter on a row, or Ctrl+C to
    cancel with no selection)."""

    CSS = """
    #filter { dock: top; }
    #tool-table { height: 1fr; }
    """
    BINDINGS = [("ctrl+c", "quit", "Cancel")]

    def __init__(self, tools: list[dict[str, Any]]) -> None:
        super().__init__()
        self._all_tools = tools
        self._visible_rows: list[dict[str, Any]] = []
        self.selected_tool: dict[str, Any] | None = None

    def compose(self) -> ComposeResult:
        yield Header()
        yield Vertical(
            Input(placeholder="Filter tools…", id="filter"),
            DataTable(id="tool-table", cursor_type="row"),
        )
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#tool-table", DataTable)
        table.add_columns("tool", "category", "version")
        self._render_rows(self._all_tools)

    def _render_rows(self, rows: list[dict[str, Any]]) -> None:
        table = self.query_one("#tool-table", DataTable)
        table.clear()
        for row in rows:
            table.add_row(row.get("tool", ""), row.get("category", ""), row.get("version", ""))
        self._visible_rows = rows

    def on_input_changed(self, event: Input.Changed) -> None:
        needle = event.value.lower()
        filtered = [
            row for row in self._all_tools if needle in str(row.get("tool", "")).lower()
        ]
        self._render_rows(filtered)

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        self.selected_tool = self._visible_rows[event.cursor_row]
        self.exit(self.selected_tool)

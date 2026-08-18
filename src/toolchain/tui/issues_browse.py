# src/toolchain/tui/issues_browse.py
from __future__ import annotations

from typing import Any

from textual.app import App, ComposeResult
from textual.containers import Vertical
from textual.widgets import DataTable, Footer, Header, Input


class IssueBrowserApp(App):
    """Fuzzy search + select over the issue list. Returns the selected
    row's `issue_slug` when the app exits (Enter on a row, or Ctrl+C to
    cancel with no selection)."""

    CSS = """
    #filter { dock: top; }
    #issue-table { height: 1fr; }
    """
    BINDINGS = [("ctrl+c", "quit", "Cancel")]

    def __init__(self, issues: list[dict[str, Any]]) -> None:
        super().__init__()
        self._all_issues = issues
        self._visible_rows: list[dict[str, Any]] = []
        self.selected_issue: str | None = None

    def compose(self) -> ComposeResult:
        yield Header()
        yield Vertical(
            Input(placeholder="Filter issues…", id="filter"),
            DataTable(id="issue-table", cursor_type="row"),
        )
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#issue-table", DataTable)
        table.add_columns("issue", "tool", "published")
        self._render_rows(self._all_issues)

    def _render_rows(self, rows: list[dict[str, Any]]) -> None:
        table = self.query_one("#issue-table", DataTable)
        table.clear()
        for row in rows:
            table.add_row(
                row.get("issue_slug", ""), row.get("tool", ""), row.get("published_at", "")
            )
        self._visible_rows = rows

    def on_input_changed(self, event: Input.Changed) -> None:
        needle = event.value.lower()
        filtered = [
            row for row in self._all_issues if needle in str(row.get("issue_slug", "")).lower()
        ]
        self._render_rows(filtered)

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        row = self._visible_rows[event.cursor_row]
        self.selected_issue = row.get("issue_slug")
        self.exit(self.selected_issue)

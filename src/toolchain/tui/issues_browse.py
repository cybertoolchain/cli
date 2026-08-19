# src/toolchain/tui/issues_browse.py
from __future__ import annotations

from datetime import datetime
from typing import Any, Callable

from textual.app import App, ComposeResult
from textual.containers import Vertical
from textual.widgets import DataTable, Footer, Header, Input

from .highlight import highlight_match
from .issue_reader_screen import IssueReaderScreen


def _format_date(value: str) -> str:
    """Just the calendar date, no time-of-day or timezone offset — the
    full ISO timestamp is more precision than the browser needs."""
    if not value:
        return ""
    try:
        return datetime.fromisoformat(value).strftime("%b %d, %Y")
    except ValueError:
        return value


class IssueBrowserApp(App):
    """Browse issues, then read one in place. Filter with '/', navigate
    with the arrow keys or vim's h/j/k/l, Enter opens the highlighted
    issue in a scrollable in-app reader, 'q' (or Ctrl+C) quits."""

    CSS = """
    #filter { dock: top; }
    #issue-table { height: 1fr; }
    """
    BINDINGS = [
        ("q", "quit", "Quit"),
        ("ctrl+c", "quit", "Quit"),
        ("/", "focus_filter", "Search"),
        ("escape", "focus_table", "Back to list"),
        ("j", "table_cursor_down", "Down"),
        ("k", "table_cursor_up", "Up"),
    ]

    def __init__(
        self, issues: list[dict[str, Any]], entries_fetcher: Callable[[str], list[dict]]
    ) -> None:
        super().__init__()
        self._all_issues = issues
        self._entries_fetcher = entries_fetcher
        self._visible_rows: list[dict[str, Any]] = []

    def compose(self) -> ComposeResult:
        yield Header()
        yield Vertical(
            Input(placeholder="Filter issues… ('/' to search)", id="filter"),
            DataTable(id="issue-table", cursor_type="row"),
        )
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#issue-table", DataTable)
        table.add_columns("issue", "published", "tools")
        self._render_rows(self._all_issues)
        table.focus()

    def _render_rows(self, rows: list[dict[str, Any]], needle: str = "") -> None:
        table = self.query_one("#issue-table", DataTable)
        table.clear()
        for row in rows:
            table.add_row(
                highlight_match(row.get("issue_slug", ""), needle),
                _format_date(row.get("published_at", "")),
                ", ".join(row.get("tools", [])),
            )
        self._visible_rows = rows

    def on_input_changed(self, event: Input.Changed) -> None:
        needle = event.value.lower()
        filtered = [
            row for row in self._all_issues if needle in str(row.get("issue_slug", "")).lower()
        ]
        self._render_rows(filtered, needle)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self.query_one("#issue-table", DataTable).focus()

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        table = self.query_one("#issue-table", DataTable)
        if not self._visible_rows or table.cursor_row is None:
            return
        row = self._visible_rows[table.cursor_row]
        slug = row.get("issue_slug")
        if not slug:
            return
        entries = self._entries_fetcher(slug)
        self.push_screen(IssueReaderScreen(slug, entries))

    def action_focus_filter(self) -> None:
        self.query_one("#filter", Input).focus()

    def action_focus_table(self) -> None:
        self.query_one("#issue-table", DataTable).focus()

    def action_table_cursor_down(self) -> None:
        self.query_one("#issue-table", DataTable).action_cursor_down()

    def action_table_cursor_up(self) -> None:
        self.query_one("#issue-table", DataTable).action_cursor_up()

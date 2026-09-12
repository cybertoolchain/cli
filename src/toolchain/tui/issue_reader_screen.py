# src/toolchain/tui/issue_reader_screen.py
from __future__ import annotations

from io import BytesIO
from typing import Any

import httpx
from PIL import Image as PILImage
from textual.app import ComposeResult
from textual.containers import VerticalScroll
from textual.screen import Screen
from textual.widgets import Footer, Header, Input, Markdown, Static
from textual.widgets.markdown import MarkdownBlock
from textual_image.widget import Image as InlineImage

from ..versioning import default_headers
from .reader import issue_markdown

_IMAGE_FETCH_TIMEOUT = 10.0


def _image_media(entry: dict[str, Any]) -> list[dict[str, Any]]:
    return [item for item in entry.get("media", []) if item.get("type") == "image"]


class IssueReaderScreen(Screen):
    """Scrollable in-app reader for one issue's entries. Markdown widgets
    give syntax-highlighted code fences for free — the same rendering the
    website uses for command-line examples. Screenshots render inline via
    the terminal's own graphics protocol (Kitty/Sixel) where supported,
    with a Unicode fallback everywhere else; a fetch failure falls back
    to a plain link instead of breaking the reader."""

    CSS = """
    #search { dock: bottom; display: none; }
    #search.-visible { display: block; }
    #reader-scroll { height: 1fr; }
    .entry-image { height: auto; max-height: 30; margin: 1 2; }
    """
    BINDINGS = [
        ("q", "back", "Back"),
        ("escape", "back", "Back"),
        ("j", "scroll_down", "Down"),
        ("k", "scroll_up", "Up"),
        ("h", "scroll_left", "Left"),
        ("l", "scroll_right", "Right"),
        ("space", "page_down", "Page down"),
        ("ctrl+d", "page_down", "Page down"),
        ("/", "search", "Search"),
        ("n", "next_match", "Next match"),
        ("N", "prev_match", "Prev match"),
    ]

    def __init__(self, issue_slug: str, entries: list[dict[str, Any]]) -> None:
        super().__init__()
        self._issue_slug = issue_slug
        self._entries = entries or [{}]
        self._image_specs: list[tuple[str, str, str]] = []
        self._last_needle = ""
        self._match_index = -1

    def compose(self) -> ComposeResult:
        yield Header()
        with VerticalScroll(id="reader-scroll"):
            for i, entry in enumerate(self._entries):
                yield Markdown(issue_markdown([entry]), classes="entry-markdown")
                for j, media in enumerate(_image_media(entry)):
                    widget_id = f"media-{i}-{j}"
                    url = media.get("url", "")
                    alt = media.get("alt") or "screenshot"
                    if url:
                        self._image_specs.append((widget_id, url, alt))
                        yield InlineImage(id=widget_id, classes="entry-image")
        yield Input(placeholder="Search…", id="search")
        yield Footer()

    def on_mount(self) -> None:
        self.title = self._issue_slug
        self.query_one("#reader-scroll", VerticalScroll).focus()
        if self._image_specs:
            self.run_worker(self._load_images(), exclusive=False, group="images")

    async def _load_images(self) -> None:
        async with httpx.AsyncClient(
            timeout=_IMAGE_FETCH_TIMEOUT, follow_redirects=True, headers=default_headers()
        ) as client:
            for widget_id, url, alt in self._image_specs:
                try:
                    response = await client.get(url)
                    response.raise_for_status()
                    pil_image = PILImage.open(BytesIO(response.content))
                    pil_image.load()
                except Exception:
                    self._replace_with_link(widget_id, url, alt)
                    continue
                try:
                    widget = self.query_one(f"#{widget_id}", InlineImage)
                except Exception:
                    continue  # screen already closed
                widget.image = pil_image

    def _replace_with_link(self, widget_id: str, url: str, alt: str) -> None:
        try:
            widget = self.query_one(f"#{widget_id}", InlineImage)
        except Exception:
            return
        container = widget.parent
        if container is not None:
            container.mount(
                Static(f"{alt}: {url}", classes="entry-image-fallback", markup=False),
                after=widget,
            )
        widget.remove()

    def action_back(self) -> None:
        search = self.query_one("#search", Input)
        if search.has_focus:
            search.remove_class("-visible")
            self.query_one("#reader-scroll", VerticalScroll).focus()
            return
        self._release_images()
        self.app.pop_screen()

    def _release_images(self) -> None:
        """Kitty/Sixel graphics are drawn by the terminal itself, outside
        Textual's normal text compositing, so merely unmounting the widget
        leaves them on screen — the issue list underneath renders correctly
        but stays hidden behind stale image data. Clearing `.image` runs the
        widget's own terminal-delete sequence (see `Image.image` setter)
        before the screen is popped."""
        for widget_id, _url, _alt in self._image_specs:
            try:
                widget = self.query_one(f"#{widget_id}", InlineImage)
            except Exception:
                continue
            widget.image = None

    def action_scroll_down(self) -> None:
        self.query_one("#reader-scroll", VerticalScroll).scroll_down()

    def action_scroll_up(self) -> None:
        self.query_one("#reader-scroll", VerticalScroll).scroll_up()

    def action_scroll_left(self) -> None:
        self.query_one("#reader-scroll", VerticalScroll).scroll_left()

    def action_scroll_right(self) -> None:
        self.query_one("#reader-scroll", VerticalScroll).scroll_right()

    def action_page_down(self) -> None:
        self.query_one("#reader-scroll", VerticalScroll).scroll_page_down()

    def action_search(self) -> None:
        search = self.query_one("#search", Input)
        search.add_class("-visible")
        search.focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self._find_next(event.value)
        event.input.remove_class("-visible")
        self.query_one("#reader-scroll", VerticalScroll).focus()

    def action_next_match(self) -> None:
        self._jump_to_match(1)

    def action_prev_match(self) -> None:
        self._jump_to_match(-1)

    def _matches_for(self, needle: str) -> list[MarkdownBlock]:
        blocks = list(self.query_one("#reader-scroll", VerticalScroll).query(MarkdownBlock))
        needle_lower = needle.lower()
        return [b for b in blocks if needle_lower in (b.source or "").lower()]

    def _find_next(self, needle: str) -> None:
        if not needle:
            return
        matches = self._matches_for(needle)
        if not matches:
            return
        if needle != self._last_needle:
            self._last_needle = needle
            self._match_index = 0
        else:
            self._match_index = (self._match_index + 1) % len(matches)
        matches[self._match_index].scroll_visible(top=True)

    def _jump_to_match(self, delta: int) -> None:
        if not self._last_needle:
            return
        matches = self._matches_for(self._last_needle)
        if not matches:
            return
        self._match_index = (self._match_index + delta) % len(matches)
        matches[self._match_index].scroll_visible(top=True)

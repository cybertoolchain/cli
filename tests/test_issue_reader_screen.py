# tests/test_issue_reader_screen.py
from __future__ import annotations

import io

import httpx
import pytest
from PIL import Image as PILImage
from textual.app import App
from textual.widgets import Static
from textual_image.widget import Image as InlineImage

from toolchain.tui.issue_reader_screen import IssueReaderScreen, _image_media

ENTRIES = [
    {
        "tool": "Nmap",
        "summary": "Nmap gains a new flag.",
        "media": [{"type": "image", "url": "https://example.test/ok.png", "alt": "nmap ui"}],
    },
    {
        "tool": "Falco",
        "summary": "Falco adds a plugin.",
        "media": [
            {"type": "image", "url": "https://example.test/broken.png", "alt": "falco ui"},
            {"type": "video", "url": "https://example.test/demo.mp4"},
        ],
    },
]


def _png_bytes() -> bytes:
    buf = io.BytesIO()
    PILImage.new("RGB", (4, 4), color="red").save(buf, format="PNG")
    return buf.getvalue()


class _FakeResponse:
    def __init__(self, content: bytes, status: int = 200) -> None:
        self.content = content
        self.status_code = status

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("boom", request=None, response=self)


class _FakeAsyncClient:
    def __init__(self, *args, **kwargs) -> None:
        pass

    async def __aenter__(self) -> "_FakeAsyncClient":
        return self

    async def __aexit__(self, *args) -> bool:
        return False

    async def get(self, url: str) -> _FakeResponse:
        if "ok.png" in url:
            return _FakeResponse(_png_bytes())
        raise httpx.ConnectError("no route")


class _HostApp(App):
    def __init__(self, entries):
        super().__init__()
        self._entries = entries

    def on_mount(self) -> None:
        self.push_screen(IssueReaderScreen("tail/44", self._entries))


def test_image_media_filters_to_image_type_only():
    assert _image_media(ENTRIES[1]) == [
        {"type": "image", "url": "https://example.test/broken.png", "alt": "falco ui"}
    ]


def test_image_media_skips_entries_with_no_url():
    entry = {"media": [{"type": "image", "url": ""}]}
    assert _image_media(entry) == [{"type": "image", "url": ""}]  # filtered later by url check


@pytest.mark.asyncio
async def test_successful_fetch_sets_the_inline_image(monkeypatch):
    monkeypatch.setattr(httpx, "AsyncClient", _FakeAsyncClient)
    app = _HostApp(ENTRIES)
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause(0.3)
        widget = app.screen.query_one("#media-0-0", InlineImage)
        assert widget.image is not None


@pytest.mark.asyncio
async def test_failed_fetch_falls_back_to_a_plain_link(monkeypatch):
    monkeypatch.setattr(httpx, "AsyncClient", _FakeAsyncClient)
    app = _HostApp(ENTRIES)
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause(0.3)
        with pytest.raises(Exception):
            app.screen.query_one("#media-1-0", InlineImage)
        fallback = [
            w for w in app.screen.query(Static) if "entry-image-fallback" in w.classes
        ]
        assert len(fallback) == 1
        assert "falco ui: https://example.test/broken.png" in str(fallback[0].render())


@pytest.mark.asyncio
async def test_search_finds_a_match_in_a_later_entry(monkeypatch):
    monkeypatch.setattr(httpx, "AsyncClient", _FakeAsyncClient)
    app = _HostApp(ENTRIES)
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause(0.1)
        await pilot.press("slash")
        for ch in "plugin":
            await pilot.press(ch)
        await pilot.press("enter")
        assert app.screen._match_index == 0
        assert app.screen._last_needle == "plugin"


@pytest.mark.asyncio
async def test_q_pops_the_reader_back_to_the_list(monkeypatch):
    monkeypatch.setattr(httpx, "AsyncClient", _FakeAsyncClient)
    app = _HostApp(ENTRIES)
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause(0.1)
        assert len(app.screen_stack) == 2
        await pilot.press("q")
        await pilot.pause()
        assert len(app.screen_stack) == 1


@pytest.mark.asyncio
async def test_q_releases_loaded_images_before_popping(monkeypatch):
    # Kitty/Sixel graphics are drawn by the terminal itself, outside
    # Textual's normal compositing — a widget merely being unmounted
    # doesn't clear them, which is what left the issue list looking blank
    # after backing out of an entry with a screenshot. The widget's own
    # `.image` setter is what issues the terminal delete sequence, so
    # backing out must clear it rather than just popping the screen.
    monkeypatch.setattr(httpx, "AsyncClient", _FakeAsyncClient)
    app = _HostApp(ENTRIES)
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause(0.3)
        widget = app.screen.query_one("#media-0-0", InlineImage)
        assert widget.image is not None
        await pilot.press("q")
        await pilot.pause()
        assert widget.image is None

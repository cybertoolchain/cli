from __future__ import annotations

from ..helpers import tool_slug
from ..models import APIError, UserInputError


def published_entries(source, tool: str) -> list[dict]:
    """One tool's published entries from the free site — the rows
    `/entries.json` used to carry for every tool at once, now served per tool
    at `/tool-entries/<slug>.json` (the site stopped publishing the corpus in
    bulk). A tool with a page but nothing published is an empty list; a slug
    the site has no page for is a 404, which is the caller's typo."""
    slug = tool_slug(tool)
    try:
        return list(source.fetch(f"tool-entries/{slug}.json"))
    except APIError as exc:
        if str(exc).startswith("404 "):
            raise UserInputError(
                f"No tracked tool at '{tool}'. Run 'toolchain tools list' to see tracked tools."
            ) from exc
        raise


def newest_per_tool(source) -> list[dict]:
    """The newest release per tracked tool — the site's `/tools.json`, the
    only cross-tool release listing the free site still publishes."""
    payload = source.fetch("tools.json")
    return list(payload.get("tools", []) if isinstance(payload, dict) else payload)

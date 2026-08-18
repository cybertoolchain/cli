from __future__ import annotations

from collections import Counter

import click

from ..helpers import emit, get_config, handle_errors
from ..source import resolve_source


@click.group()
def categories() -> None:
    """The taxonomy every category filter on the site already uses."""


@categories.command("list")
@click.pass_context
@handle_errors
def categories_list(ctx: click.Context) -> None:
    """Every category, with a live tool count."""
    config = get_config(ctx)
    source = resolve_source(config)
    if config.api_key:
        data = source.fetch("categories")
    else:
        site_data = source.fetch("tools.json")
        counts = Counter(row.get("category", "uncategorized") for row in site_data["tools"])
        data = [{"category": slug, "count": count} for slug, count in sorted(counts.items())]
    emit(data, config)

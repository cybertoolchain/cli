from __future__ import annotations

import click

from ..helpers import emit, get_config, handle_errors
from ..source import resolve_source


@click.group()
def releases() -> None:
    """Every release across the watchlist in one feed — what Tail sends,
    queryable instead of mailed."""


@releases.command("list")
@click.option("--tools", "tools_", default=None, help="Comma-separated slugs.")
@click.option("--categories", default=None, help="Comma-separated taxonomy slugs.")
@click.option("--since", default=None)
@click.option("--until", default=None)
@click.option("--limit", "list_limit", type=int, default=None)
@click.pass_context
@handle_errors
def releases_list(ctx: click.Context, tools_, categories, since, until, list_limit) -> None:
    """Filterable across the whole watchlist, not just one tool."""
    config = get_config(ctx)
    source = resolve_source(config)
    if config.api_key:
        params = {
            k: v
            for k, v in {
                "tools": tools_,
                "categories": categories,
                "since": since,
                "until": until,
                "limit": list_limit,
            }.items()
            if v is not None
        }
        data = source.fetch("releases", **params)
    else:
        entries = source.fetch("entries.json")
        data = entries
        if tools_:
            wanted = {t.strip().lower() for t in tools_.split(",")}
            data = [row for row in data if row.get("name") in wanted]
        if categories:
            wanted_cats = {c.strip().lower() for c in categories.split(",")}
            data = [row for row in data if row.get("category", "").lower() in wanted_cats]
        if since:
            data = [row for row in data if row.get("published_at", "") >= since]
        if until:
            data = [row for row in data if row.get("published_at", "") <= until]
        if list_limit is not None:
            data = data[:list_limit]
    emit(data, config)


@releases.command("latest")
@click.option("--limit", "releases_limit", type=int, default=20)
@click.pass_context
@handle_errors
def releases_latest(ctx: click.Context, releases_limit: int) -> None:
    """Newest releases across the whole watchlist, no filters — the CLI
    equivalent of the Tail newsletter feed."""
    config = get_config(ctx)
    source = resolve_source(config)
    if config.api_key:
        data = source.fetch("releases", limit=releases_limit)
    else:
        entries = source.fetch("entries.json")
        data = sorted(entries, key=lambda row: row.get("published_at", ""), reverse=True)[:releases_limit]
    emit(data, config)

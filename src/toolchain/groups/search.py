from __future__ import annotations

import click

from ..helpers import emit, get_config, handle_errors
from ..source import resolve_source


@click.command("search")
@click.argument("query")
@click.option("--type", "type_", default=None, type=click.Choice(["tool", "release"]))
@click.pass_context
@handle_errors
def search(ctx: click.Context, query: str, type_) -> None:
    """Full-text over tool names, vendors, and release summaries. Use the
    GLOBAL -l/--limit (before the subcommand) to change the default of 20
    — there is no separate --limit here."""
    config = get_config(ctx)
    limit = config.limit if config.limit is not None else 20
    source = resolve_source(config)
    if config.api_key:
        params = {"q": query, "limit": limit}
        if type_:
            params["type"] = type_
        data = source.fetch("search", **params)
    else:
        index = source.fetch("search-index.json")
        needle = query.lower()
        data = [row for row in index if needle in row.get("keywords", "").lower()]
        if type_:
            wanted = "tool" if type_ == "tool" else "issue"
            data = [row for row in data if row.get("type") == wanted]
        data = data[:limit]
    emit(data, config)

# src/toolchain/groups/tools.py
from __future__ import annotations

import click

from ..helpers import emit, get_config, handle_errors
from ..models import UserInputError
from ..source import resolve_source


@click.group()
def tools() -> None:
    """The watchlist itself — what's tracked, what each tool is, and what
    it has shipped."""


def _slug_of(tool_row: dict) -> str:
    return str(tool_row.get("tool", "")).lower().replace(" ", "-")


@tools.command("list")
@click.option("--category", default=None)
@click.option("--license", "license_", default=None, type=click.Choice(["open-source", "commercial"]))
@click.option("--tool_type", default=None)
@click.option("--q", default=None)
@click.option("--cursor", default=None)
@click.pass_context
@handle_errors
def tools_list(ctx: click.Context, category, license_, tool_type, q, cursor) -> None:
    """Every tracked tool. No key: the current watchlist snapshot from the
    site. With a key: live, server-side filtered and paginated."""
    config = get_config(ctx)
    source = resolve_source(config)
    params = {
        k: v
        for k, v in {
            "category": category,
            "license": license_,
            "tool_type": tool_type,
            "q": q,
            "cursor": cursor,
        }.items()
        if v is not None
    }
    path = "tools" if config.api_key else "tools.json"
    data = source.fetch(path, **params)
    emit(data, config)


@tools.command("count")
@click.option("--category", default=None)
@click.option("--license", "license_", default=None, type=click.Choice(["open-source", "commercial"]))
@click.option("--tool_type", default=None)
@click.pass_context
@handle_errors
def tools_count(ctx: click.Context, category, license_, tool_type) -> None:
    """Just the number — requires an API key (there is no site-JSON count
    endpoint; count it yourself from `tools list` if you have no key)."""
    config = get_config(ctx)
    if not config.api_key:
        raise UserInputError(
            "tools count requires an API key — get one at "
            f"{config.site.site_base}/account (any plan)."
        )
    source = resolve_source(config)
    params = {
        k: v
        for k, v in {"category": category, "license": license_, "tool_type": tool_type}.items()
        if v is not None
    }
    data = source.fetch("tools/count", **params)
    emit(data, config)


@tools.command("get")
@click.argument("slug")
@click.pass_context
@handle_errors
def tools_get(ctx: click.Context, slug: str) -> None:
    """One tool in full, including its most recent release."""
    config = get_config(ctx)
    source = resolve_source(config)
    if config.api_key:
        data = source.fetch(f"tools/{slug}")
    else:
        site_data = source.fetch("tools.json")
        match = next(
            (row for row in site_data["tools"] if _slug_of(row) == slug.lower()), None
        )
        if match is None:
            raise UserInputError(
                f"No tracked tool matches '{slug}'. Run 'toolchain tools list' to see slugs."
            )
        data = match
    emit(data, config)

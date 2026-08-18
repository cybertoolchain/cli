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


@tools.command("releases")
@click.argument("slug")
@click.option("--since", default=None)
@click.option("--until", default=None)
@click.pass_context
@handle_errors
def tools_releases(ctx: click.Context, slug: str, since, until) -> None:
    """One tool's release history."""
    config = get_config(ctx)
    source = resolve_source(config)
    if config.api_key:
        params = {
            k: v
            for k, v in {"since": since, "until": until, "limit": config.limit}.items()
            if v is not None
        }
        data = source.fetch(f"tools/{slug}/releases", **params)
    else:
        entries = source.fetch("entries.json")
        data = [row for row in entries if row.get("name") == slug.lower()]
        if config.limit is not None:
            data = data[: config.limit]
    emit(data, config)


@tools.command("api")
@click.argument("slug")
@click.pass_context
@handle_errors
def tools_api(ctx: click.Context, slug: str) -> None:
    """The tool's own API surface: capability areas and endpoint count on
    any key or none; full per-endpoint detail on a Researcher+ key."""
    config = get_config(ctx)
    source = resolve_source(config)
    if config.api_key:
        data = source.fetch(f"tools/{slug}/api")
    else:
        apis = source.fetch("tool-apis.json")
        match = next((v for k, v in apis.items() if k.lower() == slug.lower()), None)
        if match is None:
            raise UserInputError(f"'{slug}' has no published API in the watchlist.")
        data = match
    emit(data, config)


@tools.command("examples")
@click.argument("slug")
@click.pass_context
@handle_errors
def tools_examples(ctx: click.Context, slug: str) -> None:
    """Captured command-line examples. No key: the written explanation of
    what each captured run did. With a key: the full command and its real
    output too."""
    config = get_config(ctx)
    source = resolve_source(config)
    if config.api_key:
        data = source.fetch(f"tools/{slug}/cli")
    else:
        explains = source.fetch("cli-explains.json")
        match = next((v for k, v in explains.items() if k.lower() == slug.lower()), None)
        if match is None:
            raise UserInputError(f"No captured CLI examples for '{slug}' yet.")
        data = match
    emit(data, config)


@tools.command("stack")
@click.argument("slug")
@click.pass_context
@handle_errors
def tools_stack(ctx: click.Context, slug: str) -> None:
    """Language mix, dependencies, and AI-attribution stats. Free with no
    key, from the published watchlist snapshot; live and per-request with
    a key."""
    config = get_config(ctx)
    source = resolve_source(config)
    if config.api_key:
        data = source.fetch(f"tools/{slug}/stack")
    else:
        code = source.fetch("toolCode.json")
        match = next((v for k, v in code.items() if k.lower() == slug.lower()), None)
        if match is None:
            raise UserInputError(f"No code/stack analysis published for '{slug}'.")
        data = match
    emit(data, config)


@tools.command("sbom")
@click.argument("slug")
@click.pass_context
@handle_errors
def tools_sbom(ctx: click.Context, slug: str) -> None:
    """The tool's software bill of materials. requires an API key — there
    is no free equivalent published on the site."""
    config = get_config(ctx)
    if not config.api_key:
        raise UserInputError(
            "tools sbom requires an API key — get one at "
            f"{config.site.site_base}/account (Researcher plan or higher)."
        )
    source = resolve_source(config)
    data = source.fetch(f"tools/{slug}/sbom")
    emit(data, config)


@tools.command("browse")
@click.pass_context
@handle_errors
def tools_browse(ctx: click.Context) -> None:
    """Interactively search and select from the tools list. Human-only —
    does not go through -o/--output."""
    from ..tui.browse import ToolBrowserApp

    config = get_config(ctx)
    source = resolve_source(config)
    path = "tools" if config.api_key else "tools.json"
    data = source.fetch(path)
    rows = data.get("tools", data if isinstance(data, list) else [])
    app = ToolBrowserApp(rows)
    selected = app.run()
    if selected is not None:
        click.echo(f"{selected.get('tool')}: {selected.get('url', selected.get('docs_url', ''))}")

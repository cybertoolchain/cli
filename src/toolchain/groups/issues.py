from __future__ import annotations

import click

from ..helpers import emit, get_config, handle_errors
from ..models import UserInputError
from ..source import resolve_source


@click.group()
def issues() -> None:
    """The published archive — daily, highlights, and docs-weekly."""


@issues.command("list")
@click.option("--series", default=None, type=click.Choice(["tail", "head", "diff"]))
@click.pass_context
@handle_errors
def issues_list(ctx: click.Context, series) -> None:
    """The issue index. No key: every entry that has run in a public
    issue, grouped by issue — narrower than the full archive (no
    paywalled entries, no assimilated summary block). With a key: the
    real issue index. Use the GLOBAL -l/--limit (before the subcommand)
    to cap how many come back — there is no separate --limit here."""
    config = get_config(ctx)
    source = resolve_source(config)
    if config.api_key:
        params = {k: v for k, v in {"series": series, "limit": config.limit}.items() if v is not None}
        data = source.fetch("issues", **params)
    else:
        entries = source.fetch("entries.json")
        data = entries
        if series:
            data = [row for row in data if row.get("issue_slug", "").startswith(f"{series}/")]
        if config.limit is not None:
            data = data[: config.limit]
    emit(data, config)


@issues.command("get")
@click.argument("issue")
@click.pass_context
@handle_errors
def issues_get(ctx: click.Context, issue: str) -> None:
    """One issue's public entries. No key: derived from /entries.json,
    filtered to this issue_slug (e.g. tail/44) — a subset of the real
    issue, not the full archive record. With a key: the full issue."""
    config = get_config(ctx)
    source = resolve_source(config)
    if config.api_key:
        data = source.fetch(f"issues/{issue}")
    else:
        entries = source.fetch("entries.json")
        matches = [row for row in entries if row.get("issue_slug") == issue]
        if not matches:
            raise UserInputError(
                f"No public entries found for issue '{issue}'. Run 'toolchain issues list' "
                "to see available issue slugs."
            )
        data = matches
    emit(data, config)

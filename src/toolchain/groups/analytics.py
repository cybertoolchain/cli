from __future__ import annotations

import click

from ..helpers import emit, get_config, handle_errors
from ..source import resolve_source


@click.group()
def analytics() -> None:
    """The charts behind /analytics, as data."""


@analytics.command("get")
@click.argument("chart")
@click.pass_context
@handle_errors
def analytics_get(ctx: click.Context, chart: str) -> None:
    """One chart. No key or a Practitioner key: the masked view already
    published on the site. Researcher+: full detail, names included."""
    config = get_config(ctx)
    source = resolve_source(config)
    if config.api_key:
        data = source.fetch(f"analytics/{chart}")
    else:
        data = source.fetch(f"analytics/{chart}.json")
    emit(data, config)

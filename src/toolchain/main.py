# src/toolchain/main.py
from __future__ import annotations

import sys

import click

from .cli_group import GlobalOptionGroup
from .config import VALID_OUTPUTS, resolve_config
from .log import configure_logging
from .models import ToolchainError

BANNER = r"""
 _____           _      _           _
|_   _|__   ___ | | ___| |__   __ _(_)_ __
  | |/ _ \ / _ \| |/ __| '_ \ / _` | | '_ \
  | | (_) | (_) | | (__| | | | (_| | | | | |
  |_|\___/ \___/|_|\___|_| |_|\__,_|_|_| |_|
"""

TLDR = """\
toolchain tools list                    # every tracked tool
toolchain tools get nmap                # one tool + its latest release
toolchain --limit 10 releases latest    # what just shipped, across the watchlist
toolchain issues get 044                # one newsletter issue, as data
toolchain issues read 044               # ...and as a rendered document
toolchain search "runtime security"     # tools + releases matching a query

Add -k/--api-key (or set TOOLCHAIN_API_KEY) for live filtering, full
analytics, SBOM, and stack details. Run 'toolchain COMMAND --help' for
every option.
"""


@click.group(cls=GlobalOptionGroup, invoke_without_command=True)
@click.option("-k", "--api-key", envvar="TOOLCHAIN_API_KEY", default=None)
@click.option("--site", "site_key", default=None)
@click.option("-o", "--output", default=None, type=click.Choice(VALID_OUTPUTS))
@click.option("-v", "--verbose", is_flag=True, default=False)
@click.option("--debug", is_flag=True, default=False)
@click.option("-c", "--cache", is_flag=True, default=False)
@click.option("-l", "--limit", type=int, default=None)
@click.option("-s", "--short", is_flag=True, default=False)
@click.option("-t", "--timeout", type=float, default=None)
@click.option("--search-fields", default=None)
@click.pass_context
def cli(
    ctx: click.Context,
    api_key: str | None,
    site_key: str | None,
    output: str | None,
    verbose: bool,
    debug: bool,
    cache: bool,
    limit: int | None,
    short: bool,
    timeout: float | None,
    search_fields: str | None,
) -> None:
    """The Cyber Toolchain / aitoolchain command-line client."""
    try:
        ctx.obj = resolve_config(
            api_key=api_key,
            site=site_key,
            output=output,
            verbose=verbose,
            debug=debug,
            cache=cache,
            limit=limit,
            short=short,
            timeout=timeout,
            search_fields=search_fields,
        )
    except ToolchainError as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(exc.exit_code)
    configure_logging(verbose)
    if ctx.invoked_subcommand is None:
        click.echo(BANNER, err=True)
        click.echo(
            "Run 'toolchain --help' for commands, or 'toolchain tldr' for a quick reference.",
            err=True,
        )


@cli.command()
def tldr() -> None:
    """Quick reference for common commands."""
    click.echo(TLDR)


from .groups.tools import tools as tools_group

cli.add_command(tools_group, name="tools")

from .groups.releases import releases as releases_group

cli.add_command(releases_group, name="releases")


def main() -> None:
    try:
        cli(standalone_mode=False)
    except click.ClickException as exc:
        exc.show()
        sys.exit(exc.exit_code)
    except ToolchainError as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(exc.exit_code)
    except click.exceptions.Abort:
        sys.exit(1)


if __name__ == "__main__":
    main()

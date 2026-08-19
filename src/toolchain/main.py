# src/toolchain/main.py
from __future__ import annotations

import sys

import click

from .cli_group import GlobalOptionGroup, set_mode_meta
from .colors import PALETTES
from .config import VALID_OUTPUTS, resolve_config
from .log import configure_logging
from .models import ToolchainError

# Brand kit ASCII wordmark ("toolchain" block only — the "cyber" block
# is dropped, this CLI is shared with aitoolchain), verbatim from
# generator/site/public/brand/cyber-toolchain-ascii.txt.
_LOGO_LINES = (
    "┌┬┐┌─┐┌─┐┬  ┌─┐┬ ┬┌─┐┬┌┐┌",
    " │ │ ││ ││  │  ├─┤├─┤││││",
    " ┴ └─┘└─┘┴─┘└─┘┴ ┴┴ ┴┴┘└┘",
)


# The icon asset's own two baked-in colors (sampled directly from its
# pixels): a dark-ink background and a teal glyph that happens to be
# exactly PALETTES["dark"]["teal"]. render_icon() projects every opaque
# pixel onto the bg->teal axis to get a 0..1 "how teal is this" mix ratio,
# then re-renders it as bg->PALETTES[mode]["teal"] — so the glyph retints
# per --mode while the dark background (not a themed hue) stays put.
_ICON_BG = (7, 14, 15)
_ICON_TEAL = (52, 226, 212)


def _recolor(rgb: tuple[int, int, int], mode: str) -> tuple[int, int, int]:
    target = PALETTES[mode]["teal"]
    axis = tuple(b - a for a, b in zip(_ICON_BG, _ICON_TEAL))
    denom = sum(component * component for component in axis)
    t = sum((p - a) * d for p, a, d in zip(rgb, _ICON_BG, axis)) / denom
    t = max(0.0, min(1.0, t))
    return tuple(round(a + t * (b - a)) for a, b in zip(_ICON_BG, target))


def render_icon(mode: str) -> str:
    """The brand mark (cyber-toolchain-lockup-hero.png's icon, cropped to
    its rounded-square glyph and downsampled to 28x28) as true-color ANSI
    half-block art, retinted per --mode via _recolor() — packaged as
    src/toolchain/assets/icon.png rather than read from the sibling site
    repo, since a customer running this CLI won't have it checked out."""
    from importlib import resources

    from PIL import Image

    ref = resources.files("toolchain") / "assets" / "icon.png"
    with resources.as_file(ref) as path, Image.open(path) as im:
        im = im.convert("RGBA")
        width, height = im.size
        pixels = im.load()

    lines = []
    for y in range(0, height - 1, 2):
        cells = []
        for x in range(width):
            top = pixels[x, y]
            bottom = pixels[x, y + 1]
            top_on = top[3] >= 128
            bottom_on = bottom[3] >= 128
            if not top_on and not bottom_on:
                cells.append(" ")
            elif top_on and bottom_on:
                cells.append(
                    click.style("▀", fg=_recolor(top[:3], mode), bg=_recolor(bottom[:3], mode))
                )
            elif top_on:
                cells.append(click.style("▀", fg=_recolor(top[:3], mode)))
            else:
                cells.append(click.style("▄", fg=_recolor(bottom[:3], mode)))
        lines.append("".join(cells))
    return "\n".join(lines)


def render_logo_small(mode: str) -> str:
    """Wordmark-only mark (no icon) for lightweight, frequently-run
    subcommands like tldr/help, where the full 14-line render_banner()
    icon would overwhelm a quick reference."""
    color = PALETTES[mode]["teal"]
    return "\n".join(click.style(line, fg=color, bold=True) for line in _LOGO_LINES)


def render_banner(mode: str) -> str:
    color = PALETTES[mode]["teal"]
    icon_lines = render_icon(mode).split("\n")
    word_lines = [click.style(line, fg=color, bold=True) for line in _LOGO_LINES]

    top_pad = (len(icon_lines) - len(word_lines)) // 2
    rows = []
    for i, icon_line in enumerate(icon_lines):
        word_idx = i - top_pad
        word_line = word_lines[word_idx] if 0 <= word_idx < len(word_lines) else ""
        rows.append(f"{icon_line}  {word_line}")
    return "\n" + "\n".join(rows) + "\n"


TLDR = """\
toolchain tools list                    # every tracked tool
toolchain tools get nmap                # one tool + its latest release
toolchain --limit 10 releases latest    # what just shipped, across the watchlist
toolchain issues tail list              # just the tail-series issues
toolchain issues read tail/44           # one issue, rendered as a document
toolchain issues                        # browse issues interactively
toolchain search "runtime security"     # tools + releases matching a query

Add -k/--api-key (or set TOOLCHAIN_API_KEY) for live filtering, full
analytics, SBOM, and stack details. Run 'toolchain COMMAND --help' for
every option.
"""


def render_tldr(mode: str) -> str:
    color = PALETTES[mode]["teal"]
    lines = []
    for line in TLDR.split("\n"):
        if line.lstrip().startswith("toolchain") and "#" in line:
            command, hash_sign, comment = line.partition("#")
            lines.append(click.style(command, fg=color, bold=True) + hash_sign + comment)
        else:
            lines.append(line)
    return "\n".join(lines)


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
@click.option(
    "--mode",
    envvar="TOOLCHAIN_MODE",
    default=None,
    is_eager=True,
    callback=set_mode_meta,
    help="Color palette for the banner, help menu, and JSON output: "
    "dark|light|sepia|contrast, matching the website's 4 themes "
    "(env: TOOLCHAIN_MODE, default: dark).",
)
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
    mode: str | None,
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
            mode=mode,
        )
    except ToolchainError as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(exc.exit_code)
    configure_logging(verbose)
    if ctx.invoked_subcommand is None:
        click.echo(render_banner(ctx.obj.mode), err=True)
        click.echo(
            "Run 'toolchain --help' for commands, or 'toolchain tldr' for a quick reference.",
            err=True,
        )


@cli.command()
@click.pass_context
def tldr(ctx: click.Context) -> None:
    """Quick reference for common commands."""
    click.echo(render_logo_small(ctx.obj.mode) + "\n", err=True)
    click.echo(render_tldr(ctx.obj.mode))


@cli.command("help")
@click.pass_context
def help_command(ctx: click.Context) -> None:
    """Show this message and exit."""
    click.echo(render_logo_small(ctx.obj.mode) + "\n", err=True)
    click.echo(ctx.parent.get_help())


from .groups.tools import tools as tools_group

cli.add_command(tools_group, name="tools")

from .groups.releases import releases as releases_group

cli.add_command(releases_group, name="releases")

from .groups.categories import categories as categories_group

cli.add_command(categories_group, name="categories")

from .groups.issues import issues as issues_group

cli.add_command(issues_group, name="issues")

from .groups.analytics import analytics as analytics_group

cli.add_command(analytics_group, name="analytics")

from .groups.search import search as search_command

cli.add_command(search_command, name="search")


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

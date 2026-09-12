from __future__ import annotations

import click

from ..helpers import emit, get_config, handle_errors
from ..models import UserInputError
from ..source import resolve_source

SERIES: tuple[str, ...] = ("head", "tail", "diff")

#: The free site publishes entries per TOOL (/tool-entries/<slug>.json) and
#: retired the bulk /entries.json this CLI read issues out of — it served the
#: whole corpus in one request. Nothing free is keyed by issue any more.
_NO_KEY_ISSUE_ENTRIES = (
    "Reading an issue's entries needs an API key (-k). Without one the site "
    "publishes entries per tool — 'toolchain tools releases <slug>' — and "
    "'toolchain issues download <slug> --format html' fetches the rendered page."
)


def _qualify(series: str | None, issue: str) -> str:
    """A bare number under a series subgroup ('44' under 'tail') becomes
    the full slug ('tail/44'); an already-qualified issue passes through."""
    if series and "/" not in issue:
        return f"{series}/{issue}"
    return issue


def _list_data(ctx: click.Context, series: str | None):
    config = get_config(ctx)
    source = resolve_source(config)
    if config.api_key:
        params = {k: v for k, v in {"series": series, "limit": config.limit}.items() if v is not None}
        return config, source.fetch("issues", **params)
    # The site's search index is the one free listing of issues: one row per
    # daily (Tail) issue, addressed /newsletter/<number>. Head and Diff are
    # not in it, so a series filter for those is honestly empty here.
    index = source.fetch("search-index.json")
    data = [_issue_row(row) for row in index if row.get("type") == "issue"]
    if series:
        data = [row for row in data if row.get("issue_slug", "").startswith(f"{series}/")]
    if config.limit is not None:
        data = data[: config.limit]
    return config, data


def _issue_row(row: dict) -> dict:
    number = str(row.get("href", "")).rstrip("/").rsplit("/", 1)[-1]
    sub = str(row.get("sub", ""))
    digits = "".join(ch for ch in sub.split("·")[-1] if ch.isdigit())
    return {
        "issue_slug": f"tail/{number}",
        "label": row.get("label", ""),
        "tools": int(digits) if digits else 0,
    }


def _entries_no_key(source, issue: str) -> list[dict]:
    raise UserInputError(_NO_KEY_ISSUE_ENTRIES)


def _get_data(ctx: click.Context, issue: str):
    config = get_config(ctx)
    source = resolve_source(config)
    if config.api_key:
        return config, source.fetch(f"issues/{issue}")
    return config, _entries_no_key(source, issue)


def _download(ctx: click.Context, issue: str, fmt: str) -> None:
    config = get_config(ctx)
    source = resolve_source(config)
    if config.api_key:
        data = source.fetch(f"issues/{issue}/download", format=fmt)
        emit(data, config)
        return
    if fmt == "json":
        emit(_entries_no_key(source, issue), config)
        return
    # fmt == "html"
    if "/" not in issue:
        raise UserInputError(
            f"'{issue}' isn't a full issue slug. Run 'toolchain issues list' to find one "
            "(e.g. tail/44)."
        )
    click.echo(source.fetch_text(f"newsletter/{issue}"))


def _read(ctx: click.Context, issue: str) -> None:
    from ..tui.reader import render_issue

    config = get_config(ctx)
    source = resolve_source(config)
    if config.api_key:
        data = source.fetch(f"issues/{issue}")
        entries = data.get("entries", [])
    else:
        entries = _entries_no_key(source, issue)
    click.echo(render_issue(entries))


def _browse(ctx: click.Context, series: str | None) -> None:
    from ..tui.issues_browse import IssueBrowserApp

    config = get_config(ctx)
    if not config.api_key:
        raise UserInputError(_NO_KEY_ISSUE_ENTRIES)
    config, data = _list_data(ctx, series)
    if config.api_key:
        issues = data.get("issues", data if isinstance(data, list) else [])
        rows = [
            {
                "issue_slug": row.get("issue_slug", ""),
                "published_at": row.get("published_at", ""),
                "tools": row.get("tools") or ([row["tool"]] if row.get("tool") else []),
            }
            for row in issues
        ]
    else:
        # entries.json is one row per (tool, issue) pair — collapse to one
        # row per issue for the browser, collecting every tool featured
        # in that issue.
        seen: dict[str, dict] = {}
        for row in data:
            slug = row.get("issue_slug", "")
            entry = seen.setdefault(
                slug, {"issue_slug": slug, "published_at": row.get("published_at", ""), "tools": []}
            )
            tool = row.get("tool", "")
            if tool and tool not in entry["tools"]:
                entry["tools"].append(tool)
        rows = list(seen.values())

    source = resolve_source(config)

    def entries_fetcher(issue_slug: str) -> list[dict]:
        if config.api_key:
            return source.fetch(f"issues/{issue_slug}").get("entries", [])
        return _entries_no_key(source, issue_slug)

    app = IssueBrowserApp(rows, entries_fetcher)
    app.run()


@click.group(invoke_without_command=True)
@click.pass_context
@handle_errors
def issues(ctx: click.Context) -> None:
    """The published archive — daily, highlights, and docs-weekly. Run
    with no subcommand to browse interactively; run 'toolchain issues
    {head,tail,diff}' (with no further subcommand) to browse just that
    series. Human-only — does not go through -o/--output."""
    if ctx.invoked_subcommand is None:
        _browse(ctx, series=None)


@issues.command("list")
@click.option("--series", default=None, type=click.Choice(SERIES))
@click.pass_context
@handle_errors
def issues_list(ctx: click.Context, series) -> None:
    """The issue index. No key: the daily issues the site indexes, one
    row each (slug, label, tool count) — Head and Diff are not listed
    there. With a key: the real issue index. Use the GLOBAL -l/--limit (before the subcommand)
    to cap how many come back — there is no separate --limit here."""
    config, data = _list_data(ctx, series)
    emit(data, config)


@issues.command("get")
@click.argument("issue")
@click.pass_context
@handle_errors
def issues_get(ctx: click.Context, issue: str) -> None:
    """One issue's entries. Needs a key: the free site publishes entries
    per tool ('toolchain tools releases <slug>'), not per issue."""
    config, data = _get_data(ctx, issue)
    emit(data, config)


@issues.command("download")
@click.argument("issue")
@click.option("--format", "fmt", required=True, type=click.Choice(["json", "html"]))
@click.pass_context
@handle_errors
def issues_download(ctx: click.Context, issue: str, fmt: str) -> None:
    """The same issue as a file — JSON, or the standalone rendered page."""
    _download(ctx, issue, fmt)


@issues.command("read")
@click.argument("issue")
@click.pass_context
@handle_errors
def issues_read(ctx: click.Context, issue: str) -> None:
    """Read an issue as a rendered document — Markdown with syntax
    highlighting, not raw JSON. Human-only: does not go through
    -o/--output. Pipe to a pager, e.g. `toolchain issues read tail/44 | less -R`."""
    _read(ctx, issue)


def _make_series_group(series: str) -> click.Group:
    @click.group(
        name=series,
        invoke_without_command=True,
        help=f"'{series}' issues only. Run with no subcommand to browse just this "
        "series interactively.",
    )
    @click.pass_context
    @handle_errors
    def series_group(ctx: click.Context) -> None:
        if ctx.invoked_subcommand is None:
            _browse(ctx, series=series)

    @series_group.command("list", help=f"List every {series} issue.")
    @click.pass_context
    @handle_errors
    def series_list(ctx: click.Context) -> None:
        config, data = _list_data(ctx, series)
        emit(data, config)

    @series_group.command(
        "get", help=f"One {series} issue's entries. ISSUE may be bare (44) or full ({series}/44)."
    )
    @click.argument("issue")
    @click.pass_context
    @handle_errors
    def series_get(ctx: click.Context, issue: str) -> None:
        config, data = _get_data(ctx, _qualify(series, issue))
        emit(data, config)

    @series_group.command("download", help=f"Download one {series} issue as JSON or HTML.")
    @click.argument("issue")
    @click.option("--format", "fmt", required=True, type=click.Choice(["json", "html"]))
    @click.pass_context
    @handle_errors
    def series_download(ctx: click.Context, issue: str, fmt: str) -> None:
        _download(ctx, _qualify(series, issue), fmt)

    @series_group.command("read", help=f"Read one {series} issue as rendered Markdown.")
    @click.argument("issue")
    @click.pass_context
    @handle_errors
    def series_read(ctx: click.Context, issue: str) -> None:
        _read(ctx, _qualify(series, issue))

    return series_group


for _series in SERIES:
    issues.add_command(_make_series_group(_series))

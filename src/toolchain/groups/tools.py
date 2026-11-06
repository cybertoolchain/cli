# src/toolchain/groups/tools.py
from __future__ import annotations

import re

import click

from ..freshness import age_payload
from ..helpers import emit, get_config, handle_errors, tool_slug
from ..models import UserInputError
from ..source import resolve_source
from ..source.entries import published_entries


EXT_OPTIONS = ("api", "mcp", "sdk", "plugin", "scripting", "cli", "webhook", "declarative")

_COVERAGE_WORDS = {
    "unknown": "Not checked yet",
    "partial": "Partly checked",
    "not_applicable": "Not applicable",
}


def _parse_ext(values) -> list[str]:
    """--ext is repeatable and comma-separated. Returns the option ids in the
    order given, de-duplicated; anything outside the vocabulary is an error."""
    ids: list[str] = []
    for value in values or ():
        for part in str(value).split(","):
            part = part.strip().lower()
            if not part:
                continue
            if part not in EXT_OPTIONS:
                raise UserInputError(
                    f"Unknown extensibility option '{part}'. Choose from: {', '.join(EXT_OPTIONS)}."
                )
            if part not in ids:
                ids.append(part)
    return ids


def _require_ext_fields(rows: list[dict]) -> None:
    """A projection from before extensibility shipped has no such field on any
    row. Say so, rather than return an empty list that reads as "none"."""
    if rows and not any("extensibility_types" in row for row in rows):
        raise UserInputError(
            "This data does not include extensibility information yet, so --ext "
            "cannot filter it. Upgrade toolchain or try again after the next site update."
        )


def _filter_ext(rows: list[dict], ext: list[str]) -> list[dict]:
    """Any semantics: keep a tool that has at least one selected option."""
    _require_ext_fields(rows)
    wanted = set(ext)
    return [row for row in rows if wanted & set(row.get("extensibility_types") or ())]


def _ext_status(row: dict) -> str | None:
    """Reader wording for a tool's coverage. Never the internal word
    'reviewed' as a promise; a checked tool says 'Checked' plus the revision
    date when the revision starts with one."""
    coverage = row.get("extensibility_coverage")
    if coverage is None:
        return None
    if coverage == "reviewed":
        m = re.match(r"\d{4}-\d{2}-\d{2}", str(row.get("extensibility_revision") or ""))
        return f"Checked {m.group(0)}" if m else "Checked"
    return _COVERAGE_WORDS.get(coverage, "Not checked yet")


@click.group()
def tools() -> None:
    """The watchlist itself — what's tracked, what each tool is, and what
    it has shipped."""


def _slug_of(tool_row: dict) -> str:
    return tool_slug(tool_row.get("tool", ""))


def _tool_types(tool_row: dict) -> list[str]:
    """Every form a tool ships in. The API returns tool_type as a list (a tool
    can be a CLI and a service at once); an older payload carries the single
    string, and a row with none carries nothing."""
    value = tool_row.get("tool_type")
    if isinstance(value, str):
        return [value]
    if isinstance(value, (list, tuple)):
        return [item for item in value if isinstance(item, str)]
    return []


def _filter_tools(rows: list[dict], category, license_, tool_type, q) -> list[dict]:
    """Client-side equivalent of the API's query params, for the no-key
    path where the fetched payload is a static tools.json — a query string
    against a static file does nothing, so filtering has to happen here.
    Used by both `tools list` and `tools count`."""
    if category is not None:
        rows = [row for row in rows if row.get("category") == category]
    if license_ is not None:
        # site JSON's open_source is True/False, or None when unknown — an
        # unknown value doesn't match either license filter, which is the
        # more honest behavior than guessing.
        wanted = license_ == "open-source"
        rows = [row for row in rows if row.get("open_source") is wanted]
    if tool_type is not None:
        # The free tools.json (generator/site/src/lib/feed.ts's FeedEntry)
        # does not carry a tool_type field per tool at all — only the keyed
        # /v1/tools response does. So this filter can never match anything
        # in the no-key path; that's a real limitation of the free data,
        # not a bug in this filter.
        rows = [row for row in rows if tool_type in _tool_types(row)]
    if q is not None:
        needle = q.lower()
        rows = [row for row in rows if needle in str(row.get("tool", "")).lower()]
    return rows


@tools.command("list")
@click.option("--category", default=None)
@click.option("--license", "license_", default=None, type=click.Choice(["open-source", "commercial"]))
@click.option("--tool_type", default=None)
@click.option("--q", default=None)
@click.option("--cursor", default=None)
@click.option("--ext", "ext", multiple=True, help="Extensibility option (api, mcp, sdk, plugin, scripting, ...). Repeat or comma-separate; matches a tool with ANY.")
@click.pass_context
@handle_errors
def tools_list(ctx: click.Context, category, license_, tool_type, q, cursor, ext) -> None:
    """Every tracked tool. No key: the current watchlist snapshot from the
    site. With a key: live, server-side filtered and paginated."""
    config = get_config(ctx)
    ext_ids = _parse_ext(ext)
    source = resolve_source(config)
    params = {
        k: v
        for k, v in {
            "extensibility": ",".join(ext_ids) or None,
            "category": category,
            "license": license_,
            "tool_type": tool_type,
            "q": q,
            "cursor": cursor,
        }.items()
        if v is not None
    }
    if config.api_key:
        data = source.fetch("tools", **params)
        if ext_ids:
            _require_ext_fields(data.get("tools") or [])
    else:
        data = source.fetch("tools.json")
        rows = _filter_tools(data["tools"], category, license_, tool_type, q)
        if ext_ids:
            rows = _filter_ext(rows, ext_ids)
        data = {**data, "tools": rows}
        if ext_ids and "count" in data:
            data["count"] = len(rows)
    emit(age_payload(data), config)


@tools.command("count")
@click.option("--category", default=None)
@click.option("--license", "license_", default=None, type=click.Choice(["open-source", "commercial"]))
@click.option("--tool_type", default=None)
@click.option("--ext", "ext", multiple=True, help="Extensibility option; repeat or comma-separate (ANY).")
@click.pass_context
@handle_errors
def tools_count(ctx: click.Context, category, license_, tool_type, ext) -> None:
    """Just the number. No key: counted client-side from the free watchlist
    snapshot. With a key: live, server-side count."""
    config = get_config(ctx)
    ext_ids = _parse_ext(ext)
    source = resolve_source(config)
    if config.api_key:
        params = {
            k: v
            for k, v in {
                "category": category,
                "license": license_,
                "tool_type": tool_type,
                "extensibility": ",".join(ext_ids) or None,
            }.items()
            if v is not None
        }
        data = source.fetch("tools/count", **params)
    else:
        site_data = source.fetch("tools.json")
        filtered = _filter_tools(site_data["tools"], category, license_, tool_type, None)
        if ext_ids:
            filtered = _filter_ext(filtered, ext_ids)
        data = {"total": len(filtered)}
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
    data = {**data, "freshness": data.get("freshness")}
    status = _ext_status(data)
    if status is not None:
        data["extensibility_status"] = status
    emit(age_payload(data), config)


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
        # The site publishes entries per tool, not in bulk: /entries.json was
        # retired for /tool-entries/<slug>.json, which exists for every tool
        # with a page and is empty for one we have published nothing about.
        data = published_entries(source, slug)
        if not data:
            raise UserInputError(
                f"No release history found for '{slug}'. Run 'toolchain tools list' to see "
                "tracked tools."
            )
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


@click.command('claims')
@click.argument('slug')
@click.option('-j', '--json', 'as_json', is_flag=True, help='Return the canonical receipt JSON.')
@click.pass_context
@handle_errors
def claims(ctx: click.Context, slug: str, as_json: bool) -> None:
    """Each feature's reader word and full supporting evidence."""
    from dataclasses import replace
    import re
    config = get_config(ctx)
    if not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', slug):
        raise UserInputError('Use a tool slug from toolchain tools list.')
    source = resolve_source(config)
    path = f'tools/{slug}/claims' if config.api_key else f'claims/{slug}.json'
    if config.debug:
        click.echo(source.curl(path), err=True)
    data = source.fetch(path)
    emit(age_payload(data), replace(config, output='json') if as_json else config)

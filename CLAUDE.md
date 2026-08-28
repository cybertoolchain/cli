# CLAUDE.md — toolchain CLI

Command-line client for The Cyber Toolchain / aitoolchain. Design:
`docs/superpowers/specs/2026-08-18-toolchain-cli-design.md`. Implementation
plan: `docs/superpowers/plans/2026-08-18-toolchain-cli.md`.

## Two backends, picked once, centrally

`resolve_source(config)` (`src/toolchain/source/__init__.py`) is the only
place that decides `SiteSource` (no key, free static JSON on the product's
GitHub Pages site) vs. `ApiSource` (a key, live `/v1/*`). Every command
calls it and nothing else. A command with no free equivalent (`tools sbom`)
checks `config.api_key` itself and raises `UserInputError` naming where to
get one — do the same for any new key-only command; never let it fall
through to a raw 401 from `ApiSource`.

## Known deviation from the original design spec

The design spec listed `tools stack` as key-only. Implementation found
`generator/site/public/toolCode.json` already publishes exactly that data
(language mix, dependencies, AI-attribution) for free, so `tools stack`
reads it with no key and only calls `/v1/tools/{slug}/stack` with one. If
this surprises you, it's a real, deliberate correction — not a bug.

`tools count` is also free with no key, contrary to what an earlier version
of the design implied. It has no site-JSON count endpoint, but `tools.json`
(already fetched by `tools list`/`tools get`) carries the full tool list, so
the no-key path fetches it and counts client-side after applying the same
`--category`/`--license`/`--tool_type` filters `tools list` applies (see
`_filter_tools` in `src/toolchain/groups/tools.py`). The keyed path still
calls `/v1/tools/count` for a live, server-side count.

## `--debug` and the httpx/httpcore logging landmine

`ApiSource.curl()` is structurally leak-proof — it never references the raw
key, only `$TOOLCHAIN_API_KEY`. But `redact()` (`src/toolchain/log.py`) has
no call site anywhere yet. `configure_logging()` only configures a logger
named `"toolchain"` (`propagate=False`); it does not touch httpx/httpcore's
own loggers. If a future `--debug` enhancement ever enables their DEBUG
logging (directly or via a bare `logging.basicConfig(level=logging.DEBUG)`),
they'll log request headers — including the real `x-api-key` — straight to
stderr, outside `ApiSource`'s control. **Before wiring anything that touches
httpx/httpcore logging, keep it off or run every line through `redact()`.**

## Brand banner and `--mode`

`src/toolchain/colors.py`'s `PALETTES` is the single source of truth for
brand color, copied from `generator-brand/brands/cyber/brand.yaml`'s
`palette.<mode>.{teal,blue,amber,magenta}` for all 4 site themes. Everything
else derives from it: `config.VALID_MODES`, the wordmark/menu color in
`main.py`, and the JSON syntax-highlighting palette in `output.py`. Adding a
5th site theme means adding one row to `PALETTES` — nothing else changes.

The bare-invocation banner is `render_icon()` (the brand mark, cropped from
`cyber-toolchain-lockup-hero.png` and shipped downsampled as
`src/toolchain/assets/icon.png`, rendered as true-color ANSI half-block art
via Pillow) beside `_LOGO_LINES` (the "toolchain" wordmark block only — no
"cyber", since this CLI is shared with aitoolchain), colored per `--mode`.
The icon keeps its own baked-in brand colors; `--mode` doesn't retint it.

`--mode` is `is_eager=True` with a `callback` (`cli_group.set_mode_meta`)
that stashes the value on `ctx.meta["mode"]` *before* `ctx.obj` exists —
needed so `--help`'s own eager callback (which fires and exits before the
group's body runs) can still render a colored menu via
`GlobalOptionGroup.get_help()`. If you add a new eager option that also
needs to be help-aware, follow that same pattern; a non-eager option won't
have run yet when `--help` fires.

`--mode` also recolors `-o json` (and `-s/--short`) output via
`output.highlight_json()` — ANSI wrapped around each token via
`click.style`, which `click.echo` strips automatically for non-tty/piped
output, so redirected JSON stays valid. Tests calling `format_output()`
directly (not through `emit()`/`click.echo`) must strip it with
`click.unstyle()` before `json.loads()` — see `tests/test_output.py`'s
`_plain()` helper.

## `issues` series subgroups and TUI

`src/toolchain/groups/issues.py` factors its shared logic (`_list_data`,
`_get_data`, `_download`, `_read`, `_browse`) out of the flat `issues
list|get|download|read` commands so `_make_series_group()` can rebuild the
same four commands under `issues {head,tail,diff}`, pre-scoped to that
series — `issues tail get 44` qualifies the bare `44` to `tail/44` via
`_qualify()`; an already-qualified slug passes through untouched. Both
`issues` and each series group are `invoke_without_command=True`: with no
further subcommand they call `_browse()`, which opens `IssueBrowserApp`
(`src/toolchain/tui/issues_browse.py`) — the no-key path dedupes
`entries.json` (one row per tool+issue) down to one row per `issue_slug`
first, since the browser lists issues, not entries. Selecting a row prints
that issue rendered via `tui.reader.render_issue()`, the same renderer
`issues read` uses. Adding a 4th series means adding it to the `SERIES`
tuple — the factory and the `--series` choice on the flat commands both
read from it.

## Adding a new product (a third `--site`)

Add one `Site(site_base=..., api_base=...)` entry to `SITES` in
`src/toolchain/config.py`. `api_base=None` until that product ships a data
API — every keyed command already handles that centrally.

## Testing

Every `Source` implementation accepts an injectable `client` (see
`tests/fakes.py`'s `FakeClient`/`FakeResponse`) — no HTTP mocking library,
no real network calls, ever, in the test suite. Command-group tests
monkeypatch `resolve_source` at the group module's import path (e.g.
`toolchain.groups.tools.resolve_source`), not the shared `toolchain.source`
module, since each group imports it by name.

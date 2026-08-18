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
key attribute, only `$TOOLCHAIN_API_KEY`. But `redact()` (`src/toolchain/log.py`)
has no call site anywhere in this codebase yet, found during Task 7's review.
If a future `--debug` enhancement enables raw `httpx`/`httpcore` DEBUG-level
logging (e.g. `logging.getLogger("httpx").setLevel(logging.DEBUG)` or a bare
`logging.basicConfig(level=logging.DEBUG)` that httpx's loggers pick up),
those libraries log request headers independently of `ApiSource` — including
the real `x-api-key` value — straight to stderr, outside this class's
control entirely. `configure_logging()` (Task 5) only configures a logger
named `"toolchain"` with `propagate=False`, so it does NOT currently touch
httpx's own loggers — that's why this is a landmine and not a live bug.
**Before wiring any future feature that touches httpx/httpcore's own
logging, either keep it off entirely or run every line through `redact()`
first.**

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

# `toolchain` CLI — Design

**Goal:** A customer-facing command-line tool, `toolchain`, that gives readers of
The Cyber Toolchain (and, later, aitoolchain) programmatic access to the same
data the website shows — tools, releases, issues, search — for free with no
account, and the deeper, live, filterable `/v1` data API once they hold a
paid `ctk_…` key. Command syntax mirrors the endpoint groups already
documented on `/api` and the curl examples on that page, so a reader
translating the docs into a terminal command finds the same nouns.

**Not in this round:** publishing to PyPI/Homebrew, an aitoolchain data API
(it doesn't exist yet — only the site is live), the two "coming later"
endpoints from `/api` (`doc-diffs`, `corpus-export`). Those stay unimplemented
stubs that report "not live yet," same as the docs page does.

## Why two backends, not one

`/v1/*` on the data API (`ctk-data-api`, behind CloudFront) requires a valid
`ctk_`-prefixed key on **every** request — verified directly against
`tct/src/dataapi/auth.py` in `generator`: a missing or unknown key returns
401 unconditionally, including for what the docs page labels the "public"
tier. "Public" there means *any* key, free-tier included, not *no* key. So a
CLI that only spoke to `/v1` would have no true keyless mode at all.

But the website itself already publishes real, unauthenticated JSON built
for exactly this kind of external consumption — `/tools.json`, `/entries.json`,
`/search-index.json`, `/tool-apis.json`, `/tool-readme.json`, `/cli-explains.json`,
the per-issue archive, category RSS/OPML — verified live in `generator/site/src/pages/*.json.ts`
and `site/public/*.json`. A keyless `toolchain` reads those. A keyed `toolchain`
calls `/v1` instead, for live filtering/pagination, full (unmasked) analytics,
and the endpoints with no static-site equivalent at all (SBOM, stack/surface
stats). Both paths return through the same command and the same output
shape — the split is invisible to a script piping `-o json`, visible only in
what each command can and can't do without a key.

## Architecture

```
                 ┌────────────┐
   no key   ───▶ │ SiteSource │ ──▶ httpx GET, static JSON on cybertoolchain.github.io
                 └────────────┘
 command ──▶ Source (picked automatically)
                 ┌────────────┐
   -k/--api-key ▶│ ApiSource  │ ──▶ httpx GET, /v1/*, x-api-key header
                 └────────────┘
                        │
                        ▼
                 command-local normalizer  (site JSON and /v1 JSON differ in
                        │                    field shape; each command owns
                        ▼                    reconciling them)
                    format_output()  ──▶  json / table / csv / tsv  (emit)
```

- `Source` is a small protocol (`fetch(path, **params) -> dict`). `SiteSource`
  and `ApiSource` are the two implementations; nothing above the command layer
  knows which one is live.
- A command that has **no** site-JSON equivalent (`tools sbom`, `tools stack`,
  `analytics get`, and the not-yet-live `doc-diffs`/`corpus-export`) only
  implements the `ApiSource` path. Running it with no key raises
  `UserInputError` (exit 1) with the upgrade nudge baked in:
  `tools sbom requires an API key — get one at cybertoolchain.github.io/account
  (Researcher plan or higher).` The same sentence appears in that command's
  `--help` text, per Jon's instruction that key-gating be visible in the
  argument/option description, not just at runtime.
- `tools api`, `tools examples`, `tools releases`, and `analytics get` are
  "both, different depth": a public-tier fetch (keyless, or a free key) gets
  what the site already shows; a Researcher+ key gets the fuller `/v1`
  response (e.g. `analytics get` unmasked, `tools api` per-endpoint detail
  rather than just capability areas). This mirrors the two curl examples
  already on `/api` for `analytics` (masked vs. full).

## Command reference

Grammar: `toolchain [GLOBAL OPTIONS] <group> <verb> [ARGS] [OPTIONS]`. Verbs
stay consistent across groups (`list`, `get`, `count`) per Jon's CLI style
guide. Resource identifiers (`slug`, `issue`, `chart`) are positional, not
`-j/--id` — unlike Jon's usual convention for ambiguous resources, `/api`'s
own paths are unambiguous path segments (`GET /v1/tools/{slug}`), and a
positional reads as a direct translation of the curl example
(`toolchain tools get nmap`).

```
toolchain tools list                    # --category --license --tool_type --q --limit
toolchain tools count                   # scoped count, same filters as list
toolchain tools get <slug>              # one tool + its latest release
toolchain tools browse                  # TUI: fuzzy search + select over the tools list
toolchain tools releases <slug>         # --since --until --limit
toolchain tools api <slug>              # capability areas; full endpoint detail w/ key
toolchain tools examples <slug>         # captured CLI examples, with real output
toolchain tools stack <slug>            # language/deps/AI-attribution   [requires API key]
toolchain tools sbom <slug>             # software bill of materials     [requires API key]

toolchain releases list                 # --tools --categories --since --until --limit
toolchain releases latest [--limit N]   # newest across the whole watchlist, no filters

toolchain categories list               # taxonomy + live tool counts

toolchain issues list                   # --series --limit
toolchain issues get <issue>            # data command: -o json (default)/table/csv/tsv
toolchain issues read <issue>           # human command: Rich markdown + syntax-highlighted
                                         # terminal render; pipeable to a pager; not part
                                         # of the emit() pipeline (deliberate exception)
toolchain issues download <issue>       # --format json|html

toolchain analytics get <chart>         # masked without a key; full detail w/ Researcher+  [requires API key for full detail]

toolchain search <query>                # --type tool|release
```

`tools browse` and `issues read` are the two explicitly human-only views —
they skip `emit()`/`format_output()` on purpose (a TUI and a rendered
document have no meaningful `-o csv` mode), called out here so it doesn't
read as an inconsistency against the "one output path" rule later. Both run
through the same `Source` layer as every scriptable command.

## Config, auth, site selection

Global options resolve **flag → env var → default**, single env prefix
`TOOLCHAIN_`, centrally validated in `resolve_config()`:

| Flag | Env | Meaning |
|---|---|---|
| `-k, --api-key` | `TOOLCHAIN_API_KEY` | `ctk_…` key; absent = keyless/site mode |
| `--site` | `TOOLCHAIN_SITE` | Which product: `cybertoolchain` (default) or `aitoolchain` |
| `-o, --output` | `TOOLCHAIN_OUTPUT` | `json` (default) / `table` / `csv` / `tsv` |
| `-v, --verbose` | | Log requests/responses to stderr |
| `--debug` | | Full request/response bodies + an equivalent `curl` (ApiSource) or bare `GET` URL (SiteSource) |
| `-c, --cache` | | Serve from local response cache |
| `-l, --limit` | | Truncate the largest array in the output |
| `-s, --short` | | Compact one-line-per-row output |
| `-t, --timeout` | `TOOLCHAIN_TIMEOUT` | Request timeout, default 30s |

A `SITES` registry (`config.py`) maps a site key to its two base URLs:

```python
SITES = {
    "cybertoolchain": Site(
        site_base="https://cybertoolchain.github.io",
        api_base="https://d3hvv6ete0783d.cloudfront.net",  # swap for api.cybertoolchain.com once DNS lands
    ),
    "aitoolchain": Site(
        site_base="https://aitoolchain.io",
        api_base=None,  # no data API yet
    ),
}
```

A keyed command against a site with `api_base=None` fails with a clear,
specific error (`aitoolchain has no data API yet`) rather than a connection
error — wiring aitoolchain in later, once it has one, is filling in one URL,
not new code.

## Output & DX

Every scriptable command ends in `emit(data, config)` → `format_output()`:
`json` (default, indent=2), `table` (tabulate grid), `csv`, `tsv`. `-s/--short`
reorders and compacts to one line per row; `--search-fields` recursively pulls
matching field values. Data goes to stdout only; the banner, prompts,
`-v`/`--debug` logs, and "Executing: …" notices go to stderr, so
`toolchain tools list -o json | jq …` and interactive/TUI modes never fight
over the same stream.

Standard DX set (Jon's style guide, §10): banner + hint on bare invocation,
`--tldr`, `-c/--cache` (caches both `SiteSource` and `ApiSource` responses,
keyed by command + params), `--debug` curl-dump. Typed exceptions map to exit
codes 0/1/2/3 (`UserInputError`/`APIError`/`NetworkError`) exactly as in the
style guide; the key-required case is a `UserInputError` whose message
carries the upgrade nudge rather than a bare "missing argument."

## Repo layout & packaging

New repo: `~/repos/cybertoolchain/cli` (sibling to `generator`, `ctk-corpus`,
etc. by location, but brand-agnostic in purpose — it also targets
aitoolchain once that product has a data API).

```
cli/
├── pyproject.toml          # setuptools, src/ layout, [project.scripts] toolchain = "toolchain.main:cli"
├── README.md
├── CLAUDE.md
├── src/toolchain/
│   ├── main.py             # root Click group, global options, banner, tldr
│   ├── cli_group.py        # global-flag-misplaced hinting (custom Group subclass)
│   ├── config.py           # Config dataclass, resolve_config(), SITES registry
│   ├── models.py           # constants, exceptions, exit codes
│   ├── source/
│   │   ├── base.py         # Source protocol
│   │   ├── site.py         # SiteSource — static JSON on the GitHub Pages site
│   │   └── api.py          # ApiSource — /v1/*, x-api-key, curl-dump support
│   ├── output.py            # format_output(): json/table/csv/tsv + short mode
│   ├── helpers.py           # emit(), get_config(), handle_errors(), option groups
│   ├── cache.py              # local response cache
│   ├── log.py                 # logging config + key redaction
│   ├── tui/
│   │   ├── browse.py        # `tools browse` — Textual app, searchable/selectable list
│   │   └── reader.py        # `issues read` — Rich Markdown + syntax-highlighted render
│   ├── py.typed
│   └── groups/               # one module per command group
│       ├── tools.py
│       ├── releases.py
│       ├── categories.py
│       ├── issues.py
│       ├── analytics.py
│       └── search.py
└── tests/
    ├── fixtures/             # captured real site JSON + /api's documented example payloads
    └── test_*.py             # pytest + Hypothesis; Source implementations mocked, no network
```

Dependencies beyond Jon's style-guide baseline (click, httpx, tabulate,
questionary): **textual** (TUI: search/filter/select lists) and **rich**
(Markdown + syntax-highlighted terminal rendering; ships with textual
anyway). Installable via `pip install -e .` / `pipx install .` — matching
r7cli's real distribution shape, since this tool is meant to eventually be
customer-installed, unlike the internal `uv run`-as-scripts tools in this
workspace. Nothing published this round (no PyPI, no brew formula) — buildable
and locally installable only, per "we'll pick it public later."

TDD throughout: tests mock `SiteSource` and `ApiSource` against fixture JSON
captured from the live site and `/api`'s own documented example payloads, so
the suite never touches the network.

## Testing

- `pytest` + `Hypothesis` for property-based tests on parsers/formatters
  (`output.py`, `config.py`).
- Fixture-driven integration tests per command group: a `SiteSource` fixture
  and an `ApiSource` fixture per endpoint, both derived from real captured
  shapes (the `/api` page's own example payloads are already hand-verified
  against live runs, per its source comments — reuse them rather than
  re-inventing fixtures).
- A `--debug` snapshot test per command confirming the printed curl/GET
  matches the real endpoint path documented on `/api`.

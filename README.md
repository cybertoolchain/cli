# toolchain

Command-line client for The Cyber Toolchain (and, once it has a data API,
aitoolchain).

## Install globally

Requires [uv](https://docs.astral.sh/uv/):

    uv tool install git+https://github.com/cybertoolchain/cli

Puts `toolchain` on your PATH (`~/.local/bin` by default) from any
directory, no venv or activation needed. Upgrade to the latest commit on
`main` any time with `toolchain update`, or manually with
`uv tool upgrade toolchain-cli`.

## Install for development

    uv venv
    source .venv/bin/activate
    uv pip install -e ".[dev]"

`uv venv` only creates the virtualenv — `toolchain` isn't on your PATH until
you activate it (`source .venv/bin/activate`, once per shell session). If you
don't want to activate anything, prefix every command with `uv run` instead
(e.g. `uv run toolchain tools list`).

## Usage

No API key: reads the free data already published on the site.

    toolchain tools list
    toolchain tools get nmap
    toolchain --limit 10 releases latest
    toolchain issues read tail/44
    toolchain issues tail list          # just the tail series
    toolchain issues                    # interactive browser (Ctrl+C to cancel)
    toolchain search "runtime security"
    toolchain version                   # installed version, and whether a newer one shipped
    toolchain update                    # upgrade a global 'uv tool install' in place

With an API key (`-k`/`--api-key`, or `TOOLCHAIN_API_KEY`): live filtering,
pagination, full analytics detail, SBOM, and per-endpoint API detail. Get a
key from your account page on the site. Commands that have no free
equivalent (`tools sbom`) say so in their own `--help`.

    export TOOLCHAIN_API_KEY=ctk_your_key_here
    toolchain analytics get notes_quality   # full detail instead of masked
    toolchain tools sbom nmap

## Targeting a different product

    toolchain --site ai tools list

`aitoolchain` has no data API yet — only free site commands work against it
until one ships.

## Global options

`-k/--api-key`, `--site`, `-o/--output` (json/table/csv/tsv), `-v/--verbose`,
`--debug`, `-c/--cache`, `-l/--limit`, `-s/--short`, `-t/--timeout`,
`--search-fields`, `--mode` (dark/light/sepia/contrast — colors the banner,
help menu, and JSON output to match the site's theme). Must appear
**before** the subcommand. `toolchain help` works the same as `--help`.

## Shell completion

Tab-completion for commands and options, bash and zsh:

    # bash — add to ~/.bashrc
    source /path/to/cli/completions/toolchain.bash

    # zsh — add to ~/.zshrc, before compinit
    source /path/to/cli/completions/toolchain.zsh

Regenerate both after adding/renaming a command or option:

    _TOOLCHAIN_COMPLETE=bash_source toolchain > completions/toolchain.bash
    _TOOLCHAIN_COMPLETE=zsh_source toolchain > completions/toolchain.zsh

`tests/test_completions.py` fails if the committed files drift from what the
CLI would generate, as a reminder to re-run the above.

## Development

    uv run pytest

TDD throughout: every command's tests stub `resolve_source` with a fake
`Source`, so the suite never touches the network.

## Releasing

`toolchain version` and `toolchain update` compare against this repo's
**latest GitHub release**, not the newest commit — so a version bump only
becomes visible to installed users once one is cut:

    # bump the version in pyproject.toml, then:
    git tag vX.Y.Z && git push origin vX.Y.Z
    gh release create vX.Y.Z --generate-notes

`uv tool install`/`uv tool upgrade` always track `main`'s current commit
regardless of tags, so `toolchain update` itself always pulls the latest code
— the release only affects what `toolchain version` reports as available.

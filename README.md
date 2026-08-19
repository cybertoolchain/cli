# toolchain

Command-line client for The Cyber Toolchain (and, once it has a data API,
aitoolchain).

## Install

    uv venv
    uv pip install -e ".[dev]"

## Usage

No API key: reads the free data already published on the site.

    toolchain tools list
    toolchain tools get nmap
    toolchain --limit 10 releases latest
    toolchain issues read tail/44
    toolchain issues tail list          # just the tail series
    toolchain issues                    # interactive browser (Ctrl+C to cancel)
    toolchain search "runtime security"

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

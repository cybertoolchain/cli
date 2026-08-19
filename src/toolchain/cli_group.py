# src/toolchain/cli_group.py
from __future__ import annotations

import re

import click

from .colors import PALETTES

_SECTION_HEADER_RE = re.compile(r"^(Usage|Options|Commands):", re.MULTILINE)
#: A help-text line naming one option/command: 2-space indent, the
#: name/flags, then a 2+ space gap before its description — how Click's
#: HelpFormatter lays out both the Options and Commands sections.
_ENTRY_LINE_RE = re.compile(r"^(  [-\w][-\w, ]*?)(\s{2,})(.*)$")


def set_mode_meta(ctx: click.Context, param: click.Parameter, value: str | None) -> str | None:
    """Eager --mode callback: stashes the color mode on ctx.meta so it's
    available to get_help() below, which (being tied to the eager --help
    option) runs before the group's own callback would otherwise set
    ctx.obj. An unrecognized value here is left for resolve_config to
    reject properly later — help output just falls back to sepia."""
    ctx.meta["mode"] = value if value in PALETTES else "sepia"
    return value


def colorize_help(text: str, mode: str) -> str:
    """Bold the section headers and the name column of each Options/Commands
    entry in Click's rendered help text, in the given mode's brand teal."""
    color = PALETTES[mode]["teal"]

    def header_repl(match: re.Match) -> str:
        return click.style(f"{match.group(1)}:", fg=color, bold=True)

    text = _SECTION_HEADER_RE.sub(header_repl, text)

    lines = []
    for line in text.split("\n"):
        entry = _ENTRY_LINE_RE.match(line)
        if entry:
            name, gap, rest = entry.groups()
            lines.append(click.style(name, fg=color) + gap + rest)
        else:
            lines.append(line)
    return "\n".join(lines)

GLOBAL_FLAGS: frozenset[str] = frozenset(
    {
        "-k", "--api-key",
        "--site",
        "-o", "--output",
        "-v", "--verbose",
        "--debug",
        "-c", "--cache",
        "-l", "--limit",
        "-s", "--short",
        "-t", "--timeout",
        "--search-fields",
        "--mode",
    }
)

#: Global flags that consume the following token as their value. Needed to
#: correctly find where the subcommand starts: a naive "first token not
#: starting with -" breaks the moment two global flags are combined and one
#: of them takes a value — `toolchain -o json -v tools list` would
#: otherwise see "json" as the subcommand and wrongly flag the
#: still-correctly-placed -v as misplaced. (Found in Task 11's review: the
#: plan's own first draft of this function had exactly that bug.)
_VALUE_FLAGS: frozenset[str] = frozenset(
    {
        "-k", "--api-key", "--site", "-o", "--output", "-l", "--limit",
        "-t", "--timeout", "--search-fields", "--mode",
    }
)


class GlobalOptionGroup(click.Group):
    """Detects a global flag used after the subcommand and prints a
    corrective example instead of a confusing per-subcommand parse error."""

    def get_help(self, ctx: click.Context) -> str:
        return colorize_help(super().get_help(ctx), ctx.meta.get("mode", "sepia"))

    def parse_args(self, ctx: click.Context, args: list[str]) -> list[str]:
        sub_idx = None
        i = 0
        while i < len(args):
            token = args[i]
            if token.startswith("-"):
                name = token.split("=", 1)[0]
                if name in _VALUE_FLAGS and "=" not in token:
                    i += 2  # skip the flag AND its separate value token
                    continue
                i += 1
                continue
            sub_idx = i
            break

        if sub_idx is not None:
            j = sub_idx + 1
            while j < len(args):
                token = args[j]
                name = token.split("=", 1)[0]
                if name in GLOBAL_FLAGS:
                    has_inline_value = "=" in token
                    consumes_next = name in _VALUE_FLAGS and not has_inline_value
                    # Everything the user actually typed, minus this
                    # misplaced flag (and its separate value token, if it
                    # had one) — the full path, not just up to the first
                    # subcommand word.
                    remainder = args[:j] + args[j + (2 if consumes_next else 1) :]
                    corrected_flag = f"{name} <value>" if name in _VALUE_FLAGS else name
                    example = f"toolchain {corrected_flag} {' '.join(remainder)}".rstrip()
                    raise click.UsageError(
                        f"'{name}' is a global option and must appear before the subcommand.\n\n"
                        "  toolchain [GLOBAL OPTIONS] GROUP COMMAND ...\n\n"
                        "Example:\n"
                        f"  {example}"
                    )
                j += 1
        return super().parse_args(ctx, args)

# src/toolchain/cli_group.py
from __future__ import annotations

import click

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
    {"-k", "--api-key", "--site", "-o", "--output", "-l", "--limit", "-t", "--timeout", "--search-fields"}
)


class GlobalOptionGroup(click.Group):
    """Detects a global flag used after the subcommand and prints a
    corrective example instead of a confusing per-subcommand parse error."""

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

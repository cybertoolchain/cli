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


class GlobalOptionGroup(click.Group):
    """Detects a global flag used after the subcommand and prints a
    corrective example instead of a confusing per-subcommand parse error."""

    def parse_args(self, ctx: click.Context, args: list[str]) -> list[str]:
        sub_idx = next((i for i, a in enumerate(args) if not a.startswith("-")), None)
        if sub_idx is not None:
            for token in args[sub_idx + 1 :]:
                name = token.split("=", 1)[0]
                if name in GLOBAL_FLAGS:
                    raise click.UsageError(
                        f"'{name}' is a global option and must appear before the subcommand.\n\n"
                        "  toolchain [GLOBAL OPTIONS] GROUP COMMAND ...\n\n"
                        "Example:\n"
                        f"  toolchain {name} <value> {' '.join(args[:sub_idx + 1])}"
                    )
        return super().parse_args(ctx, args)

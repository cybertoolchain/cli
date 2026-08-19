# src/toolchain/groups/version.py
from __future__ import annotations

import shutil
import subprocess

import click

from ..helpers import handle_errors
from ..models import ToolchainError
from ..versioning import current_version, update_available

_GIT_SPEC = "git+https://github.com/cybertoolchain/cli"


@click.command("version")
def version_command() -> None:
    """Show the installed version, and whether a newer one is published."""
    click.echo(f"toolchain-cli {current_version()}")
    newer = update_available()
    if newer:
        click.echo(
            f"A newer version is available: {newer}. Run 'toolchain update' to upgrade.",
            err=True,
        )


@click.command("update")
@handle_errors
def update_command() -> None:
    """Upgrade a global 'uv tool install' of this CLI to the latest commit
    on the default branch. Only works for that install method — an
    editable dev checkout is updated with 'git pull' instead."""
    if shutil.which("uv") is None:
        raise ToolchainError(
            "uv isn't on your PATH — install it (https://docs.astral.sh/uv/) or "
            f"reinstall manually: uv tool install --reinstall {_GIT_SPEC}"
        )
    click.echo(f"toolchain-cli {current_version()} — checking for updates...")
    result = subprocess.run(["uv", "tool", "upgrade", "toolchain-cli"])
    if result.returncode != 0:
        raise ToolchainError(
            "Upgrade failed. If this wasn't installed with 'uv tool install', run: "
            f"uv tool install --reinstall {_GIT_SPEC}"
        )

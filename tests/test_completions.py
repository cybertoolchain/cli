# tests/test_completions.py
from __future__ import annotations

from pathlib import Path

from click.shell_completion import BashComplete, ZshComplete

from toolchain.main import cli

COMPLETIONS = Path(__file__).parent.parent / "completions"


def test_bash_completion_file_matches_generated_source():
    generated = BashComplete(cli, {}, "toolchain", "_TOOLCHAIN_COMPLETE").source()
    committed = (COMPLETIONS / "toolchain.bash").read_text()
    assert committed == generated


def test_zsh_completion_file_matches_generated_source():
    generated = ZshComplete(cli, {}, "toolchain", "_TOOLCHAIN_COMPLETE").source()
    committed = (COMPLETIONS / "toolchain.zsh").read_text()
    assert committed == generated

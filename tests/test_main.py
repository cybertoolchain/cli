# tests/test_main.py
from __future__ import annotations

from click.testing import CliRunner

from toolchain.main import cli


def test_bare_invocation_prints_banner_and_hint_and_exits_0():
    runner = CliRunner()
    result = runner.invoke(cli, [])
    assert result.exit_code == 0
    assert "toolchain --help" in result.output or "tldr" in result.output


def test_tldr_command_prints_quick_reference():
    runner = CliRunner()
    result = runner.invoke(cli, ["tldr"])
    assert result.exit_code == 0
    assert "toolchain tools list" in result.output


def test_help_lists_the_command_groups():
    runner = CliRunner()
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert "tldr" in result.output


def test_unknown_site_flag_exits_1_with_message():
    runner = CliRunner()
    result = runner.invoke(cli, ["--site", "not-real", "tldr"])
    assert result.exit_code == 1
    assert "Unknown --site" in result.output

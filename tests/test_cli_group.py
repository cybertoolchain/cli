# tests/test_cli_group.py
from __future__ import annotations

import click
from click.testing import CliRunner

from toolchain.cli_group import GlobalOptionGroup


def _build_test_cli():
    @click.group(cls=GlobalOptionGroup)
    @click.option("-o", "--output", default="json")
    @click.option("-v", "--verbose", is_flag=True, default=False)
    def root(output, verbose):
        pass

    @root.group()
    def tools():
        pass

    @tools.command("list")
    def tools_list():
        click.echo("ok")

    return root


def test_global_flag_before_subcommand_works():
    runner = CliRunner()
    result = runner.invoke(_build_test_cli(), ["-o", "json", "tools", "list"])
    assert result.exit_code == 0
    assert "ok" in result.output


def test_global_flag_after_subcommand_is_rejected():
    runner = CliRunner()
    result = runner.invoke(_build_test_cli(), ["tools", "list", "-o", "json"])
    assert result.exit_code != 0
    assert "global option" in result.output
    assert "must appear before the subcommand" in result.output


def test_error_message_shows_a_corrective_example():
    runner = CliRunner()
    result = runner.invoke(_build_test_cli(), ["tools", "list", "-o", "json"])
    assert "toolchain -o <value> tools list" in result.output or "-o <value>" in result.output


def test_unrelated_subcommand_option_is_unaffected():
    runner = CliRunner()
    result = runner.invoke(_build_test_cli(), ["tools", "list"])
    assert result.exit_code == 0


def test_two_correctly_placed_global_flags_are_not_rejected():
    # Regression test: a naive "first token not starting with -" boundary
    # search lands on "json" (the VALUE of -o) instead of "tools", and then
    # wrongly flags the still-correctly-placed -v as misplaced.
    runner = CliRunner()
    result = runner.invoke(_build_test_cli(), ["-o", "json", "-v", "tools", "list"])
    assert result.exit_code == 0
    assert "ok" in result.output

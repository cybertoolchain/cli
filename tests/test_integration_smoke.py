from __future__ import annotations

from click.testing import CliRunner

from toolchain.main import cli


def test_help_lists_every_command_group():
    result = CliRunner().invoke(cli, ["--help"])
    assert result.exit_code == 0
    for name in ["tools", "releases", "categories", "issues", "analytics", "search", "tldr"]:
        assert name in result.output


def test_every_group_help_exits_zero():
    runner = CliRunner()
    for group in ["tools", "releases", "categories", "issues", "analytics"]:
        result = runner.invoke(cli, [group, "--help"])
        assert result.exit_code == 0, f"{group} --help failed: {result.output}"


def test_key_only_commands_all_state_the_requirement_in_help():
    runner = CliRunner()
    for args in (["tools", "sbom", "--help"],):
        result = runner.invoke(cli, args)
        assert "requires an API key" in result.output


def test_global_flag_after_subcommand_is_still_rejected_end_to_end():
    result = CliRunner().invoke(cli, ["tools", "list", "-k", "ctk_x"])
    assert result.exit_code != 0
    assert "global option" in result.output

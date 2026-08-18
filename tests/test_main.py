# tests/test_main.py
from __future__ import annotations

import click
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


def test_help_command_matches_dash_dash_help():
    runner = CliRunner()
    result = runner.invoke(cli, ["help"])
    assert result.exit_code == 0
    assert "tldr" in result.output
    assert "Usage: cli" in result.output or "Usage:" in result.output


def test_bare_invocation_shows_brand_wordmark():
    runner = CliRunner()
    result = runner.invoke(cli, [])
    assert result.exit_code == 0
    assert "┌┬┐" in result.output


def test_bare_invocation_wordmark_omits_cyber():
    from toolchain.main import _LOGO_LINES

    assert "┌─┐┬ ┬┌┐" not in "".join(_LOGO_LINES)  # the dropped "cyber" block


def test_render_icon_produces_half_block_art():
    from toolchain.main import render_icon

    icon = render_icon("dark")
    lines = icon.split("\n")
    assert len(lines) == 14  # 28px asset, 2 rows per half-block character
    assert any("▀" in line or "▄" in line for line in lines)


def test_render_icon_recolors_per_mode():
    from toolchain.main import render_icon

    dark = render_icon("dark")
    contrast = render_icon("contrast")
    assert dark != contrast


def test_render_tldr_colors_the_command_examples():
    from toolchain.main import render_tldr

    dark = render_tldr("dark")
    contrast = render_tldr("contrast")
    assert dark != contrast
    assert "toolchain tools list" in click.unstyle(dark)


def test_tldr_command_is_colored_by_mode():
    runner = CliRunner()
    sepia = runner.invoke(cli, ["--mode", "sepia", "tldr"], color=True)
    contrast = runner.invoke(cli, ["--mode", "contrast", "tldr"], color=True)
    assert sepia.output != contrast.output
    assert click.unstyle(sepia.output) == click.unstyle(contrast.output)


def test_render_banner_places_icon_beside_the_wordmark():
    from toolchain.main import render_banner

    banner = render_banner("dark")
    lines = banner.strip("\n").split("\n")
    assert len(lines) == 14
    assert "┌┬┐" in "".join(lines)


def test_mode_defaults_to_dark_and_is_accepted():
    runner = CliRunner()
    for mode in ("dark", "light", "sepia", "contrast"):
        result = runner.invoke(cli, ["--mode", mode])
        assert result.exit_code == 0, result.output


def test_invalid_mode_exits_1_with_message():
    runner = CliRunner()
    result = runner.invoke(cli, ["--mode", "neon"])
    assert result.exit_code == 1
    assert "Unknown --mode" in result.output


def test_unknown_site_flag_exits_1_with_message():
    runner = CliRunner()
    result = runner.invoke(cli, ["--site", "not-real", "tldr"])
    assert result.exit_code == 1
    assert "Unknown --site" in result.output


def test_tools_group_is_registered():
    from click.testing import CliRunner

    result = CliRunner().invoke(cli, ["tools", "--help"])
    assert result.exit_code == 0
    assert "list" in result.output

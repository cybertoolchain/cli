# tests/test_group_version.py
from __future__ import annotations

from click.testing import CliRunner

from toolchain.main import cli


def test_version_command_prints_the_installed_version(monkeypatch):
    monkeypatch.setattr("toolchain.groups.version.current_version", lambda: "1.2.3")
    monkeypatch.setattr("toolchain.groups.version.update_available", lambda: None)
    result = CliRunner().invoke(cli, ["version"])
    assert result.exit_code == 0
    assert result.stdout == "toolchain-cli 1.2.3\n"
    assert result.stderr == ""


def test_version_command_checks_every_time_and_warns_on_stderr(monkeypatch):
    checked = []
    monkeypatch.setattr("toolchain.groups.version.current_version", lambda: "1.2.3")
    monkeypatch.setattr(
        "toolchain.groups.version.update_available", lambda: checked.append(1) or "1.3.0"
    )
    result = CliRunner().invoke(cli, ["version"])
    assert result.exit_code == 0
    assert checked == [1]  # the check ran unconditionally, no flag needed
    assert result.stdout == "toolchain-cli 1.2.3\n"
    assert "1.3.0" in result.stderr
    assert "toolchain update" in result.stderr


def test_update_command_runs_uv_tool_upgrade(monkeypatch):
    calls = []

    class FakeCompleted:
        returncode = 0

    monkeypatch.setattr("toolchain.groups.version.shutil.which", lambda name: "/usr/bin/uv")
    monkeypatch.setattr("toolchain.groups.version.current_version", lambda: "1.2.3")

    def fake_run(args, **kwargs):
        calls.append(args)
        return FakeCompleted()

    monkeypatch.setattr("toolchain.groups.version.subprocess.run", fake_run)
    result = CliRunner().invoke(cli, ["update"])
    assert result.exit_code == 0
    assert calls == [["uv", "tool", "upgrade", "toolchain-cli"]]


def test_update_command_errors_when_uv_is_not_on_path(monkeypatch):
    monkeypatch.setattr("toolchain.groups.version.shutil.which", lambda name: None)
    result = CliRunner().invoke(cli, ["update"])
    assert result.exit_code != 0
    assert "uv isn't on your PATH" in result.output


def test_update_command_errors_when_the_upgrade_fails(monkeypatch):
    class FakeCompleted:
        returncode = 1

    monkeypatch.setattr("toolchain.groups.version.shutil.which", lambda name: "/usr/bin/uv")
    monkeypatch.setattr("toolchain.groups.version.current_version", lambda: "1.2.3")
    monkeypatch.setattr("toolchain.groups.version.subprocess.run", lambda *a, **k: FakeCompleted())
    result = CliRunner().invoke(cli, ["update"])
    assert result.exit_code != 0
    assert "Upgrade failed" in result.output

# tests/test_group_tools.py
from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from toolchain.main import cli

FIXTURES = Path(__file__).parent / "fixtures"


def load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text())


def test_tools_list_uses_site_source_with_no_key(monkeypatch):
    site_data = load("site_tools.json")

    class StubSource:
        def fetch(self, path, **params):
            assert path == "tools.json"
            return site_data

    monkeypatch.setattr("toolchain.groups.tools.resolve_source", lambda config: StubSource())
    result = CliRunner().invoke(cli, ["tools", "list"])
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["count"] == 2
    assert payload["tools"][0]["tool"] == "Nmap"


def test_tools_list_uses_api_source_with_key(monkeypatch):
    api_data = load("api_tools_list.json")

    class StubSource:
        def fetch(self, path, **params):
            assert path == "tools"
            return api_data

    monkeypatch.setattr("toolchain.groups.tools.resolve_source", lambda config: StubSource())
    result = CliRunner().invoke(cli, ["-k", "ctk_live_abc", "tools", "list"])
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["total"] == 2
    assert payload["tools"][0]["slug"] == "nmap"


def test_tools_list_passes_filters_as_params(monkeypatch):
    captured = {}

    class StubSource:
        def fetch(self, path, **params):
            captured.update(params)
            return {"tools": []}

    monkeypatch.setattr("toolchain.groups.tools.resolve_source", lambda config: StubSource())
    CliRunner().invoke(cli, ["tools", "list", "--category", "reconnaissance", "--q", "scan"])
    assert captured["category"] == "reconnaissance"
    assert captured["q"] == "scan"


def test_tools_count(monkeypatch):
    api_data = load("api_tools_count.json")

    class StubSource:
        def fetch(self, path, **params):
            assert path == "tools/count"
            return api_data

    monkeypatch.setattr("toolchain.groups.tools.resolve_source", lambda config: StubSource())
    result = CliRunner().invoke(cli, ["-k", "ctk_live_abc", "tools", "count"])
    assert result.exit_code == 0
    assert json.loads(result.output)["total"] == 836


def test_tools_get_no_key_finds_tool_by_name_in_site_data(monkeypatch):
    site_data = load("site_tools.json")

    class StubSource:
        def fetch(self, path, **params):
            assert path == "tools.json"
            return site_data

    monkeypatch.setattr("toolchain.groups.tools.resolve_source", lambda config: StubSource())
    result = CliRunner().invoke(cli, ["tools", "get", "nmap"])
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["tool"] == "Nmap"


def test_tools_get_no_key_unknown_slug_is_user_input_error(monkeypatch):
    site_data = load("site_tools.json")

    class StubSource:
        def fetch(self, path, **params):
            return site_data

    monkeypatch.setattr("toolchain.groups.tools.resolve_source", lambda config: StubSource())
    result = CliRunner().invoke(cli, ["tools", "get", "not-a-real-tool"])
    assert result.exit_code == 1
    assert "not-a-real-tool" in result.output


def test_tools_get_with_key_uses_v1_slug_path(monkeypatch):
    api_data = load("api_tools_detail.json")

    class StubSource:
        def fetch(self, path, **params):
            assert path == "tools/nmap"
            return api_data

    monkeypatch.setattr("toolchain.groups.tools.resolve_source", lambda config: StubSource())
    result = CliRunner().invoke(cli, ["-k", "ctk_live_abc", "tools", "get", "nmap"])
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["latest_release"]["version"] == "commits-2026-07-11"

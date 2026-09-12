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


def test_tools_list_passes_filters_as_params_keyed_path(monkeypatch):
    captured = {}

    class StubSource:
        def fetch(self, path, **params):
            captured.update(params)
            return {"tools": []}

    monkeypatch.setattr("toolchain.groups.tools.resolve_source", lambda config: StubSource())
    CliRunner().invoke(
        cli, ["-k", "ctk_live_abc", "tools", "list", "--category", "reconnaissance", "--q", "scan"]
    )
    assert captured["category"] == "reconnaissance"
    assert captured["q"] == "scan"


def test_tools_list_no_key_filters_client_side_by_category(monkeypatch):
    site_data = load("site_tools.json")

    class StubSource:
        def fetch(self, path, **params):
            assert path == "tools.json"
            return site_data

    monkeypatch.setattr("toolchain.groups.tools.resolve_source", lambda config: StubSource())
    result = CliRunner().invoke(cli, ["tools", "list", "--category", "reconnaissance"])
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert len(payload["tools"]) == 1
    assert payload["tools"][0]["tool"] == "Nmap"


def test_tools_list_no_key_filters_client_side_by_q(monkeypatch):
    site_data = load("site_tools.json")

    class StubSource:
        def fetch(self, path, **params):
            return site_data

    monkeypatch.setattr("toolchain.groups.tools.resolve_source", lambda config: StubSource())
    result = CliRunner().invoke(cli, ["tools", "list", "--q", "falco"])
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert len(payload["tools"]) == 1
    assert payload["tools"][0]["tool"] == "Falco"


def test_tools_list_no_key_filters_client_side_by_license(monkeypatch):
    site_data = load("site_tools.json")
    # Both fixture rows are open_source: true — flip one to exercise the
    # commercial branch and confirm license filtering actually narrows.
    site_data["tools"][1]["open_source"] = False

    class StubSource:
        def fetch(self, path, **params):
            return site_data

    monkeypatch.setattr("toolchain.groups.tools.resolve_source", lambda config: StubSource())
    result = CliRunner().invoke(cli, ["tools", "list", "--license", "commercial"])
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert len(payload["tools"]) == 1
    assert payload["tools"][0]["tool"] == "Falco"


def test_tools_list_no_key_ignores_cursor(monkeypatch):
    site_data = load("site_tools.json")

    class StubSource:
        def fetch(self, path, **params):
            return site_data

    monkeypatch.setattr("toolchain.groups.tools.resolve_source", lambda config: StubSource())
    result = CliRunner().invoke(cli, ["tools", "list", "--cursor", "anything"])
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert len(payload["tools"]) == 2


def test_tools_count_with_key_uses_v1_count_path(monkeypatch):
    api_data = load("api_tools_count.json")

    class StubSource:
        def fetch(self, path, **params):
            assert path == "tools/count"
            return api_data

    monkeypatch.setattr("toolchain.groups.tools.resolve_source", lambda config: StubSource())
    result = CliRunner().invoke(cli, ["-k", "ctk_live_abc", "tools", "count"])
    assert result.exit_code == 0
    assert json.loads(result.output)["total"] == 836


def test_tools_count_no_key_counts_the_site_snapshot(monkeypatch):
    site_data = load("site_tools.json")

    class StubSource:
        def fetch(self, path, **params):
            assert path == "tools.json"
            return site_data

    monkeypatch.setattr("toolchain.groups.tools.resolve_source", lambda config: StubSource())
    result = CliRunner().invoke(cli, ["tools", "count"])
    assert result.exit_code == 0
    assert json.loads(result.output)["total"] == 2


def test_tools_count_no_key_applies_the_same_filters_as_tools_list(monkeypatch):
    site_data = load("site_tools.json")

    class StubSource:
        def fetch(self, path, **params):
            return site_data

    monkeypatch.setattr("toolchain.groups.tools.resolve_source", lambda config: StubSource())
    result = CliRunner().invoke(cli, ["tools", "count", "--category", "reconnaissance"])
    assert result.exit_code == 0
    assert json.loads(result.output)["total"] == 1


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


def test_tools_releases_no_key_reads_the_tools_own_entries_file(monkeypatch):
    # /entries.json (the whole corpus in one request) is gone; the site
    # publishes each tool's history at /tool-entries/<slug>.json.
    entries = load("site_entries.json")

    class StubSource:
        def fetch(self, path, **params):
            assert path == "tool-entries/nmap.json"
            return [row for row in entries if row["name"] == "nmap"]

    monkeypatch.setattr("toolchain.groups.tools.resolve_source", lambda config: StubSource())
    result = CliRunner().invoke(cli, ["tools", "releases", "Nmap"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert len(payload) == 2
    assert all(row["name"] == "nmap" for row in payload)


def test_tools_releases_no_key_unknown_slug_is_user_input_error(monkeypatch):
    from toolchain.models import APIError

    class StubSource:
        def fetch(self, path, **params):
            assert path == "tool-entries/not-a-real-tool.json"
            raise APIError(f"404 fetching https://cybertoolchain.io/{path}")

    monkeypatch.setattr("toolchain.groups.tools.resolve_source", lambda config: StubSource())
    result = CliRunner().invoke(cli, ["tools", "releases", "not-a-real-tool"])
    assert result.exit_code == 1
    assert "not-a-real-tool" in result.output


def test_tools_releases_no_key_tool_with_nothing_published_is_user_input_error(monkeypatch):
    class StubSource:
        def fetch(self, path, **params):
            return []

    monkeypatch.setattr("toolchain.groups.tools.resolve_source", lambda config: StubSource())
    result = CliRunner().invoke(cli, ["tools", "releases", "quiet-tool"])
    assert result.exit_code == 1
    assert "quiet-tool" in result.output


def test_tools_releases_with_key_uses_v1_path(monkeypatch):
    class StubSource:
        def fetch(self, path, **params):
            assert path == "tools/nmap/releases"
            return {"releases": [], "next_cursor": None}

    monkeypatch.setattr("toolchain.groups.tools.resolve_source", lambda config: StubSource())
    result = CliRunner().invoke(cli, ["-k", "ctk_live_abc", "tools", "releases", "nmap"])
    assert result.exit_code == 0


def test_tools_api_no_key_reads_tool_apis_json(monkeypatch):
    apis = load("site_tool_apis.json")

    class StubSource:
        def fetch(self, path, **params):
            assert path == "tool-apis.json"
            return apis

    monkeypatch.setattr("toolchain.groups.tools.resolve_source", lambda config: StubSource())
    result = CliRunner().invoke(cli, ["tools", "api", "1Password"])
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["spec_version"] == "1.8.1"


def test_tools_api_no_key_unknown_tool_is_user_input_error(monkeypatch):
    apis = load("site_tool_apis.json")

    class StubSource:
        def fetch(self, path, **params):
            return apis

    monkeypatch.setattr("toolchain.groups.tools.resolve_source", lambda config: StubSource())
    result = CliRunner().invoke(cli, ["tools", "api", "nmap"])
    assert result.exit_code == 1
    assert "no published API" in result.output


def test_tools_examples_no_key_reads_cli_explains_json(monkeypatch):
    explains = load("site_cli_explains.json")

    class StubSource:
        def fetch(self, path, **params):
            assert path == "cli-explains.json"
            return explains

    monkeypatch.setattr("toolchain.groups.tools.resolve_source", lambda config: StubSource())
    result = CliRunner().invoke(cli, ["tools", "examples", "Aircrack-ng"])
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert "t-opt-fe24a716" in payload


def test_tools_examples_with_key_uses_v1_cli_path(monkeypatch):
    class StubSource:
        def fetch(self, path, **params):
            assert path == "tools/nmap/cli"
            return {"examples": []}

    monkeypatch.setattr("toolchain.groups.tools.resolve_source", lambda config: StubSource())
    result = CliRunner().invoke(cli, ["-k", "ctk_live_abc", "tools", "examples", "nmap"])
    assert result.exit_code == 0


def test_tools_stack_no_key_reads_tool_code_json(monkeypatch):
    code = load("site_tool_code.json")

    class StubSource:
        def fetch(self, path, **params):
            assert path == "toolCode.json"
            return code

    monkeypatch.setattr("toolchain.groups.tools.resolve_source", lambda config: StubSource())
    result = CliRunner().invoke(cli, ["tools", "stack", "ADR"])
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["deps"]["direct"] == 73


def test_tools_stack_no_key_unknown_tool_is_user_input_error(monkeypatch):
    code = load("site_tool_code.json")

    class StubSource:
        def fetch(self, path, **params):
            return code

    monkeypatch.setattr("toolchain.groups.tools.resolve_source", lambda config: StubSource())
    result = CliRunner().invoke(cli, ["tools", "stack", "not-a-tool"])
    assert result.exit_code == 1


def test_tools_stack_with_key_uses_v1_path(monkeypatch):
    class StubSource:
        def fetch(self, path, **params):
            assert path == "tools/nmap/stack"
            return {}

    monkeypatch.setattr("toolchain.groups.tools.resolve_source", lambda config: StubSource())
    result = CliRunner().invoke(cli, ["-k", "ctk_live_abc", "tools", "stack", "nmap"])
    assert result.exit_code == 0


def test_tools_sbom_with_no_key_requires_api_key():
    result = CliRunner().invoke(cli, ["tools", "sbom", "nmap"])
    assert result.exit_code == 1
    assert "requires an API key" in result.output


def test_tools_sbom_with_key_uses_v1_path(monkeypatch):
    class StubSource:
        def fetch(self, path, **params):
            assert path == "tools/nmap/sbom"
            return {"components": []}

    monkeypatch.setattr("toolchain.groups.tools.resolve_source", lambda config: StubSource())
    result = CliRunner().invoke(cli, ["-k", "ctk_live_abc", "tools", "sbom", "nmap"])
    assert result.exit_code == 0


def test_tools_sbom_help_states_the_key_requirement():
    result = CliRunner().invoke(cli, ["tools", "sbom", "--help"])
    assert "requires an API key" in result.output


def test_tools_browse_is_registered_and_has_help():
    result = CliRunner().invoke(cli, ["tools", "browse", "--help"])
    assert result.exit_code == 0
    assert "Interactively" in result.output

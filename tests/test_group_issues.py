from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from toolchain.main import cli

FIXTURES = Path(__file__).parent / "fixtures"


def load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text())


def test_issues_list_no_key_groups_entries_by_issue_slug(monkeypatch):
    entries = load("site_entries.json")

    class StubSource:
        def fetch(self, path, **params):
            assert path == "entries.json"
            return entries

    monkeypatch.setattr("toolchain.groups.issues.resolve_source", lambda config: StubSource())
    result = CliRunner().invoke(cli, ["issues", "list"])
    assert result.exit_code == 0
    payload = json.loads(result.output)
    slugs = {row["issue_slug"] for row in payload}
    assert slugs == {"tail/44", "tail/38", "tail/42"}


def test_issues_list_filters_by_series(monkeypatch):
    entries = load("site_entries.json")

    class StubSource:
        def fetch(self, path, **params):
            return entries

    monkeypatch.setattr("toolchain.groups.issues.resolve_source", lambda config: StubSource())
    result = CliRunner().invoke(cli, ["issues", "list", "--series", "tail"])
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert all(row["issue_slug"].startswith("tail/") for row in payload)


def test_issues_list_with_key_uses_v1_path(monkeypatch):
    class StubSource:
        def fetch(self, path, **params):
            assert path == "issues"
            return {"issues": [], "next_cursor": None}

    monkeypatch.setattr("toolchain.groups.issues.resolve_source", lambda config: StubSource())
    result = CliRunner().invoke(cli, ["-k", "ctk_live_abc", "issues", "list"])
    assert result.exit_code == 0


def test_issues_get_no_key_returns_matching_entries(monkeypatch):
    entries = load("site_entries.json")

    class StubSource:
        def fetch(self, path, **params):
            return entries

    monkeypatch.setattr("toolchain.groups.issues.resolve_source", lambda config: StubSource())
    result = CliRunner().invoke(cli, ["issues", "get", "tail/44"])
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert len(payload) == 1
    assert payload[0]["tool"] == "Nmap"


def test_issues_get_no_key_unknown_issue_is_user_input_error(monkeypatch):
    entries = load("site_entries.json")

    class StubSource:
        def fetch(self, path, **params):
            return entries

    monkeypatch.setattr("toolchain.groups.issues.resolve_source", lambda config: StubSource())
    result = CliRunner().invoke(cli, ["issues", "get", "tail/999"])
    assert result.exit_code == 1


def test_issues_get_with_key_uses_v1_path(monkeypatch):
    class StubSource:
        def fetch(self, path, **params):
            assert path == "issues/044"
            return {"issue": "044", "entries": []}

    monkeypatch.setattr("toolchain.groups.issues.resolve_source", lambda config: StubSource())
    result = CliRunner().invoke(cli, ["-k", "ctk_live_abc", "issues", "get", "044"])
    assert result.exit_code == 0


def test_issues_download_json_no_key_matches_issues_get(monkeypatch):
    entries = load("site_entries.json")

    class StubSource:
        def fetch(self, path, **params):
            return entries

    monkeypatch.setattr("toolchain.groups.issues.resolve_source", lambda config: StubSource())
    result = CliRunner().invoke(cli, ["issues", "download", "tail/44", "--format", "json"])
    assert result.exit_code == 0
    assert json.loads(result.output)[0]["tool"] == "Nmap"


def test_issues_download_html_no_key_fetches_the_rendered_page(monkeypatch):
    class StubSource:
        def fetch_text(self, path, **params):
            assert path == "newsletter/tail/44"
            return "<html>issue 44</html>"

    monkeypatch.setattr("toolchain.groups.issues.resolve_source", lambda config: StubSource())
    result = CliRunner().invoke(cli, ["issues", "download", "tail/44", "--format", "html"])
    assert result.exit_code == 0
    assert "<html>issue 44</html>" in result.output


def test_issues_download_html_bare_number_is_rejected_no_key():
    result = CliRunner().invoke(cli, ["issues", "download", "44", "--format", "html"])
    assert result.exit_code == 1
    assert "issues list" in result.output


def test_issues_download_requires_format():
    result = CliRunner().invoke(cli, ["issues", "download", "tail/44"])
    assert result.exit_code != 0


def test_issues_download_with_key_uses_v1_path(monkeypatch):
    class StubSource:
        def fetch(self, path, **params):
            assert path == "issues/044/download"
            assert params == {"format": "json"}
            return {"issue": "044"}

    monkeypatch.setattr("toolchain.groups.issues.resolve_source", lambda config: StubSource())
    result = CliRunner().invoke(
        cli, ["-k", "ctk_live_abc", "issues", "download", "044", "--format", "json"]
    )
    assert result.exit_code == 0

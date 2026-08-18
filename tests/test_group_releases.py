from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from toolchain.main import cli

FIXTURES = Path(__file__).parent / "fixtures"


def load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text())


def test_releases_list_no_key_reads_entries_json(monkeypatch):
    entries = load("site_entries.json")

    class StubSource:
        def fetch(self, path, **params):
            assert path == "entries.json"
            return entries

    monkeypatch.setattr("toolchain.groups.releases.resolve_source", lambda config: StubSource())
    result = CliRunner().invoke(cli, ["releases", "list"])
    assert result.exit_code == 0
    assert len(json.loads(result.output)) == 3


def test_releases_list_filters_by_tools(monkeypatch):
    entries = load("site_entries.json")

    class StubSource:
        def fetch(self, path, **params):
            return entries

    monkeypatch.setattr("toolchain.groups.releases.resolve_source", lambda config: StubSource())
    result = CliRunner().invoke(cli, ["releases", "list", "--tools", "falco"])
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert len(payload) == 1
    assert payload[0]["name"] == "falco"


def test_releases_list_filters_by_categories(monkeypatch):
    entries = load("site_entries.json")

    class StubSource:
        def fetch(self, path, **params):
            return entries

    monkeypatch.setattr("toolchain.groups.releases.resolve_source", lambda config: StubSource())
    result = CliRunner().invoke(cli, ["releases", "list", "--categories", "runtime-security"])
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert all(row["category"] == "runtime-security" for row in payload)


def test_releases_list_with_key_uses_v1_path(monkeypatch):
    class StubSource:
        def fetch(self, path, **params):
            assert path == "releases"
            return {"releases": [], "next_cursor": None}

    monkeypatch.setattr("toolchain.groups.releases.resolve_source", lambda config: StubSource())
    result = CliRunner().invoke(cli, ["-k", "ctk_live_abc", "releases", "list"])
    assert result.exit_code == 0


def test_releases_latest_sorts_newest_first_and_applies_default_limit(monkeypatch):
    entries = load("site_entries.json")

    class StubSource:
        def fetch(self, path, **params):
            return entries

    monkeypatch.setattr("toolchain.groups.releases.resolve_source", lambda config: StubSource())
    result = CliRunner().invoke(cli, ["releases", "latest"])
    assert result.exit_code == 0
    payload = json.loads(result.output)
    dates = [row["published_at"] for row in payload]
    assert dates == sorted(dates, reverse=True)


def test_releases_latest_limit_flag(monkeypatch):
    # --limit is the GLOBAL flag (Task 3/12) — there is no per-command
    # --limit anywhere in this CLI, precisely to avoid colliding with it
    # under GlobalOptionGroup (see Task 11's ledger: a bare "--limit" after
    # the subcommand is indistinguishable from a misplaced global flag).
    # So it goes BEFORE the subcommand here, like every other global flag.
    entries = load("site_entries.json")

    class StubSource:
        def fetch(self, path, **params):
            return entries

    monkeypatch.setattr("toolchain.groups.releases.resolve_source", lambda config: StubSource())
    result = CliRunner().invoke(cli, ["--limit", "1", "releases", "latest"])
    assert result.exit_code == 0
    assert len(json.loads(result.output)) == 1


def test_releases_list_limit_flag(monkeypatch):
    entries = load("site_entries.json")

    class StubSource:
        def fetch(self, path, **params):
            return entries

    monkeypatch.setattr("toolchain.groups.releases.resolve_source", lambda config: StubSource())
    result = CliRunner().invoke(cli, ["--limit", "2", "releases", "list"])
    assert result.exit_code == 0
    assert len(json.loads(result.output)) == 2

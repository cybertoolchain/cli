from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from toolchain.main import cli
from toolchain.models import APIError

FIXTURES = Path(__file__).parent / "fixtures"


def load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text())


class SiteSource:
    """The free site as it is now: one release per tool in /tools.json, and a
    tool's full published history at /tool-entries/<slug>.json. /entries.json
    is gone (404) — it served the whole corpus in one request."""

    def __init__(self):
        self.paths = []

    def fetch(self, path, **params):
        self.paths.append(path)
        if path == "tools.json":
            return load("site_tools_feed.json")
        if path.startswith("tool-entries/") and path.endswith(".json"):
            slug = path[len("tool-entries/"):-len(".json")]
            rows = [row for row in load("site_entries.json") if row["name"] == slug]
            if not rows:
                raise APIError(f"404 fetching https://cybertoolchain.io/{path}")
            return rows
        raise APIError(f"404 fetching https://cybertoolchain.io/{path}")


def test_releases_list_no_key_reads_the_newest_release_per_tool(monkeypatch):
    source = SiteSource()
    monkeypatch.setattr("toolchain.groups.releases.resolve_source", lambda config: source)
    result = CliRunner().invoke(cli, ["releases", "list"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert source.paths == ["tools.json"]
    # Two tools in the fixture; Nmap has two entries and lists once.
    assert [row["tool"] for row in payload] == ["Nmap", "Falco"]


def test_releases_list_filters_by_tools_reads_each_tools_history(monkeypatch):
    source = SiteSource()
    monkeypatch.setattr("toolchain.groups.releases.resolve_source", lambda config: source)
    result = CliRunner().invoke(cli, ["releases", "list", "--tools", "Nmap,falco"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert source.paths == ["tool-entries/nmap.json", "tool-entries/falco.json"]
    assert [row["name"] for row in payload] == ["nmap", "nmap", "falco"]


def test_releases_list_unknown_tool_is_user_input_error(monkeypatch):
    monkeypatch.setattr("toolchain.groups.releases.resolve_source", lambda config: SiteSource())
    result = CliRunner().invoke(cli, ["releases", "list", "--tools", "not-a-real-tool"])
    assert result.exit_code == 1
    assert "not-a-real-tool" in result.output


def test_releases_list_filters_by_categories(monkeypatch):
    monkeypatch.setattr("toolchain.groups.releases.resolve_source", lambda config: SiteSource())
    result = CliRunner().invoke(cli, ["releases", "list", "--categories", "runtime-security"])
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload and all(row["category"] == "runtime-security" for row in payload)


def test_releases_list_with_key_uses_v1_path(monkeypatch):
    class StubSource:
        def fetch(self, path, **params):
            assert path == "releases"
            return {"releases": [], "next_cursor": None}

    monkeypatch.setattr("toolchain.groups.releases.resolve_source", lambda config: StubSource())
    result = CliRunner().invoke(cli, ["-k", "ctk_live_abc", "releases", "list"])
    assert result.exit_code == 0


def test_releases_latest_sorts_newest_first_and_applies_default_limit(monkeypatch):
    monkeypatch.setattr("toolchain.groups.releases.resolve_source", lambda config: SiteSource())
    result = CliRunner().invoke(cli, ["releases", "latest"])
    assert result.exit_code == 0
    payload = json.loads(result.output)
    dates = [row["published_at"] for row in payload]
    assert dates and dates == sorted(dates, reverse=True)


def test_releases_latest_limit_flag(monkeypatch):
    # --limit is the GLOBAL flag (Task 3/12) — there is no per-command
    # --limit anywhere in this CLI, precisely to avoid colliding with it
    # under GlobalOptionGroup (see Task 11's ledger: a bare "--limit" after
    # the subcommand is indistinguishable from a misplaced global flag).
    # So it goes BEFORE the subcommand here, like every other global flag.
    monkeypatch.setattr("toolchain.groups.releases.resolve_source", lambda config: SiteSource())
    result = CliRunner().invoke(cli, ["--limit", "1", "releases", "latest"])
    assert result.exit_code == 0
    assert len(json.loads(result.output)) == 1


def test_releases_list_limit_flag(monkeypatch):
    monkeypatch.setattr("toolchain.groups.releases.resolve_source", lambda config: SiteSource())
    result = CliRunner().invoke(cli, ["--limit", "1", "releases", "list", "--tools", "nmap"])
    assert result.exit_code == 0
    assert len(json.loads(result.output)) == 1

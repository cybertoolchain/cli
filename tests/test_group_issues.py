from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from toolchain.main import cli

FIXTURES = Path(__file__).parent / "fixtures"


def load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text())


# The free site retired /entries.json (it served the whole corpus in one
# request) for per-tool /tool-entries/<slug>.json. Nothing free is keyed by
# issue any more: the list comes from the site's search index, and reading an
# issue's entries needs a key.


class IndexSource:
    def __init__(self):
        self.paths = []

    def fetch(self, path, **params):
        self.paths.append(path)
        assert path == "search-index.json", path
        return load("site_search_index_issues.json")


def test_issues_list_no_key_reads_the_site_search_index(monkeypatch):
    source = IndexSource()
    monkeypatch.setattr("toolchain.groups.issues.resolve_source", lambda config: source)
    result = CliRunner().invoke(cli, ["issues", "list"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert {row["issue_slug"] for row in payload} == {"tail/44", "tail/38", "tail/42"}
    row = next(r for r in payload if r["issue_slug"] == "tail/44")
    assert row == {"issue_slug": "tail/44", "label": "Issue 044", "tools": 1}
    assert source.paths == ["search-index.json"]


def test_issues_list_filters_by_series(monkeypatch):
    monkeypatch.setattr("toolchain.groups.issues.resolve_source", lambda config: IndexSource())
    result = CliRunner().invoke(cli, ["issues", "list", "--series", "tail"])
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload and all(row["issue_slug"].startswith("tail/") for row in payload)
    # Head and Diff are not in the site's index, so the honest answer is empty.
    result = CliRunner().invoke(cli, ["issues", "list", "--series", "head"])
    assert result.exit_code == 0
    assert json.loads(result.output) == []


def test_issues_list_with_key_uses_v1_path(monkeypatch):
    class StubSource:
        def fetch(self, path, **params):
            assert path == "issues"
            return {"issues": [], "next_cursor": None}

    monkeypatch.setattr("toolchain.groups.issues.resolve_source", lambda config: StubSource())
    result = CliRunner().invoke(cli, ["-k", "ctk_live_abc", "issues", "list"])
    assert result.exit_code == 0


class NeverFetched:
    def fetch(self, path, **params):
        raise AssertionError(f"no free endpoint serves an issue's entries; fetched {path}")


def test_issues_get_no_key_says_a_key_is_needed(monkeypatch):
    monkeypatch.setattr("toolchain.groups.issues.resolve_source", lambda config: NeverFetched())
    result = CliRunner().invoke(cli, ["issues", "get", "tail/44"])
    assert result.exit_code == 1
    assert "API key" in result.output
    assert "tools releases" in result.output
    assert "--format html" in result.output


def test_issues_get_with_key_uses_v1_path(monkeypatch):
    class StubSource:
        def fetch(self, path, **params):
            assert path == "issues/044"
            return {"issue": "044", "entries": []}

    monkeypatch.setattr("toolchain.groups.issues.resolve_source", lambda config: StubSource())
    result = CliRunner().invoke(cli, ["-k", "ctk_live_abc", "issues", "get", "044"])
    assert result.exit_code == 0


def test_issues_download_json_no_key_says_a_key_is_needed(monkeypatch):
    monkeypatch.setattr("toolchain.groups.issues.resolve_source", lambda config: NeverFetched())
    result = CliRunner().invoke(cli, ["issues", "download", "tail/44", "--format", "json"])
    assert result.exit_code == 1
    assert "API key" in result.output


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


def test_issues_read_no_key_says_a_key_is_needed(monkeypatch):
    monkeypatch.setattr("toolchain.groups.issues.resolve_source", lambda config: NeverFetched())
    result = CliRunner().invoke(cli, ["issues", "read", "tail/44"])
    assert result.exit_code == 1
    assert "API key" in result.output


def test_issues_read_with_key_renders_markdown(monkeypatch):
    entries = load("site_entries.json")

    class StubSource:
        def fetch(self, path, **params):
            assert path == "issues/tail/44"
            return {"issue": "044", "entries": [row for row in entries if row["issue_slug"] == "tail/44"]}

    monkeypatch.setattr("toolchain.groups.issues.resolve_source", lambda config: StubSource())
    result = CliRunner().invoke(cli, ["-k", "ctk_live_abc", "issues", "read", "tail/44"])
    assert result.exit_code == 0, result.output
    assert "Nmap" in result.output


def test_issues_head_list_matches_list_with_series_flag(monkeypatch):
    monkeypatch.setattr("toolchain.groups.issues.resolve_source", lambda config: IndexSource())
    result = CliRunner().invoke(cli, ["issues", "head", "list"])
    assert result.exit_code == 0
    with_flag = CliRunner().invoke(cli, ["issues", "list", "--series", "head"])
    assert json.loads(result.output) == json.loads(with_flag.output)


def test_issues_tail_list_scopes_to_tail_only(monkeypatch):
    monkeypatch.setattr("toolchain.groups.issues.resolve_source", lambda config: IndexSource())
    result = CliRunner().invoke(cli, ["issues", "tail", "list"])
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload and all(row["issue_slug"].startswith("tail/") for row in payload)


def test_issues_tail_get_qualifies_a_bare_issue_number(monkeypatch):
    class StubSource:
        def fetch(self, path, **params):
            assert path == "issues/tail/44"
            return {"issue": "044", "entries": [{"tool": "Nmap"}]}

    monkeypatch.setattr("toolchain.groups.issues.resolve_source", lambda config: StubSource())
    result = CliRunner().invoke(cli, ["-k", "ctk_live_abc", "issues", "tail", "get", "44"])
    assert result.exit_code == 0, result.output
    assert json.loads(result.output)["entries"][0]["tool"] == "Nmap"


def test_issues_tail_get_accepts_an_already_qualified_slug(monkeypatch):
    class StubSource:
        def fetch(self, path, **params):
            assert path == "issues/tail/44"
            return {"issue": "044", "entries": [{"tool": "Nmap"}]}

    monkeypatch.setattr("toolchain.groups.issues.resolve_source", lambda config: StubSource())
    result = CliRunner().invoke(cli, ["-k", "ctk_live_abc", "issues", "tail", "get", "tail/44"])
    assert result.exit_code == 0, result.output


def test_issues_series_groups_are_registered_with_help():
    for series in ("head", "tail", "diff"):
        result = CliRunner().invoke(cli, ["issues", series, "--help"])
        assert result.exit_code == 0, result.output
        assert series in result.output


def test_issues_bare_invocation_no_key_says_a_key_is_needed(monkeypatch):
    # The browser reads whole issues on selection, which the free site no
    # longer serves — refused up front rather than crashing on the first pick.
    monkeypatch.setattr("toolchain.groups.issues.resolve_source", lambda config: NeverFetched())
    monkeypatch.setattr("toolchain.tui.issues_browse.IssueBrowserApp",
                        lambda *a, **k: (_ for _ in ()).throw(AssertionError("opened")))
    result = CliRunner().invoke(cli, ["issues"])
    assert result.exit_code == 1
    assert "API key" in result.output


KEYED_INDEX = {"issues": [
    {"issue_slug": "tail/44", "published_at": "2026-08-09T22:03:18+00:00", "tools": ["Nmap"]},
    {"issue_slug": "tail/44", "published_at": "2026-08-09T22:03:18+00:00", "tools": ["Nmap"]},
    {"issue_slug": "head/3", "published_at": "2026-08-08T00:00:00+00:00", "tools": ["Falco"]},
], "next_cursor": None}


class KeyedSource:
    def fetch(self, path, **params):
        if path == "issues":
            rows = KEYED_INDEX["issues"]
            if params.get("series"):
                rows = [r for r in rows if r["issue_slug"].startswith(params["series"] + "/")]
            return {"issues": rows, "next_cursor": None}
        assert path.startswith("issues/"), path
        return {"issue": path.split("/", 1)[1], "entries": [{"tool": "Nmap"}]}


def test_issues_bare_invocation_opens_the_browser(monkeypatch):
    class FakeApp:
        def __init__(self, issues, entries_fetcher):
            self.issues = issues
            self.entries_fetcher = entries_fetcher

        def run(self):
            return None  # simulate quitting with no selection

    monkeypatch.setattr("toolchain.groups.issues.resolve_source", lambda config: KeyedSource())
    monkeypatch.setattr("toolchain.tui.issues_browse.IssueBrowserApp", FakeApp)
    result = CliRunner().invoke(cli, ["-k", "ctk_live_abc", "issues"])
    assert result.exit_code == 0, result.output
    assert result.output == ""


def test_issues_series_bare_invocation_opens_a_scoped_browser(monkeypatch):
    captured = {}

    class FakeApp:
        def __init__(self, issues, entries_fetcher):
            captured["rows"] = issues

        def run(self):
            return None

    monkeypatch.setattr("toolchain.groups.issues.resolve_source", lambda config: KeyedSource())
    monkeypatch.setattr("toolchain.tui.issues_browse.IssueBrowserApp", FakeApp)
    result = CliRunner().invoke(cli, ["-k", "ctk_live_abc", "issues", "tail"])
    assert result.exit_code == 0, result.output
    assert captured["rows"] and all(row["issue_slug"].startswith("tail/") for row in captured["rows"])


def test_issues_browse_rows_include_published_date_and_tool_list(monkeypatch):
    captured = {}

    class FakeApp:
        def __init__(self, issues, entries_fetcher):
            captured["rows"] = issues

        def run(self):
            return None

    monkeypatch.setattr("toolchain.groups.issues.resolve_source", lambda config: KeyedSource())
    monkeypatch.setattr("toolchain.tui.issues_browse.IssueBrowserApp", FakeApp)
    CliRunner().invoke(cli, ["-k", "ctk_live_abc", "issues"])
    row = next(r for r in captured["rows"] if r["issue_slug"] == "tail/44")
    assert row["published_at"] == "2026-08-09T22:03:18+00:00"
    assert row["tools"] == ["Nmap"]


def test_issues_browse_entries_fetcher_reads_the_selected_issue(monkeypatch):
    captured = {}

    class FakeApp:
        def __init__(self, issues, entries_fetcher):
            captured["fetcher"] = entries_fetcher

        def run(self):
            return None

    monkeypatch.setattr("toolchain.groups.issues.resolve_source", lambda config: KeyedSource())
    monkeypatch.setattr("toolchain.tui.issues_browse.IssueBrowserApp", FakeApp)
    CliRunner().invoke(cli, ["-k", "ctk_live_abc", "issues"])
    assert captured["fetcher"]("tail/44")[0]["tool"] == "Nmap"


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

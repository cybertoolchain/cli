from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from toolchain.main import cli

FIXTURES = Path(__file__).parent / "fixtures"


def load(name: str):
    return json.loads((FIXTURES / name).read_text())


def test_search_no_key_matches_keywords(monkeypatch):
    index = load("site_search_index.json")

    class StubSource:
        def fetch(self, path, **params):
            assert path == "search-index.json"
            return index

    monkeypatch.setattr("toolchain.groups.search.resolve_source", lambda config: StubSource())
    result = CliRunner().invoke(cli, ["search", "kubernetes"])
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert len(payload) == 1
    assert payload[0]["label"] == "Falco"


def test_search_no_key_filters_by_type(monkeypatch):
    index = load("site_search_index.json")

    class StubSource:
        def fetch(self, path, **params):
            return index

    monkeypatch.setattr("toolchain.groups.search.resolve_source", lambda config: StubSource())
    result = CliRunner().invoke(cli, ["search", "nmap", "--type", "tool"])
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert all(row["type"] == "tool" for row in payload)


def test_search_no_key_respects_limit_default(monkeypatch):
    index = load("site_search_index.json") * 30  # force > default limit of 20
    for i, row in enumerate(index):
        row["keywords"] = "nmap " + row["keywords"]

    class StubSource:
        def fetch(self, path, **params):
            return index

    monkeypatch.setattr("toolchain.groups.search.resolve_source", lambda config: StubSource())
    result = CliRunner().invoke(cli, ["search", "nmap"])
    assert result.exit_code == 0
    assert len(json.loads(result.output)) == 20


def test_search_with_key_uses_v1_path(monkeypatch):
    class StubSource:
        def fetch(self, path, **params):
            assert path == "search"
            assert params["q"] == "nmap"
            return {"results": []}

    monkeypatch.setattr("toolchain.groups.search.resolve_source", lambda config: StubSource())
    result = CliRunner().invoke(cli, ["-k", "ctk_live_abc", "search", "nmap"])
    assert result.exit_code == 0

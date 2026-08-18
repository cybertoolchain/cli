from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from toolchain.main import cli

FIXTURES = Path(__file__).parent / "fixtures"


def load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text())


def test_categories_list_no_key_derives_counts_from_tools_json(monkeypatch):
    site_data = load("site_tools.json")

    class StubSource:
        def fetch(self, path, **params):
            assert path == "tools.json"
            return site_data

    monkeypatch.setattr("toolchain.groups.categories.resolve_source", lambda config: StubSource())
    result = CliRunner().invoke(cli, ["categories", "list"])
    assert result.exit_code == 0
    payload = json.loads(result.output)
    by_slug = {row["category"]: row["count"] for row in payload}
    assert by_slug == {"reconnaissance": 1, "runtime-security": 1}


def test_categories_list_with_key_uses_v1_path(monkeypatch):
    class StubSource:
        def fetch(self, path, **params):
            assert path == "categories"
            return {"categories": []}

    monkeypatch.setattr("toolchain.groups.categories.resolve_source", lambda config: StubSource())
    result = CliRunner().invoke(cli, ["-k", "ctk_live_abc", "categories", "list"])
    assert result.exit_code == 0

from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from toolchain.main import cli

FIXTURES = Path(__file__).parent / "fixtures"


def load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text())


def test_analytics_get_no_key_reads_masked_site_json(monkeypatch):
    masked = load("site_analytics_notes_quality.json")

    class StubSource:
        def fetch(self, path, **params):
            assert path == "analytics/notes_quality.json"
            return masked

    monkeypatch.setattr("toolchain.groups.analytics.resolve_source", lambda config: StubSource())
    result = CliRunner().invoke(cli, ["analytics", "get", "notes_quality"])
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["data"]["tools"][0]["score"] == 87.0
    assert "▒" in payload["data"]["tools"][0]["name"]


def test_analytics_get_with_researcher_key_returns_unmasked(monkeypatch):
    full = load("api_analytics_researcher.json")

    class StubSource:
        def fetch(self, path, **params):
            assert path == "analytics/notes_quality"
            return full

    monkeypatch.setattr("toolchain.groups.analytics.resolve_source", lambda config: StubSource())
    result = CliRunner().invoke(cli, ["-k", "ctk_researcher_abc", "analytics", "get", "notes_quality"])
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["withheld"] is False
    assert payload["data"]["tools"][0]["name"] == "dockerscan"


def test_analytics_get_with_practitioner_key_is_still_masked(monkeypatch):
    # A key below Researcher tier hits the same /v1 endpoint and the API
    # itself decides the masking — the CLI has no tier logic of its own,
    # it just passes through whatever comes back.
    masked = load("api_analytics_practitioner.json")

    class StubSource:
        def fetch(self, path, **params):
            assert path == "analytics/notes_quality"
            return masked

    monkeypatch.setattr("toolchain.groups.analytics.resolve_source", lambda config: StubSource())
    result = CliRunner().invoke(cli, ["-k", "ctk_practitioner_abc", "analytics", "get", "notes_quality"])
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["withheld"] is True
    assert "▒" in payload["data"]["tools"][0]["name"]

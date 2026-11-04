# tests/test_tools_extensibility.py
from __future__ import annotations

import json

import pytest
from click.testing import CliRunner

from toolchain.main import cli

ROWS = [
    ("Nmap", "nmap", ["scripting", "plugin"], "reviewed", "2026-10-26.1"),
    ("Falco", "falco", ["api", "mcp"], "partial", "2026-10-26.1"),
    ("Zeek", "zeek", [], "unknown", "2026-10-26.1"),
    ("Semgrep", "semgrep", ["sdk"], "reviewed", "2026-10-26.1"),
]


def _site():
    return {
        "count": len(ROWS),
        "tools": [
            {"tool": n, "category": "x", "open_source": True, "extensibility_types": t,
             "extensibility_coverage": c, "extensibility_revision": r, "brand_new_key": 1}
            for n, _s, t, c, r in ROWS
        ],
    }


def _api(ext=None):
    wanted = set(ext.split(",")) if ext else None
    tools = [
        {"name": n, "slug": s, "extensibility_types": t, "extensibility_coverage": c,
         "extensibility_revision": r, "brand_new_key": 1}
        for n, s, t, c, r in ROWS
        if wanted is None or wanted & set(t)
    ]
    return {"tools": tools, "total": len(tools)}


class Stub:
    def __init__(self, site=None, calls=None):
        self.site = site if site is not None else _site()
        self.calls = calls if calls is not None else []

    def fetch(self, path, **params):
        self.calls.append((path, params))
        if path == "tools.json":
            return self.site
        if path == "tools":
            return _api(params.get("extensibility"))
        if path == "tools/count":
            return {"total": _api(params.get("extensibility"))["total"]}
        if path.startswith("tools/"):
            return {"slug": path.split("/")[1], **_api()["tools"][0], "future": {"a": 1}}
        raise AssertionError(path)


@pytest.fixture
def stub(monkeypatch):
    s = Stub()
    monkeypatch.setattr("toolchain.groups.tools.resolve_source", lambda config: s)
    return s


def run(*args):
    return CliRunner().invoke(cli, list(args))


def names(payload):
    return sorted((t.get("tool") or t.get("name")) for t in payload["tools"])


def test_keyed_and_nokey_list_agree(stub):
    for ext in ("api", "scripting,sdk", "api,mcp,plugin"):
        free = json.loads(run("tools", "list", "--ext", ext).output)
        keyed = json.loads(run("-k", "ctk_live_abc", "tools", "list", "--ext", ext).output)
        assert names(free) == names(keyed)


def test_keyed_and_nokey_count_agree(stub):
    for ext in ("api", "scripting,sdk", "api,mcp,plugin"):
        free = json.loads(run("tools", "count", "--ext", ext).output)
        keyed = json.loads(run("-k", "ctk_live_abc", "tools", "count", "--ext", ext).output)
        assert free["total"] == keyed["total"]
    assert json.loads(run("tools", "count", "--ext", "scripting,sdk").output)["total"] == 2


def test_repeatable_and_comma_forms_are_any(stub):
    a = json.loads(run("tools", "list", "--ext", "api", "--ext", "sdk").output)
    b = json.loads(run("tools", "list", "--ext", "api,sdk").output)
    assert names(a) == names(b) == ["Falco", "Semgrep"]


def test_keyed_sends_server_param(stub):
    run("-k", "ctk_live_abc", "tools", "list", "--ext", "api", "--ext", "mcp")
    assert stub.calls[-1] == ("tools", {"extensibility": "api,mcp"})
    run("-k", "ctk_live_abc", "tools", "count", "--ext", "api")
    assert stub.calls[-1] == ("tools/count", {"extensibility": "api"})


def test_filter_applies_before_other_filters_and_count_in_payload(stub):
    out = json.loads(run("tools", "list", "--ext", "api").output)
    assert out["count"] == 1


def test_invalid_option_is_clear_error(stub):
    for args in (["tools", "list"], ["tools", "count"], ["-k", "ctk_live_abc", "tools", "list"]):
        r = run(*args, "--ext", "bogus")
        assert r.exit_code == 1
        assert "bogus" in r.output and "api" in r.output
    assert stub.calls == []


def test_missing_fields_gives_explicit_message(monkeypatch):
    old = {"count": 1, "tools": [{"tool": "Nmap", "category": "x"}]}
    s = Stub(site=old)
    monkeypatch.setattr("toolchain.groups.tools.resolve_source", lambda config: s)
    for cmd in ("list", "count"):
        r = run("tools", cmd, "--ext", "api")
        assert r.exit_code == 1
        assert "extensibility" in r.output.lower() and "not" in r.output.lower()


def test_unknown_keys_tolerated(stub):
    r = run("tools", "list")
    assert r.exit_code == 0
    assert json.loads(r.output)["tools"][0]["brand_new_key"] == 1
    r = run("-k", "ctk_live_abc", "tools", "get", "nmap")
    assert r.exit_code == 0
    assert json.loads(r.output)["future"] == {"a": 1}


def test_get_shows_reader_wording(stub):
    out = json.loads(run("tools", "get", "nmap").output)
    assert out["extensibility_types"] == ["scripting", "plugin"]
    assert out["extensibility_status"] == "Checked 2026-10-26"
    assert "reviewed" not in json.dumps(out["extensibility_status"]).lower()


def test_get_unknown_coverage_wording(stub):
    out = json.loads(run("tools", "get", "zeek").output)
    assert out["extensibility_status"] == "Not checked yet"
    out = json.loads(run("tools", "get", "falco").output)
    assert out["extensibility_status"] == "Partly checked"

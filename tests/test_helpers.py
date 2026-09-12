from __future__ import annotations

import click
import pytest

from toolchain.config import resolve_config
from toolchain.helpers import emit, get_config, handle_errors
from toolchain.models import APIError


def test_get_config_reads_ctx_obj():
    config = resolve_config()
    ctx = click.Context(click.Command("x"))
    ctx.obj = config
    assert get_config(ctx) is config


def test_emit_prints_formatted_json(capsys):
    config = resolve_config()
    emit({"a": 1}, config)
    out = capsys.readouterr().out
    assert out.strip() == '{\n  "a": 1\n}'


def test_emit_respects_output_format(capsys):
    config = resolve_config(output="csv")
    emit({"tools": [{"name": "Nmap"}]}, config)
    out = capsys.readouterr().out
    assert "name" in out
    assert "Nmap" in out


def test_handle_errors_catches_toolchain_error_and_exits():
    @handle_errors
    def boom():
        raise APIError("500 fetching /v1/tools")

    with pytest.raises(SystemExit) as exc_info:
        boom()
    assert exc_info.value.code == 2


def test_handle_errors_prints_message_to_stderr(capsys):
    @handle_errors
    def boom():
        raise APIError("500 fetching /v1/tools")

    with pytest.raises(SystemExit):
        boom()
    err = capsys.readouterr().err
    assert "Error: 500 fetching /v1/tools" in err


def test_handle_errors_passes_through_on_success():
    @handle_errors
    def fine():
        return 42

    assert fine() == 42


def test_tool_slug_matches_the_sites_rule():
    from toolchain.helpers import tool_slug

    # Mirrors site/src/lib/toolSlug.ts: the address of /tools/<slug> and
    # /tool-entries/<slug>.json, so a divergence here is a 404 there.
    assert tool_slug("Nmap") == "nmap"
    assert tool_slug("OWASP ZAP") == "owasp-zap"
    assert tool_slug("Node.js  (LTS)") == "node-js-lts"
    assert tool_slug(" --Claude Code-- ") == "claude-code"

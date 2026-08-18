from __future__ import annotations

import logging
import sys

from toolchain.log import configure_logging, redact


def test_redacts_api_key_token():
    text = 'curl -H "x-api-key: ctk_live_abc123XYZ" https://example.com'
    assert "ctk_live_abc123XYZ" not in redact(text)
    assert "ctk_***REDACTED***" in redact(text)


def test_redact_leaves_non_key_text_untouched():
    assert redact("no secrets here") == "no secrets here"


def test_redact_handles_multiple_keys():
    text = "ctk_one ... ctk_two"
    out = redact(text)
    assert "ctk_one" not in out
    assert "ctk_two" not in out
    assert out.count("ctk_***REDACTED***") == 2


def test_verbose_sets_debug_level():
    logger = configure_logging(verbose=True)
    assert logger.level == logging.DEBUG


def test_quiet_sets_warning_level():
    logger = configure_logging(verbose=False)
    assert logger.level == logging.WARNING


def test_logger_writes_to_stderr():
    logger = configure_logging(verbose=True)
    assert any(h.stream is sys.stderr for h in logger.handlers)

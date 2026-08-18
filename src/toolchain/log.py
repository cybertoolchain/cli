from __future__ import annotations

import logging
import re
import sys

_KEY_PATTERN = re.compile(r"ctk_[A-Za-z0-9_-]+")

_LOGGER_NAME = "toolchain"


def redact(text: str) -> str:
    """Scrubs any ctk_... API key token out of a string before it can reach
    a log line or a --debug curl dump."""
    return _KEY_PATTERN.sub("ctk_***REDACTED***", text)


def configure_logging(verbose: bool) -> logging.Logger:
    logger = logging.getLogger(_LOGGER_NAME)
    logger.setLevel(logging.DEBUG if verbose else logging.WARNING)
    logger.handlers.clear()
    handler = logging.StreamHandler(stream=sys.stderr)
    handler.setFormatter(logging.Formatter("%(levelname)s %(message)s"))
    logger.addHandler(handler)
    logger.propagate = False
    return logger

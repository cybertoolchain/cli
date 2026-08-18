from __future__ import annotations

from typing import Any, Protocol


class Source(Protocol):
    """Anything a command can fetch structured data from — either the
    free static site JSON or the keyed /v1 API."""

    def fetch(self, path: str, **params: Any) -> dict: ...

    def curl(self, path: str, **params: Any) -> str: ...

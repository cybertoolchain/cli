from __future__ import annotations

import json as _json
from dataclasses import dataclass, field
from typing import Any

import httpx


@dataclass
class FakeResponse:
    status_code: int
    json_data: dict | None = None
    text: str = ""
    invalid_json: bool = False

    def json(self) -> dict:
        if self.invalid_json:
            raise _json.JSONDecodeError("Expecting value", self.text or "", 0)
        return self.json_data or {}


@dataclass
class FakeClient:
    """Stands in for httpx.Client in tests. `responses` maps an exact URL
    (scheme+host+path, no query string) to the FakeResponse it returns;
    `raise_on` maps a URL to an exception instance to raise instead, for
    exercising the timeout/connect-error paths."""

    responses: dict[str, FakeResponse] = field(default_factory=dict)
    raise_on: dict[str, Exception] = field(default_factory=dict)
    calls: list[dict[str, Any]] = field(default_factory=list)

    def get(self, url: str, *, params: dict | None = None, headers: dict | None = None):
        self.calls.append({"url": url, "params": params, "headers": headers})
        if url in self.raise_on:
            raise self.raise_on[url]
        if url not in self.responses:
            raise AssertionError(f"FakeClient got an unexpected URL: {url}")
        return self.responses[url]

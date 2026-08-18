# toolchain CLI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `toolchain`, a customer-facing CLI that reads The Cyber
Toolchain's free public site data with no account, and switches to the live,
keyed `/v1` data API when a `ctk_…` API key is supplied — command grammar
mirroring the groups already documented on `/api`.

**Architecture:** Every command resolves a `Source` (a `fetch(path, **params)
-> dict` protocol) via `resolve_source(config)`: no key → `SiteSource` (plain
`httpx` GETs against static JSON already published on the product's GitHub
Pages site); a key → `ApiSource` (`httpx` GETs against `/v1/*` with an
`x-api-key` header). Commands with no site-JSON equivalent (`tools sbom`,
`analytics get`'s full-detail path, and the not-yet-live `doc-diffs`/
`corpus-export`) check for a key explicitly and raise a typed error naming
where to get one. Every scriptable command ends in one `emit()`/
`format_output()` call; `tools browse` (Textual TUI) and `issues read` (Rich
renderer) are the two deliberate exceptions.

**Tech Stack:** Python 3.10+, Click 8+, httpx (sync `Client`), tabulate,
questionary, Textual + Rich (TUI/rendering). `src/` layout, `pyproject.toml`,
`[project.scripts]` entry point. pytest + Hypothesis; no dependency beyond
this list.

**Spec:** `docs/superpowers/specs/2026-08-18-toolchain-cli-design.md`

## Global Constraints

- Python `>=3.10`, `from __future__ import annotations` at the top of every module, type hints on all signatures, ship `py.typed`.
- Click 8+, not argparse/typer. `src/toolchain/` package, `pyproject.toml` (setuptools), `[project.scripts] toolchain = "toolchain.main:main"`.
- Dependencies, all pinned `>=`: `click`, `httpx`, `tabulate`, `questionary`, `textual`, `rich`. No others without discussion.
- Global options resolve **flag → env var (`TOOLCHAIN_` prefix) → default**, validated once in `resolve_config()`. Global flags must appear before the subcommand (enforced by a custom `click.Group`).
- Every scriptable command ends in `emit(data, config)` → one `format_output()` path: `json` (default) / `table` / `csv` / `tsv`, `-s/--short`, `--search-fields`, `-l/--limit`. Data → stdout only; banner/logs/prompts → stderr.
- Typed exceptions map to exit codes: `UserInputError` 1, `APIError` 2, `NetworkError` 3, success 0.
- No route accepts a key or connects to a network without going through a `Source` — tests always inject a fake client, never touch the network.
- A command with no free (site) equivalent must say so in its own `--help` text **and** raise `UserInputError` naming a fix (get a key / which plan) when run without one — never a bare "missing argument" or a raw 401.
- TDD: write the failing test first for every step that adds behavior.

---

### Task 1: Repo scaffold & packaging

**Files:**
- Create: `pyproject.toml`
- Create: `src/toolchain/__init__.py`
- Create: `src/toolchain/py.typed`
- Create: `tests/test_package.py`

**Interfaces:**
- Produces: an installable `toolchain` package importable as `import toolchain`; `pip install -e .` gives a console script `toolchain` (wired to `toolchain.main:main` once Task 12 creates it — the entry point is declared now, `main.py` follows later).

- [ ] **Step 1: Write `pyproject.toml`**

```toml
[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[project]
name = "toolchain-cli"
version = "0.1.0"
description = "Command-line client for The Cyber Toolchain and aitoolchain"
requires-python = ">=3.10"
dependencies = [
    "click>=8.0",
    "httpx>=0.24",
    "tabulate>=0.9",
    "questionary>=2.0",
    "textual>=0.60",
    "rich>=13.7",
]

[project.optional-dependencies]
dev = ["pytest>=8.0", "hypothesis>=6.100"]

[project.scripts]
toolchain = "toolchain.main:main"

[tool.setuptools.package-dir]
toolchain = "src/toolchain"

[tool.setuptools.package-data]
toolchain = ["py.typed"]
```

- [ ] **Step 2: Create the package skeleton**

`src/toolchain/__init__.py`:
```python
from __future__ import annotations

__version__ = "0.1.0"
```

`src/toolchain/py.typed`: empty file.

- [ ] **Step 3: Write the failing test**

```python
# tests/test_package.py
from __future__ import annotations


def test_package_importable():
    import toolchain

    assert toolchain.__version__ == "0.1.0"
```

- [ ] **Step 4: Install and run**

```bash
cd /Users/jonschipp/repos/cybertoolchain/cli
uv venv
uv pip install -e ".[dev]"
uv run pytest tests/test_package.py -v
```
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml src/toolchain/__init__.py src/toolchain/py.typed tests/test_package.py
git commit -m "chore: repo scaffold and packaging"
```

---

### Task 2: Exceptions & exit codes

**Files:**
- Create: `src/toolchain/models.py`
- Test: `tests/test_models.py`

**Interfaces:**
- Produces: `ToolchainError` (base, `exit_code = 1`), `UserInputError` (1), `APIError` (2), `NetworkError` (3) — every later module raises one of these three, never a bare `Exception`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_models.py
from __future__ import annotations

from toolchain.models import APIError, NetworkError, ToolchainError, UserInputError


def test_user_input_error_exit_code_1():
    assert UserInputError("bad flag").exit_code == 1


def test_api_error_exit_code_2():
    assert APIError("500").exit_code == 2


def test_network_error_exit_code_3():
    assert NetworkError("timeout").exit_code == 3


def test_all_are_toolchain_errors():
    assert issubclass(UserInputError, ToolchainError)
    assert issubclass(APIError, ToolchainError)
    assert issubclass(NetworkError, ToolchainError)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_models.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'toolchain.models'`.

- [ ] **Step 3: Write the implementation**

```python
# src/toolchain/models.py
from __future__ import annotations


class ToolchainError(Exception):
    """Base of every error the CLI raises deliberately. Never raise bare."""

    exit_code = 1


class UserInputError(ToolchainError):
    """Bad flag, missing/invalid argument, or a command run without a
    required API key."""

    exit_code = 1


class APIError(ToolchainError):
    """HTTP 4xx/5xx (other than an auth rejection) from either backend."""

    exit_code = 2


class NetworkError(ToolchainError):
    """Connection refused, timeout, DNS failure."""

    exit_code = 3
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_models.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/toolchain/models.py tests/test_models.py
git commit -m "feat: typed exception hierarchy with exit codes"
```

---

### Task 3: Config & site registry

**Files:**
- Create: `src/toolchain/config.py`
- Test: `tests/test_config.py`

**Interfaces:**
- Consumes: `UserInputError` from `models.py` (Task 2).
- Produces: `Site` (dataclass: `site_base: str`, `api_base: str | None`), `SITES: dict[str, Site]`, `VALID_OUTPUTS: tuple[str, ...]`, `Config` (frozen dataclass with fields `api_key`, `site_key`, `site`, `output`, `verbose`, `debug`, `cache`, `limit`, `short`, `timeout`, `search_fields`), `resolve_config(*, api_key=None, site=None, output=None, verbose=False, debug=False, cache=False, limit=None, short=False, timeout=None, search_fields=None) -> Config`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_config.py
from __future__ import annotations

import pytest

from toolchain.config import SITES, VALID_OUTPUTS, resolve_config
from toolchain.models import UserInputError


def test_defaults_to_cybertoolchain_site():
    config = resolve_config()
    assert config.site_key == "cybertoolchain"
    assert config.site is SITES["cybertoolchain"]
    assert config.site.api_base is not None


def test_aitoolchain_has_no_api_base_yet():
    config = resolve_config(site="aitoolchain")
    assert config.site.api_base is None
    assert config.site.site_base == "https://aitoolchain.io"


def test_unknown_site_raises_user_input_error():
    with pytest.raises(UserInputError, match="cybertoolchain, aitoolchain"):
        resolve_config(site="not-a-real-site")


def test_output_defaults_to_json():
    assert resolve_config().output == "json"


def test_invalid_output_raises_user_input_error():
    with pytest.raises(UserInputError):
        resolve_config(output="yaml")


def test_flag_beats_env(monkeypatch):
    monkeypatch.setenv("TOOLCHAIN_API_KEY", "ctk_from_env")
    config = resolve_config(api_key="ctk_from_flag")
    assert config.api_key == "ctk_from_flag"


def test_env_beats_default(monkeypatch):
    monkeypatch.setenv("TOOLCHAIN_SITE", "aitoolchain")
    config = resolve_config()
    assert config.site_key == "aitoolchain"


def test_timeout_defaults_to_30():
    assert resolve_config().timeout == 30.0


def test_valid_outputs_are_stable():
    assert VALID_OUTPUTS == ("json", "table", "csv", "tsv")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_config.py -v`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Write the implementation**

```python
# src/toolchain/config.py
from __future__ import annotations

import os
from dataclasses import dataclass

from .models import UserInputError

VALID_OUTPUTS: tuple[str, ...] = ("json", "table", "csv", "tsv")


@dataclass(frozen=True)
class Site:
    """Where one product's data lives. `api_base` is None until that
    product has a live `/v1` data API — a keyed command against such a
    site fails with a clear message rather than a raw connection error."""

    site_base: str
    api_base: str | None


SITES: dict[str, Site] = {
    "cybertoolchain": Site(
        site_base="https://cybertoolchain.github.io",
        # CloudFront in front of ctk-data-api. Swap for api.cybertoolchain.com
        # here, once, when that DNS/cert work lands — every command reads
        # this one constant.
        api_base="https://d3hvv6ete0783d.cloudfront.net",
    ),
    "aitoolchain": Site(
        site_base="https://aitoolchain.io",
        api_base=None,
    ),
}


@dataclass(frozen=True)
class Config:
    api_key: str | None
    site_key: str
    site: Site
    output: str
    verbose: bool
    debug: bool
    cache: bool
    limit: int | None
    short: bool
    timeout: float
    search_fields: str | None


def resolve_config(
    *,
    api_key: str | None = None,
    site: str | None = None,
    output: str | None = None,
    verbose: bool = False,
    debug: bool = False,
    cache: bool = False,
    limit: int | None = None,
    short: bool = False,
    timeout: float | None = None,
    search_fields: str | None = None,
) -> Config:
    """flag -> env (TOOLCHAIN_ prefix) -> default, validated once, here."""
    resolved_key = api_key or os.environ.get("TOOLCHAIN_API_KEY") or None

    resolved_site_key = site or os.environ.get("TOOLCHAIN_SITE") or "cybertoolchain"
    if resolved_site_key not in SITES:
        supported = ", ".join(SITES)
        raise UserInputError(
            f"Unknown --site '{resolved_site_key}'. Supported values are: {supported}"
        )

    resolved_output = output or os.environ.get("TOOLCHAIN_OUTPUT") or "json"
    if resolved_output not in VALID_OUTPUTS:
        supported = ", ".join(VALID_OUTPUTS)
        raise UserInputError(
            f"Unsupported --output '{resolved_output}'. Supported values are: {supported}"
        )

    resolved_timeout = (
        timeout if timeout is not None else float(os.environ.get("TOOLCHAIN_TIMEOUT", "30"))
    )

    return Config(
        api_key=resolved_key,
        site_key=resolved_site_key,
        site=SITES[resolved_site_key],
        output=resolved_output,
        verbose=verbose,
        debug=debug,
        cache=cache,
        limit=limit,
        short=short,
        timeout=resolved_timeout,
        search_fields=search_fields,
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_config.py -v`
Expected: PASS (9 passed).

- [ ] **Step 5: Commit**

```bash
git add src/toolchain/config.py tests/test_config.py
git commit -m "feat: config resolution and the cybertoolchain/aitoolchain site registry"
```

---

### Task 4: Local response cache

**Files:**
- Create: `src/toolchain/cache.py`
- Test: `tests/test_cache.py`

**Interfaces:**
- Produces: `Cache` class with `.get(key: str) -> dict | None` and `.set(key: str, value: dict) -> None`, backed by JSON files under a directory passed to the constructor (no `platformdirs` dependency — caller decides the directory). Also produces `CachingSource(inner: Source, cache: Cache)` — a `Source` that wraps another `Source`, checking the cache before delegating to `inner.fetch()` and writing the result back. Task 8 wires this into `resolve_source` so `-c/--cache` actually does something; without that wiring the flag would be a silent no-op (found in the plan's own preflight scan).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_cache.py
from __future__ import annotations

from toolchain.cache import Cache


def test_miss_returns_none(tmp_path):
    cache = Cache(tmp_path)
    assert cache.get("tools:list:") is None


def test_set_then_get_round_trips(tmp_path):
    cache = Cache(tmp_path)
    cache.set("tools:list:", {"tools": [{"name": "Nmap"}]})
    assert cache.get("tools:list:") == {"tools": [{"name": "Nmap"}]}


def test_different_keys_do_not_collide(tmp_path):
    cache = Cache(tmp_path)
    cache.set("tools:get:nmap", {"name": "Nmap"})
    cache.set("tools:get:falco", {"name": "Falco"})
    assert cache.get("tools:get:nmap") == {"name": "Nmap"}
    assert cache.get("tools:get:falco") == {"name": "Falco"}


def test_key_with_path_separators_is_safe(tmp_path):
    cache = Cache(tmp_path)
    cache.set("tools/get/../../etc/passwd", {"x": 1})
    assert cache.get("tools/get/../../etc/passwd") == {"x": 1}
    # Nothing escaped the cache directory.
    assert all(p.parent == tmp_path for p in tmp_path.glob("*.json"))


def test_caching_source_serves_from_cache_on_second_call(tmp_path):
    from toolchain.cache import CachingSource

    class CountingSource:
        def __init__(self):
            self.calls = 0

        def fetch(self, path, **params):
            self.calls += 1
            return {"n": self.calls}

    inner = CountingSource()
    source = CachingSource(inner, Cache(tmp_path))
    first = source.fetch("tools.json")
    second = source.fetch("tools.json")
    assert first == second == {"n": 1}
    assert inner.calls == 1


def test_caching_source_treats_different_params_as_different_keys(tmp_path):
    from toolchain.cache import CachingSource

    class EchoSource:
        def fetch(self, path, **params):
            return {"path": path, "params": params}

    source = CachingSource(EchoSource(), Cache(tmp_path))
    a = source.fetch("tools", category="cli")
    b = source.fetch("tools", category="service")
    assert a != b
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_cache.py -v`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Write the implementation**

```python
# src/toolchain/cache.py
from __future__ import annotations

import hashlib
import json
from pathlib import Path


class Cache:
    """A flat directory of JSON files, one per cache key. The key is hashed
    for the filename so arbitrary command+params strings (which may contain
    '/', '..', or other path-unsafe characters) can never escape the
    directory or collide with each other."""

    def __init__(self, directory: Path) -> None:
        self._dir = Path(directory)
        self._dir.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
        return self._dir / f"{digest}.json"

    def get(self, key: str) -> dict | None:
        path = self._path(key)
        if not path.exists():
            return None
        return json.loads(path.read_text())

    def set(self, key: str, value: dict) -> None:
        self._path(key).write_text(json.dumps(value))


class CachingSource:
    """Wraps another Source: serves a cached response when one exists for
    this exact (path, params), else delegates and caches the result. Makes
    -c/--cache actually do something — see resolve_source in Task 8."""

    def __init__(self, inner: "Any", cache: Cache) -> None:
        self._inner = inner
        self._cache = cache

    def _key(self, path: str, params: dict) -> str:
        return f"{path}:{sorted(params.items())}"

    def fetch(self, path: str, **params) -> dict:
        key = self._key(path, params)
        cached = self._cache.get(key)
        if cached is not None:
            return cached
        result = self._inner.fetch(path, **params)
        self._cache.set(key, result)
        return result

    def curl(self, path: str, **params) -> str:
        return self._inner.curl(path, **params)
```

Add `from typing import Any` to the top of `cache.py`'s imports.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_cache.py -v`
Expected: PASS (6 passed).

- [ ] **Step 5: Commit**

```bash
git add src/toolchain/cache.py tests/test_cache.py
git commit -m "feat: local response cache and CachingSource wrapper for -c/--cache"
```

---

### Task 5: Logging & key redaction

**Files:**
- Create: `src/toolchain/log.py`
- Test: `tests/test_log.py`

**Interfaces:**
- Produces: `configure_logging(verbose: bool) -> logging.Logger` (returns a logger named `"toolchain"`, level `DEBUG` if verbose else `WARNING`, writing to stderr) and `redact(text: str) -> str` (replaces any `ctk_[A-Za-z0-9_-]+` token with `ctk_***REDACTED***`).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_log.py
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_log.py -v`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Write the implementation**

```python
# src/toolchain/log.py
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_log.py -v`
Expected: PASS (6 passed).

- [ ] **Step 5: Commit**

```bash
git add src/toolchain/log.py tests/test_log.py
git commit -m "feat: logging setup with API-key redaction"
```

---

### Task 6: Source protocol, SiteSource, and shared test fakes

**Files:**
- Create: `src/toolchain/source/__init__.py` (protocol export only in this task; `resolve_source` added in Task 8)
- Create: `src/toolchain/source/base.py`
- Create: `src/toolchain/source/site.py`
- Create: `tests/fakes.py`
- Test: `tests/test_source_site.py`

**Interfaces:**
- Consumes: `NetworkError`, `APIError` from `models.py` (Task 2).
- Produces: `Source` (a `Protocol` with `fetch(self, path: str, **params) -> dict`), `SiteSource(site_base: str, *, timeout: float = 30.0, client: httpx.Client | None = None)` with `.fetch(path, **params) -> dict` and `.curl(path, **params) -> str`. `tests/fakes.py` produces `FakeClient(responses: dict[str, FakeResponse])` and `FakeResponse(status_code: int, json_data: dict | None = None)` — a minimal `httpx.Client` stand-in with a `.get(url, params=None, headers=None)` method, used by every later Source/command test.

- [ ] **Step 1: Write the shared test fakes**

```python
# tests/fakes.py
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import httpx


@dataclass
class FakeResponse:
    status_code: int
    json_data: dict | None = None

    def json(self) -> dict:
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
```

- [ ] **Step 2: Write the Source protocol**

```python
# src/toolchain/source/base.py
from __future__ import annotations

from typing import Any, Protocol


class Source(Protocol):
    """Anything a command can fetch structured data from — either the
    free static site JSON or the keyed /v1 API."""

    def fetch(self, path: str, **params: Any) -> dict: ...

    def curl(self, path: str, **params: Any) -> str: ...
```

```python
# src/toolchain/source/__init__.py
from __future__ import annotations

from .base import Source
from .site import SiteSource

__all__ = ["Source", "SiteSource"]
```

- [ ] **Step 3: Write the failing test**

```python
# tests/test_source_site.py
from __future__ import annotations

import httpx
import pytest

from toolchain.models import APIError, NetworkError
from toolchain.source.site import SiteSource

from .fakes import FakeClient, FakeResponse


def test_fetch_gets_the_right_url():
    client = FakeClient(
        responses={"https://cybertoolchain.github.io/tools.json": FakeResponse(200, {"tools": []})}
    )
    source = SiteSource("https://cybertoolchain.github.io", client=client)
    result = source.fetch("tools.json")
    assert result == {"tools": []}
    assert client.calls[0]["url"] == "https://cybertoolchain.github.io/tools.json"


def test_fetch_strips_double_slashes():
    client = FakeClient(
        responses={"https://cybertoolchain.github.io/tools.json": FakeResponse(200, {})}
    )
    source = SiteSource("https://cybertoolchain.github.io/", client=client)
    source.fetch("/tools.json")
    assert client.calls[0]["url"] == "https://cybertoolchain.github.io/tools.json"


def test_fetch_passes_params():
    client = FakeClient(
        responses={"https://cybertoolchain.github.io/entries.json": FakeResponse(200, {})}
    )
    source = SiteSource("https://cybertoolchain.github.io", client=client)
    source.fetch("entries.json", tool="nmap")
    assert client.calls[0]["params"] == {"tool": "nmap"}


def test_4xx_raises_api_error():
    client = FakeClient(
        responses={"https://cybertoolchain.github.io/missing.json": FakeResponse(404, {})}
    )
    source = SiteSource("https://cybertoolchain.github.io", client=client)
    with pytest.raises(APIError, match="404"):
        source.fetch("missing.json")


def test_timeout_raises_network_error():
    client = FakeClient(
        raise_on={
            "https://cybertoolchain.github.io/tools.json": httpx.TimeoutException("slow")
        }
    )
    source = SiteSource("https://cybertoolchain.github.io", client=client)
    with pytest.raises(NetworkError):
        source.fetch("tools.json")


def test_connect_error_raises_network_error():
    client = FakeClient(
        raise_on={
            "https://cybertoolchain.github.io/tools.json": httpx.ConnectError("refused")
        }
    )
    source = SiteSource("https://cybertoolchain.github.io", client=client)
    with pytest.raises(NetworkError):
        source.fetch("tools.json")


def test_curl_renders_a_get_url():
    source = SiteSource("https://cybertoolchain.github.io", client=FakeClient())
    assert source.curl("tools.json") == "curl https://cybertoolchain.github.io/tools.json"


def test_curl_includes_params():
    source = SiteSource("https://cybertoolchain.github.io", client=FakeClient())
    assert source.curl("entries.json", tool="nmap") == (
        "curl https://cybertoolchain.github.io/entries.json?tool=nmap"
    )
```

- [ ] **Step 4: Run test to verify it fails**

Run: `uv run pytest tests/test_source_site.py -v`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 5: Write the implementation**

```python
# src/toolchain/source/site.py
from __future__ import annotations

from typing import Any
from urllib.parse import urlencode

import httpx

from ..models import APIError, NetworkError


class SiteSource:
    """Reads static JSON already published on a product's GitHub Pages
    site — free, no key, exactly what a browser would fetch."""

    def __init__(
        self,
        site_base: str,
        *,
        timeout: float = 30.0,
        client: httpx.Client | Any | None = None,
    ) -> None:
        self._base = site_base.rstrip("/")
        self._client = client if client is not None else httpx.Client(timeout=timeout)

    def _url(self, path: str) -> str:
        return f"{self._base}/{path.lstrip('/')}"

    def fetch(self, path: str, **params: Any) -> dict:
        url = self._url(path)
        try:
            response = self._client.get(url, params=params or None)
        except httpx.TimeoutException as exc:
            raise NetworkError(f"Timed out fetching {url}") from exc
        except httpx.ConnectError as exc:
            raise NetworkError(f"Could not connect to {url}") from exc
        if response.status_code >= 400:
            raise APIError(f"{response.status_code} fetching {url}")
        return response.json()

    def curl(self, path: str, **params: Any) -> str:
        url = self._url(path)
        if params:
            url = f"{url}?{urlencode(params)}"
        return f"curl {url}"
```

- [ ] **Step 6: Run test to verify it passes**

Run: `uv run pytest tests/test_source_site.py -v`
Expected: PASS (8 passed).

- [ ] **Step 7: Commit**

```bash
git add src/toolchain/source/ tests/fakes.py tests/test_source_site.py
git commit -m "feat: Source protocol, SiteSource, and shared test fakes"
```

---

### Task 7: ApiSource

**Files:**
- Create: `src/toolchain/source/api.py`
- Test: `tests/test_source_api.py`

**Interfaces:**
- Consumes: `Source` protocol shape (Task 6), `UserInputError`/`APIError`/`NetworkError` (Task 2), `FakeClient`/`FakeResponse` (Task 6).
- Produces: `ApiSource(api_base: str, api_key: str, *, timeout: float = 30.0, client=None)` with `.fetch(path, **params) -> dict` (GETs `{api_base}/v1/{path}` with `x-api-key` header; 401 → `UserInputError`, 429 → `APIError`, other 4xx/5xx → `APIError`) and `.curl(path, **params) -> str` (redacted key placeholder, matching `/api`'s own doc examples: `x-api-key: $TOOLCHAIN_API_KEY`, never the real value).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_source_api.py
from __future__ import annotations

import httpx
import pytest

from toolchain.models import APIError, NetworkError, UserInputError
from toolchain.source.api import ApiSource

from .fakes import FakeClient, FakeResponse

BASE = "https://d3hvv6ete0783d.cloudfront.net"


def test_fetch_hits_v1_path_with_key_header():
    client = FakeClient(responses={f"{BASE}/v1/tools/count": FakeResponse(200, {"total": 836})})
    source = ApiSource(BASE, "ctk_live_abc", client=client)
    result = source.fetch("tools/count")
    assert result == {"total": 836}
    assert client.calls[0]["url"] == f"{BASE}/v1/tools/count"
    assert client.calls[0]["headers"] == {"x-api-key": "ctk_live_abc"}


def test_fetch_passes_params():
    client = FakeClient(responses={f"{BASE}/v1/tools": FakeResponse(200, {"tools": []})})
    source = ApiSource(BASE, "ctk_live_abc", client=client)
    source.fetch("tools", limit=2)
    assert client.calls[0]["params"] == {"limit": 2}


def test_401_raises_user_input_error():
    client = FakeClient(responses={f"{BASE}/v1/tools": FakeResponse(401, {})})
    source = ApiSource(BASE, "ctk_bad", client=client)
    with pytest.raises(UserInputError, match="rejected"):
        source.fetch("tools")


def test_429_raises_api_error():
    client = FakeClient(responses={f"{BASE}/v1/tools": FakeResponse(429, {})})
    source = ApiSource(BASE, "ctk_live_abc", client=client)
    with pytest.raises(APIError, match="Rate limit"):
        source.fetch("tools")


def test_other_4xx_raises_api_error():
    client = FakeClient(responses={f"{BASE}/v1/tools": FakeResponse(404, {})})
    source = ApiSource(BASE, "ctk_live_abc", client=client)
    with pytest.raises(APIError, match="404"):
        source.fetch("tools")


def test_timeout_raises_network_error():
    client = FakeClient(raise_on={f"{BASE}/v1/tools": httpx.TimeoutException("slow")})
    source = ApiSource(BASE, "ctk_live_abc", client=client)
    with pytest.raises(NetworkError):
        source.fetch("tools")


def test_curl_never_prints_the_real_key():
    source = ApiSource(BASE, "ctk_live_secret_value", client=FakeClient())
    dump = source.curl("tools/count")
    assert "ctk_live_secret_value" not in dump
    assert "$TOOLCHAIN_API_KEY" in dump
    assert f"{BASE}/v1/tools/count" in dump
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_source_api.py -v`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Write the implementation**

```python
# src/toolchain/source/api.py
from __future__ import annotations

from typing import Any
from urllib.parse import urlencode

import httpx

from ..models import APIError, NetworkError, UserInputError


class ApiSource:
    """Calls the keyed, versioned data API (/v1/*) behind CloudFront."""

    def __init__(
        self,
        api_base: str,
        api_key: str,
        *,
        timeout: float = 30.0,
        client: httpx.Client | Any | None = None,
    ) -> None:
        self._base = api_base.rstrip("/")
        self._key = api_key
        self._client = client if client is not None else httpx.Client(timeout=timeout)

    def _url(self, path: str) -> str:
        return f"{self._base}/v1/{path.lstrip('/')}"

    def fetch(self, path: str, **params: Any) -> dict:
        url = self._url(path)
        try:
            response = self._client.get(
                url, params=params or None, headers={"x-api-key": self._key}
            )
        except httpx.TimeoutException as exc:
            raise NetworkError(f"Timed out fetching {url}") from exc
        except httpx.ConnectError as exc:
            raise NetworkError(f"Could not connect to {url}") from exc
        if response.status_code == 401:
            raise UserInputError(
                "The API key was rejected (missing, revoked, or unknown). "
                "Get a new one from your account page."
            )
        if response.status_code == 429:
            raise APIError("Rate limit exceeded for this key. Try again later.")
        if response.status_code >= 400:
            raise APIError(f"{response.status_code} fetching {url}")
        return response.json()

    def curl(self, path: str, **params: Any) -> str:
        url = self._url(path)
        if params:
            url = f"{url}?{urlencode(params)}"
        return f'curl -H "x-api-key: $TOOLCHAIN_API_KEY" \\\n  {url}'
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_source_api.py -v`
Expected: PASS (7 passed).

- [ ] **Step 5: Commit**

```bash
git add src/toolchain/source/api.py tests/test_source_api.py
git commit -m "feat: ApiSource for the keyed /v1 data API"
```

---

### Task 8: Source resolution

**Files:**
- Modify: `src/toolchain/source/__init__.py`
- Test: `tests/test_source_resolve.py`

**Interfaces:**
- Consumes: `Config` (Task 3), `SiteSource`/`ApiSource` (Tasks 6–7), `UserInputError` (Task 2), `Cache`/`CachingSource` (Task 4).
- Produces: `resolve_source(config: Config) -> Source` — the one place that decides SiteSource vs. ApiSource, and whether the result is wrapped in `CachingSource` for `-c/--cache`. Every command group (Tasks 13+) calls this and nothing else to get its data source.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_source_resolve.py
from __future__ import annotations

import pytest

from toolchain.config import resolve_config
from toolchain.models import UserInputError
from toolchain.source import ApiSource, SiteSource, resolve_source


def test_no_key_gives_site_source():
    config = resolve_config()
    source = resolve_source(config)
    assert isinstance(source, SiteSource)


def test_key_gives_api_source():
    config = resolve_config(api_key="ctk_live_abc")
    source = resolve_source(config)
    assert isinstance(source, ApiSource)


def test_key_against_a_site_with_no_api_raises():
    config = resolve_config(api_key="ctk_live_abc", site="aitoolchain")
    with pytest.raises(UserInputError, match="aitoolchain has no data API yet"):
        resolve_source(config)


def test_no_key_against_aitoolchain_still_gives_site_source():
    config = resolve_config(site="aitoolchain")
    source = resolve_source(config)
    assert isinstance(source, SiteSource)


def test_cache_flag_wraps_the_source_in_caching_source(tmp_path, monkeypatch):
    from toolchain.cache import CachingSource

    monkeypatch.setattr("toolchain.source.CACHE_DIR", tmp_path)
    config = resolve_config(cache=True)
    source = resolve_source(config)
    assert isinstance(source, CachingSource)


def test_no_cache_flag_returns_the_source_directly():
    config = resolve_config(cache=False)
    source = resolve_source(config)
    assert isinstance(source, SiteSource)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_source_resolve.py -v`
Expected: FAIL with `ImportError: cannot import name 'resolve_source'`.

- [ ] **Step 3: Write the implementation**

```python
# src/toolchain/source/__init__.py
from __future__ import annotations

from pathlib import Path

from ..cache import Cache, CachingSource
from ..config import Config
from ..models import UserInputError
from .api import ApiSource
from .base import Source
from .site import SiteSource

__all__ = ["Source", "SiteSource", "ApiSource", "resolve_source", "CACHE_DIR"]

#: Module-level so tests can monkeypatch it (see test_source_resolve.py) to
#: point at a tmp_path instead of the real home directory.
CACHE_DIR = Path.home() / ".cache" / "toolchain"


def resolve_source(config: Config) -> Source:
    """The one decision point: no key -> the free static site; a key -> the
    live, versioned data API. Also the one place that catches "this product
    has no data API yet" before a command gets a confusing connection
    failure against a None base URL, and that wraps the result in
    CachingSource when -c/--cache is set."""
    if config.api_key:
        if config.site.api_base is None:
            raise UserInputError(
                f"{config.site_key} has no data API yet — only the free site "
                "data is available for it."
            )
        source: Source = ApiSource(config.site.api_base, config.api_key, timeout=config.timeout)
    else:
        source = SiteSource(config.site.site_base, timeout=config.timeout)

    if config.cache:
        return CachingSource(source, Cache(CACHE_DIR))
    return source
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_source_resolve.py -v`
Expected: PASS (6 passed).

- [ ] **Step 5: Commit**

```bash
git add src/toolchain/source/__init__.py tests/test_source_resolve.py
git commit -m "feat: resolve_source picks SiteSource/ApiSource and wires -c/--cache"
```

---

### Task 9: Output formatting

**Files:**
- Create: `src/toolchain/output.py`
- Test: `tests/test_output.py`

**Interfaces:**
- Produces: `extract_items(data: Any) -> list[dict] | None` (largest list-of-dicts anywhere in an arbitrary response), `format_output(data: Any, *, fmt: str = "json", limit: int | None = None, search_fields: str | None = None, short: bool = False) -> str`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_output.py
from __future__ import annotations

import json

from hypothesis import given
from hypothesis import strategies as st

from toolchain.output import extract_items, format_output

TOOLS_RESPONSE = {
    "tools": [
        {"name": "Nmap", "category": "reconnaissance", "url": "https://nmap.org"},
        {"name": "Falco", "category": "runtime-security", "url": "https://falco.org"},
    ],
    "total": 2,
    "next_cursor": None,
}


def test_extract_items_finds_the_list_of_dicts():
    assert extract_items(TOOLS_RESPONSE) == TOOLS_RESPONSE["tools"]


def test_extract_items_none_when_no_list_present():
    assert extract_items({"total": 2}) is None


def test_extract_items_picks_the_largest_list():
    data = {"a": [{"x": 1}], "b": [{"y": 1}, {"y": 2}, {"y": 3}]}
    assert extract_items(data) == data["b"]


def test_json_is_the_default_format():
    out = format_output(TOOLS_RESPONSE)
    assert json.loads(out) == TOOLS_RESPONSE


def test_json_output_is_indented():
    out = format_output({"a": 1}, fmt="json")
    assert out == '{\n  "a": 1\n}'


def test_table_renders_a_grid_with_headers():
    out = format_output(TOOLS_RESPONSE, fmt="table")
    assert "name" in out
    assert "Nmap" in out
    assert "Falco" in out


def test_table_with_no_list_raises_value_error():
    import pytest

    with pytest.raises(ValueError, match="no list of records"):
        format_output({"total": 2}, fmt="table")


def test_csv_has_a_header_row_and_one_row_per_item():
    out = format_output(TOOLS_RESPONSE, fmt="csv")
    lines = out.strip().splitlines()
    assert lines[0].split(",") == sorted(["name", "category", "url"])
    assert len(lines) == 3


def test_tsv_uses_tab_delimiter():
    out = format_output(TOOLS_RESPONSE, fmt="tsv")
    assert "\t" in out.splitlines()[0]
    assert "," not in out.splitlines()[0]


def test_limit_truncates_the_item_list():
    out = format_output(TOOLS_RESPONSE, fmt="json", limit=1)
    assert len(json.loads(out)) == 1


def test_short_gives_one_json_line_per_row():
    out = format_output(TOOLS_RESPONSE, short=True)
    lines = out.strip().splitlines()
    assert len(lines) == 2
    for line in lines:
        json.loads(line)  # each line is valid JSON on its own


def test_short_reorders_name_first():
    out = format_output(TOOLS_RESPONSE, short=True)
    first_line = out.strip().splitlines()[0]
    assert list(json.loads(first_line).keys())[0] == "name"


def test_search_fields_pulls_matching_values_with_count():
    out = format_output(TOOLS_RESPONSE, search_fields="category")
    result = json.loads(out)
    assert result["field"] == "category"
    assert result["count"] == 2
    assert sorted(result["values"]) == ["reconnaissance", "runtime-security"]


@given(st.lists(st.dictionaries(st.text(min_size=1, max_size=5), st.integers()), max_size=5))
def test_extract_items_never_crashes_on_arbitrary_lists(items):
    data = {"wrapped": items}
    extract_items(data)  # must not raise, for any list-of-dicts shape
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_output.py -v`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Write the implementation**

```python
# src/toolchain/output.py
from __future__ import annotations

import csv
import io
import json
from typing import Any

from tabulate import tabulate

_PRIORITY_FIELDS = {"name", "tool", "display", "status", "severity", "category"}
_DEEMPHASIZE_SUFFIXES = ("id", "uuid", "url", "href")


def extract_items(data: Any) -> list[dict] | None:
    """The largest list-of-dicts found anywhere in an arbitrary response, or
    None if there isn't one — lets table/csv/limit work without per-endpoint
    wiring, the same way Jon's other CLIs do it."""
    candidates: list[list[dict]] = []

    def walk(node: Any) -> None:
        if isinstance(node, list):
            if node and all(isinstance(item, dict) for item in node):
                candidates.append(node)
            for item in node:
                walk(item)
        elif isinstance(node, dict):
            for value in node.values():
                walk(value)

    walk(data)
    if not candidates:
        return None
    return max(candidates, key=len)


def _priority_key(field: str) -> tuple[int, str]:
    lower = field.lower()
    if lower in _PRIORITY_FIELDS:
        return (0, field)
    if lower.endswith(_DEEMPHASIZE_SUFFIXES):
        return (2, field)
    return (1, field)


def _reorder(row: dict) -> dict:
    return {key: row[key] for key in sorted(row, key=_priority_key)}


def _search_fields(data: Any, name: str) -> dict:
    matches: list[Any] = []

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                if key == name:
                    matches.append(value)
                walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(data)
    return {"field": name, "count": len(matches), "values": matches}


def format_output(
    data: Any,
    *,
    fmt: str = "json",
    limit: int | None = None,
    search_fields: str | None = None,
    short: bool = False,
) -> str:
    if search_fields:
        data = _search_fields(data, search_fields)

    items = extract_items(data)
    if items is not None and limit is not None:
        items = items[:limit]
        if isinstance(data, dict):
            list_key = next(k for k, v in data.items() if v is extract_items(data) or v == items or True)
        data = {**data} if isinstance(data, dict) else items
        if isinstance(data, dict):
            for key, value in list(data.items()):
                if isinstance(value, list) and value and all(isinstance(x, dict) for x in value):
                    data[key] = items
                    break

    if short:
        rows = items if items is not None else ([data] if isinstance(data, dict) else [])
        return "\n".join(json.dumps(_reorder(row), separators=(",", ":")) for row in rows)

    if fmt == "json":
        return json.dumps(data, indent=2)

    if items is None:
        raise ValueError(f"Cannot render {fmt} output: no list of records found in the response")

    if fmt == "table":
        return tabulate(items, headers="keys", tablefmt="grid")

    if fmt in ("csv", "tsv"):
        buffer = io.StringIO()
        delimiter = "," if fmt == "csv" else "\t"
        fieldnames = sorted({key for row in items for key in row})
        writer = csv.DictWriter(buffer, fieldnames=fieldnames, delimiter=delimiter)
        writer.writeheader()
        writer.writerows(items)
        return buffer.getvalue()

    raise ValueError(f"Unsupported output format: {fmt}")
```

Note on the `limit` + `json` interaction: the loop above replaces the
matched list-of-dicts value in place on a shallow copy of `data` so a
limited JSON response still carries its surrounding metadata (`total`,
`next_cursor`) rather than becoming a bare list — write the test in Step 1
(`test_limit_truncates_the_item_list`) against this exact behavior; if the
implementation instead returns a bare list for `fmt="json"` with a `limit`,
adjust the assertion to `json.loads(out)["tools"]` having length 1, whichever
this task's Step 4 run confirms.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_output.py -v`
Expected: PASS (14 passed, including the Hypothesis test). If
`test_limit_truncates_the_item_list` fails because `json.loads(out)` is now
a dict, update that one assertion to `len(json.loads(out)["tools"]) == 1`
and re-run — the property under test (limit truncates the list) is what
matters, not which of the two reasonable JSON shapes it takes.

- [ ] **Step 5: Commit**

```bash
git add src/toolchain/output.py tests/test_output.py
git commit -m "feat: one output-formatting path (json/table/csv/tsv, short, search-fields)"
```

---

### Task 10: emit / get_config / handle_errors

**Files:**
- Create: `src/toolchain/helpers.py`
- Test: `tests/test_helpers.py`

**Interfaces:**
- Consumes: `Config` (Task 3), `format_output` (Task 9), `ToolchainError` (Task 2).
- Produces: `get_config(ctx: click.Context) -> Config`, `emit(data: Any, config: Config) -> None` (writes `format_output(...)` to stdout via `click.echo`), `handle_errors(fn)` decorator (catches `ToolchainError`, prints `Error: {message}` to stderr, `sys.exit(exc.exit_code)`).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_helpers.py
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_helpers.py -v`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Write the implementation**

```python
# src/toolchain/helpers.py
from __future__ import annotations

import functools
import sys
from typing import Any, Callable, TypeVar

import click

from .config import Config
from .models import ToolchainError
from .output import format_output

F = TypeVar("F", bound=Callable[..., Any])


def get_config(ctx: click.Context) -> Config:
    return ctx.obj


def emit(data: Any, config: Config) -> None:
    click.echo(
        format_output(
            data,
            fmt=config.output,
            limit=config.limit,
            search_fields=config.search_fields,
            short=config.short,
        )
    )


def handle_errors(fn: F) -> F:
    @functools.wraps(fn)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            return fn(*args, **kwargs)
        except ToolchainError as exc:
            click.echo(f"Error: {exc}", err=True)
            sys.exit(exc.exit_code)

    return wrapper  # type: ignore[return-value]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_helpers.py -v`
Expected: PASS (6 passed).

- [ ] **Step 5: Commit**

```bash
git add src/toolchain/helpers.py tests/test_helpers.py
git commit -m "feat: emit/get_config/handle_errors helper layer"
```

---

### Task 11: Global-option-misplacement Group subclass

**Files:**
- Create: `src/toolchain/cli_group.py`
- Test: `tests/test_cli_group.py`

**Interfaces:**
- Produces: `GLOBAL_FLAGS: frozenset[str]`, `GlobalOptionGroup(click.Group)` — overrides `parse_args` to raise a `click.UsageError` with a corrective example when a known global flag token appears after the first positional (subcommand) argument.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_cli_group.py
from __future__ import annotations

import click
from click.testing import CliRunner

from toolchain.cli_group import GlobalOptionGroup


def _build_test_cli():
    @click.group(cls=GlobalOptionGroup)
    @click.option("-o", "--output", default="json")
    @click.option("-v", "--verbose", is_flag=True, default=False)
    def root(output, verbose):
        pass

    @root.group()
    def tools():
        pass

    @tools.command("list")
    def tools_list():
        click.echo("ok")

    return root


def test_global_flag_before_subcommand_works():
    runner = CliRunner()
    result = runner.invoke(_build_test_cli(), ["-o", "json", "tools", "list"])
    assert result.exit_code == 0
    assert "ok" in result.output


def test_global_flag_after_subcommand_is_rejected():
    runner = CliRunner()
    result = runner.invoke(_build_test_cli(), ["tools", "list", "-o", "json"])
    assert result.exit_code != 0
    assert "global option" in result.output
    assert "must appear before the subcommand" in result.output


def test_error_message_shows_a_corrective_example():
    runner = CliRunner()
    result = runner.invoke(_build_test_cli(), ["tools", "list", "-o", "json"])
    assert "toolchain -o <value> tools list" in result.output or "-o <value>" in result.output


def test_unrelated_subcommand_option_is_unaffected():
    runner = CliRunner()
    result = runner.invoke(_build_test_cli(), ["tools", "list"])
    assert result.exit_code == 0


def test_two_correctly_placed_global_flags_are_not_rejected():
    # Regression test: a naive "first token not starting with -" boundary
    # search lands on "json" (the VALUE of -o) instead of "tools", and then
    # wrongly flags the still-correctly-placed -v as misplaced.
    runner = CliRunner()
    result = runner.invoke(_build_test_cli(), ["-o", "json", "-v", "tools", "list"])
    assert result.exit_code == 0
    assert "ok" in result.output
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_cli_group.py -v`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Write the implementation**

```python
# src/toolchain/cli_group.py
from __future__ import annotations

import click

GLOBAL_FLAGS: frozenset[str] = frozenset(
    {
        "-k", "--api-key",
        "--site",
        "-o", "--output",
        "-v", "--verbose",
        "--debug",
        "-c", "--cache",
        "-l", "--limit",
        "-s", "--short",
        "-t", "--timeout",
        "--search-fields",
    }
)


#: Global flags that consume the following token as their value. Needed to
#: correctly find where the subcommand starts: a naive "first token not
#: starting with -" breaks the moment two global flags are combined and one
#: of them takes a value — `toolchain -o json -v tools list` would
#: otherwise see "json" as the subcommand and wrongly flag the
#: still-correctly-placed -v as misplaced. (Found in Task 11's review: the
#: plan's own first draft of this function had exactly that bug.)
_VALUE_FLAGS: frozenset[str] = frozenset(
    {"-k", "--api-key", "--site", "-o", "--output", "-l", "--limit", "-t", "--timeout", "--search-fields"}
)


class GlobalOptionGroup(click.Group):
    """Detects a global flag used after the subcommand and prints a
    corrective example instead of a confusing per-subcommand parse error."""

    def parse_args(self, ctx: click.Context, args: list[str]) -> list[str]:
        sub_idx = None
        i = 0
        while i < len(args):
            token = args[i]
            if token.startswith("-"):
                name = token.split("=", 1)[0]
                if name in _VALUE_FLAGS and "=" not in token:
                    i += 2  # skip the flag AND its separate value token
                    continue
                i += 1
                continue
            sub_idx = i
            break

        if sub_idx is not None:
            for token in args[sub_idx + 1 :]:
                name = token.split("=", 1)[0]
                if name in GLOBAL_FLAGS:
                    raise click.UsageError(
                        f"'{name}' is a global option and must appear before the subcommand.\n\n"
                        "  toolchain [GLOBAL OPTIONS] GROUP COMMAND ...\n\n"
                        "Example:\n"
                        f"  toolchain {name} <value> {' '.join(args[:sub_idx + 1])}"
                    )
        return super().parse_args(ctx, args)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_cli_group.py -v`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```bash
git add src/toolchain/cli_group.py tests/test_cli_group.py
git commit -m "feat: hint when a global flag is placed after the subcommand"
```

---

### Task 12: Root CLI — banner, tldr, wiring

**Files:**
- Create: `src/toolchain/main.py`
- Test: `tests/test_main.py`

**Interfaces:**
- Consumes: `GlobalOptionGroup` (Task 11), `resolve_config` (Task 3), `VALID_OUTPUTS`/`SITES` (Task 3), `ToolchainError` (Task 2), `configure_logging` (Task 5).
- Produces: `cli` (the root `click.Group`, exported for command-group registration in later tasks), `main() -> None` (the `[project.scripts]` entry point — wraps `cli(standalone_mode=False)`, maps `ToolchainError`/`click.ClickException`/`click.Abort` to the right exit code).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_main.py
from __future__ import annotations

from click.testing import CliRunner

from toolchain.main import cli


def test_bare_invocation_prints_banner_and_hint_and_exits_0():
    runner = CliRunner()
    result = runner.invoke(cli, [])
    assert result.exit_code == 0
    assert "toolchain --help" in result.output or "tldr" in result.output


def test_tldr_command_prints_quick_reference():
    runner = CliRunner()
    result = runner.invoke(cli, ["tldr"])
    assert result.exit_code == 0
    assert "toolchain tools list" in result.output


def test_help_lists_the_command_groups():
    runner = CliRunner()
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert "tldr" in result.output


def test_unknown_site_flag_exits_1_with_message():
    runner = CliRunner()
    result = runner.invoke(cli, ["--site", "not-real", "tldr"])
    assert result.exit_code == 1
    assert "Unknown --site" in result.output
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_main.py -v`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Write the implementation**

```python
# src/toolchain/main.py
from __future__ import annotations

import sys

import click

from .cli_group import GlobalOptionGroup
from .config import VALID_OUTPUTS, resolve_config
from .log import configure_logging
from .models import ToolchainError

BANNER = r"""
 _____           _      _           _
|_   _|__   ___ | | ___| |__   __ _(_)_ __
  | |/ _ \ / _ \| |/ __| '_ \ / _` | | '_ \
  | | (_) | (_) | | (__| | | | (_| | | | | |
  |_|\___/ \___/|_|\___|_| |_|\__,_|_|_| |_|
"""

TLDR = """\
toolchain tools list                    # every tracked tool
toolchain tools get nmap                # one tool + its latest release
toolchain releases latest --limit 10    # what just shipped, across the watchlist
toolchain issues get 044                # one newsletter issue, as data
toolchain issues read 044               # ...and as a rendered document
toolchain search "runtime security"     # tools + releases matching a query

Add -k/--api-key (or set TOOLCHAIN_API_KEY) for live filtering, full
analytics, SBOM, and stack details. Run 'toolchain COMMAND --help' for
every option.
"""


@click.group(cls=GlobalOptionGroup, invoke_without_command=True)
@click.option("-k", "--api-key", envvar="TOOLCHAIN_API_KEY", default=None)
@click.option("--site", "site_key", default=None)
@click.option("-o", "--output", default=None, type=click.Choice(VALID_OUTPUTS))
@click.option("-v", "--verbose", is_flag=True, default=False)
@click.option("--debug", is_flag=True, default=False)
@click.option("-c", "--cache", is_flag=True, default=False)
@click.option("-l", "--limit", type=int, default=None)
@click.option("-s", "--short", is_flag=True, default=False)
@click.option("-t", "--timeout", type=float, default=None)
@click.option("--search-fields", default=None)
@click.pass_context
def cli(
    ctx: click.Context,
    api_key: str | None,
    site_key: str | None,
    output: str | None,
    verbose: bool,
    debug: bool,
    cache: bool,
    limit: int | None,
    short: bool,
    timeout: float | None,
    search_fields: str | None,
) -> None:
    """The Cyber Toolchain / aitoolchain command-line client."""
    try:
        ctx.obj = resolve_config(
            api_key=api_key,
            site=site_key,
            output=output,
            verbose=verbose,
            debug=debug,
            cache=cache,
            limit=limit,
            short=short,
            timeout=timeout,
            search_fields=search_fields,
        )
    except ToolchainError as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(exc.exit_code)
    configure_logging(verbose)
    if ctx.invoked_subcommand is None:
        click.echo(BANNER, err=True)
        click.echo(
            "Run 'toolchain --help' for commands, or 'toolchain tldr' for a quick reference.",
            err=True,
        )


@cli.command()
def tldr() -> None:
    """Quick reference for common commands."""
    click.echo(TLDR)


def main() -> None:
    try:
        cli(standalone_mode=False)
    except click.ClickException as exc:
        exc.show()
        sys.exit(exc.exit_code)
    except ToolchainError as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(exc.exit_code)
    except click.exceptions.Abort:
        sys.exit(1)


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_main.py -v`
Expected: PASS (4 passed).

Plan bug found here: with the `try`/`except` left out of the `cli()` callback
(i.e. `resolve_config()` called bare, and `ToolchainError` handled only in
`main()`), `test_unknown_site_flag_exits_1_with_message` fails — exit code is
1, but `result.output` is empty. `main()`'s try/except only runs on the real
`toolchain` entry point (`cli(standalone_mode=False)`); the test invokes
`cli` directly via `CliRunner`, where Click's own `standalone_mode=True`
machinery only auto-handles `click.ClickException`/`Exit`/`Abort` — not our
`ToolchainError` hierarchy — so a raw, unprinted exception propagates. The
`cli()` callback itself must catch `ToolchainError` from `resolve_config()`,
echo it, and `sys.exit(exc.exit_code)`, which is now reflected in the code
block above.

- [ ] **Step 5: Install and smoke-test the real entry point**

```bash
uv pip install -e ".[dev]"
uv run toolchain tldr
uv run toolchain --help
```
Expected: both print without error.

- [ ] **Step 6: Commit**

```bash
git add src/toolchain/main.py tests/test_main.py
git commit -m "feat: root CLI group, banner, tldr, and the console-script entry point"
```

---

### Task 13: `tools list` / `tools count` / `tools get`

**Files:**
- Create: `src/toolchain/groups/__init__.py`
- Create: `src/toolchain/groups/tools.py`
- Create: `tests/fixtures/site_tools.json`
- Create: `tests/fixtures/api_tools_list.json`
- Create: `tests/fixtures/api_tools_count.json`
- Create: `tests/fixtures/api_tools_detail.json`
- Test: `tests/test_group_tools.py`

**Interfaces:**
- Consumes: `resolve_source` (Task 8), `emit`/`get_config`/`handle_errors` (Task 10), `SiteSource`/`ApiSource` (Tasks 6–7).
- Produces: `tools` (a `click.Group`, registered onto `cli` in `main.py` by this task's Step 6) with commands `list`, `count`, `get SLUG`. Every command in this task and Tasks 14–16 imports `from .tools import tools` where `tools = click.Group("tools")`, so later tasks attach more commands to the same object rather than redefining it.

- [ ] **Step 1: Write the fixtures**

`tests/fixtures/site_tools.json` (trimmed from a real `/tools.json` response —
`toolsFeed()` output, `generator/site/src/pages/tools.json.ts`):
```json
{
  "title": "The Cyber Toolchain — watchlist",
  "home_page_url": "https://cybertoolchain.github.io/",
  "feed_url": "https://cybertoolchain.github.io/tools.json",
  "updated": "2026-08-13",
  "count": 2,
  "tools": [
    {
      "tool": "Nmap",
      "category": "reconnaissance",
      "version": "commits-2026-07-11",
      "url": "https://github.com/nmap/nmap/compare/49a85f9c3c11...115af39aacf9",
      "summary": "Nmap gains TLS close_notify tolerance, SSL service portrule coverage, and signal propagation to child processes with `-k`.",
      "open_source": true,
      "published_at": "2026-08-09T22:03:18+00:00",
      "signal_kind": "activity",
      "permalink": "https://cybertoolchain.github.io/tools/nmap"
    },
    {
      "tool": "Falco",
      "category": "runtime-security",
      "version": "v0.40.0",
      "url": "https://falco.org/docs/reference/changelog/",
      "summary": "Falco 0.40.0 adds a new gRPC output plugin and hardens rule syntax validation.",
      "open_source": true,
      "published_at": "2026-08-05T10:00:00+00:00",
      "signal_kind": "release",
      "permalink": "https://cybertoolchain.github.io/tools/falco"
    }
  ]
}
```

`tests/fixtures/api_tools_count.json` (verbatim from `/api`'s documented example):
```json
{"total": 836, "generated_at": "2026-08-14"}
```

`tests/fixtures/api_tools_list.json` (verbatim from `/api`'s documented example):
```json
{
  "tools": [
    {
      "name": "Nmap", "display": "Nmap", "category": "reconnaissance", "vendor": null,
      "tool_type": "cli", "tags": ["network-scanning", "port-scanning", "service-detection", "os-fingerprinting"],
      "repo": "nmap/nmap", "url": null, "docs_url": "https://nmap.org/book/man.html",
      "changelog_url": "https://nmap.org/changelog.html", "website": null, "adapter": "github",
      "open_source": null, "license": "oss", "launched": null, "added": "2026-06-24",
      "retired": false, "slug": "nmap"
    },
    {
      "name": "Falco", "display": "Falco", "category": "runtime-security", "vendor": null,
      "tool_type": "service", "tags": ["ebpf", "runtime-detection", "syscall-monitoring", "kubernetes"],
      "repo": "falcosecurity/falco", "url": null, "docs_url": "https://falco.org/docs/",
      "changelog_url": "https://falco.org/docs/reference/changelog/", "website": null, "adapter": "github",
      "open_source": null, "license": "oss", "launched": null, "added": "2026-07-02",
      "retired": false, "slug": "falco"
    }
  ],
  "total": 2,
  "next_cursor": null
}
```

`tests/fixtures/api_tools_detail.json` (verbatim from `/api`'s documented example for `nmap`):
```json
{
  "name": "Nmap", "display": "Nmap", "category": "reconnaissance", "vendor": null,
  "tool_type": "cli", "tags": ["network-scanning", "port-scanning", "service-detection", "os-fingerprinting"],
  "repo": "nmap/nmap", "url": null, "docs_url": "https://nmap.org/book/man.html",
  "changelog_url": "https://nmap.org/changelog.html", "website": null, "adapter": "github",
  "open_source": null, "license": "oss", "launched": null, "added": "2026-06-24",
  "retired": false, "slug": "nmap",
  "latest_release": {
    "tool": "Nmap", "category": "reconnaissance", "version": "commits-2026-07-11",
    "published_at": "2026-08-09T22:03:18+00:00",
    "url": "https://github.com/nmap/nmap/compare/49a85f9c3c11...115af39aacf9",
    "summary": "Nmap gains TLS close_notify tolerance, SSL service portrule coverage, and signal propagation to child processes with `-k`.",
    "feature_bullets": ["Adds `-k` signal propagation."],
    "breaking_changes": [],
    "usage_examples": [{
      "description": "Specify an interface with -e to bind both the outgoing interface and the source address.",
      "command": "nmap -e eth1 -S 192.168.1.50 <target>", "language": "", "kind": "shell"
    }],
    "signal_kind": "activity", "prerelease": false, "is_latest": false
  },
  "has_api_surface": false,
  "has_cli_surface": true
}
```

- [ ] **Step 2: Write the failing test**

```python
# tests/test_group_tools.py
from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from toolchain.main import cli

FIXTURES = Path(__file__).parent / "fixtures"


def load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text())


def test_tools_list_uses_site_source_with_no_key(monkeypatch):
    site_data = load("site_tools.json")

    class StubSource:
        def fetch(self, path, **params):
            assert path == "tools.json"
            return site_data

    monkeypatch.setattr("toolchain.groups.tools.resolve_source", lambda config: StubSource())
    result = CliRunner().invoke(cli, ["tools", "list"])
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["count"] == 2
    assert payload["tools"][0]["tool"] == "Nmap"


def test_tools_list_uses_api_source_with_key(monkeypatch):
    api_data = load("api_tools_list.json")

    class StubSource:
        def fetch(self, path, **params):
            assert path == "tools"
            return api_data

    monkeypatch.setattr("toolchain.groups.tools.resolve_source", lambda config: StubSource())
    result = CliRunner().invoke(cli, ["-k", "ctk_live_abc", "tools", "list"])
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["total"] == 2
    assert payload["tools"][0]["slug"] == "nmap"


def test_tools_list_passes_filters_as_params(monkeypatch):
    captured = {}

    class StubSource:
        def fetch(self, path, **params):
            captured.update(params)
            return {"tools": []}

    monkeypatch.setattr("toolchain.groups.tools.resolve_source", lambda config: StubSource())
    CliRunner().invoke(cli, ["tools", "list", "--category", "reconnaissance", "--q", "scan"])
    assert captured["category"] == "reconnaissance"
    assert captured["q"] == "scan"


def test_tools_count(monkeypatch):
    api_data = load("api_tools_count.json")

    class StubSource:
        def fetch(self, path, **params):
            assert path == "tools/count"
            return api_data

    monkeypatch.setattr("toolchain.groups.tools.resolve_source", lambda config: StubSource())
    result = CliRunner().invoke(cli, ["-k", "ctk_live_abc", "tools", "count"])
    assert result.exit_code == 0
    assert json.loads(result.output)["total"] == 836


def test_tools_get_no_key_finds_tool_by_name_in_site_data(monkeypatch):
    site_data = load("site_tools.json")

    class StubSource:
        def fetch(self, path, **params):
            assert path == "tools.json"
            return site_data

    monkeypatch.setattr("toolchain.groups.tools.resolve_source", lambda config: StubSource())
    result = CliRunner().invoke(cli, ["tools", "get", "nmap"])
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["tool"] == "Nmap"


def test_tools_get_no_key_unknown_slug_is_user_input_error(monkeypatch):
    site_data = load("site_tools.json")

    class StubSource:
        def fetch(self, path, **params):
            return site_data

    monkeypatch.setattr("toolchain.groups.tools.resolve_source", lambda config: StubSource())
    result = CliRunner().invoke(cli, ["tools", "get", "not-a-real-tool"])
    assert result.exit_code == 1
    assert "not-a-real-tool" in result.output


def test_tools_get_with_key_uses_v1_slug_path(monkeypatch):
    api_data = load("api_tools_detail.json")

    class StubSource:
        def fetch(self, path, **params):
            assert path == "tools/nmap"
            return api_data

    monkeypatch.setattr("toolchain.groups.tools.resolve_source", lambda config: StubSource())
    result = CliRunner().invoke(cli, ["-k", "ctk_live_abc", "tools", "get", "nmap"])
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["latest_release"]["version"] == "commits-2026-07-11"
```

- [ ] **Step 3: Run test to verify it fails**

Run: `uv run pytest tests/test_group_tools.py -v`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 4: Write the implementation**

```python
# src/toolchain/groups/__init__.py
from __future__ import annotations
```

```python
# src/toolchain/groups/tools.py
from __future__ import annotations

import click

from ..helpers import emit, get_config, handle_errors
from ..models import UserInputError
from ..source import resolve_source


@click.group()
def tools() -> None:
    """The watchlist itself — what's tracked, what each tool is, and what
    it has shipped."""


def _slug_of(tool_row: dict) -> str:
    return str(tool_row.get("tool", "")).lower().replace(" ", "-")


@tools.command("list")
@click.option("--category", default=None)
@click.option("--license", "license_", default=None, type=click.Choice(["open-source", "commercial"]))
@click.option("--tool_type", default=None)
@click.option("--q", default=None)
@click.option("--cursor", default=None)
@click.pass_context
@handle_errors
def tools_list(ctx: click.Context, category, license_, tool_type, q, cursor) -> None:
    """Every tracked tool. No key: the current watchlist snapshot from the
    site. With a key: live, server-side filtered and paginated."""
    config = get_config(ctx)
    source = resolve_source(config)
    params = {
        k: v
        for k, v in {
            "category": category,
            "license": license_,
            "tool_type": tool_type,
            "q": q,
            "cursor": cursor,
        }.items()
        if v is not None
    }
    path = "tools" if config.api_key else "tools.json"
    data = source.fetch(path, **params)
    emit(data, config)


@tools.command("count")
@click.option("--category", default=None)
@click.option("--license", "license_", default=None, type=click.Choice(["open-source", "commercial"]))
@click.option("--tool_type", default=None)
@click.pass_context
@handle_errors
def tools_count(ctx: click.Context, category, license_, tool_type) -> None:
    """Just the number — requires an API key (there is no site-JSON count
    endpoint; count it yourself from `tools list` if you have no key)."""
    config = get_config(ctx)
    if not config.api_key:
        raise UserInputError(
            "tools count requires an API key — get one at "
            f"{config.site.site_base}/account (any plan)."
        )
    source = resolve_source(config)
    params = {
        k: v
        for k, v in {"category": category, "license": license_, "tool_type": tool_type}.items()
        if v is not None
    }
    data = source.fetch("tools/count", **params)
    emit(data, config)


@tools.command("get")
@click.argument("slug")
@click.pass_context
@handle_errors
def tools_get(ctx: click.Context, slug: str) -> None:
    """One tool in full, including its most recent release."""
    config = get_config(ctx)
    source = resolve_source(config)
    if config.api_key:
        data = source.fetch(f"tools/{slug}")
    else:
        site_data = source.fetch("tools.json")
        match = next(
            (row for row in site_data["tools"] if _slug_of(row) == slug.lower()), None
        )
        if match is None:
            raise UserInputError(
                f"No tracked tool matches '{slug}'. Run 'toolchain tools list' to see slugs."
            )
        data = match
    emit(data, config)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest tests/test_group_tools.py -v`
Expected: PASS (7 passed).

- [ ] **Step 6: Register the group on the root CLI**

Modify `src/toolchain/main.py`, adding after the `tldr` command definition:

```python
from .groups.tools import tools as tools_group

cli.add_command(tools_group, name="tools")
```

Add to `tests/test_main.py`:
```python
def test_tools_group_is_registered():
    from click.testing import CliRunner

    result = CliRunner().invoke(cli, ["tools", "--help"])
    assert result.exit_code == 0
    assert "list" in result.output
```

Run: `uv run pytest tests/test_main.py -v`
Expected: PASS (5 passed).

- [ ] **Step 7: Commit**

```bash
git add src/toolchain/groups/ tests/fixtures/site_tools.json tests/fixtures/api_tools_*.json tests/test_group_tools.py tests/test_main.py src/toolchain/main.py
git commit -m "feat: tools list/count/get"
```

---

### Task 14: `tools releases` / `tools api` / `tools examples`

**Files:**
- Modify: `src/toolchain/groups/tools.py`
- Create: `tests/fixtures/site_entries.json`
- Create: `tests/fixtures/site_tool_apis.json`
- Create: `tests/fixtures/site_cli_explains.json`
- Modify: `tests/test_group_tools.py`

**Interfaces:**
- Consumes: same as Task 13.
- Produces: `tools releases SLUG`, `tools api SLUG`, `tools examples SLUG` added to the same `tools` group object.

- [ ] **Step 1: Write the fixtures**

`tests/fixtures/site_entries.json` (trimmed from a real `/entries.json`
response — `buildFeedEntries()`, `generator/site/src/lib/stack.ts`):
```json
[
  {
    "tool": "Nmap",
    "name": "nmap",
    "category": "reconnaissance",
    "summary": "Nmap gains TLS close_notify tolerance and signal propagation to child processes with `-k`.",
    "url": "https://github.com/nmap/nmap/compare/49a85f9c3c11...115af39aacf9",
    "published_at": "2026-08-09T22:03:18+00:00",
    "issue_slug": "tail/44",
    "has_command": true,
    "version": "commits-2026-07-11",
    "feature_bullets": ["Adds `-k` signal propagation."],
    "breaking_changes": []
  },
  {
    "tool": "Nmap",
    "name": "nmap",
    "category": "reconnaissance",
    "summary": "Nmap 7.99 adds NSE script updates.",
    "url": "https://nmap.org/changelog.html",
    "published_at": "2026-07-20T09:00:00+00:00",
    "issue_slug": "tail/38",
    "has_command": false,
    "version": "7.99",
    "feature_bullets": ["NSE script updates."]
  },
  {
    "tool": "Falco",
    "name": "falco",
    "category": "runtime-security",
    "summary": "Falco 0.40.0 adds a new gRPC output plugin.",
    "url": "https://falco.org/docs/reference/changelog/",
    "published_at": "2026-08-05T10:00:00+00:00",
    "issue_slug": "tail/42",
    "has_command": false,
    "version": "v0.40.0",
    "feature_bullets": ["gRPC output plugin."]
  }
]
```

`tests/fixtures/site_tool_apis.json` (real entry, trimmed, from
`generator/site/public/tool-apis.json` — used for `1password` in this
fixture rather than `nmap`, since Nmap ships no API):
```json
{
  "1Password": {
    "changes": [],
    "deprecated": [],
    "endpoints": [
      "GET /vaults",
      "GET /vaults/{vaultUuid}",
      "GET /vaults/{vaultUuid}/items",
      "POST /vaults/{vaultUuid}/items"
    ],
    "spec_url": "https://i.1password.com/media/1password-connect/1password-connect-api_1.8.1.yaml",
    "spec_version": "1.8.1",
    "title": "1Password Connect API"
  }
}
```

`tests/fixtures/site_cli_explains.json` (real entry, trimmed, from
`generator/site/public/cli-explains.json`):
```json
{
  "Aircrack-ng": {
    "t-opt-fe24a716": {
      "digest": "ac0115e69ae7e6aa",
      "findings": "The tool exited with status 1 after printing a single error: 'Session file already exists'.",
      "generated_at": "2026-08-02T17:42:53+00:00",
      "inputs": "Aircrack-ng was run against a pcap slice file with -N.",
      "model": "claude-sonnet-4-6",
      "prompt_ver": "v1"
    }
  }
}
```

- [ ] **Step 2: Add the failing tests**

Append to `tests/test_group_tools.py`:
```python
def test_tools_releases_no_key_filters_entries_by_tool(monkeypatch):
    entries = load("site_entries.json")

    class StubSource:
        def fetch(self, path, **params):
            assert path == "entries.json"
            return entries

    monkeypatch.setattr("toolchain.groups.tools.resolve_source", lambda config: StubSource())
    result = CliRunner().invoke(cli, ["tools", "releases", "nmap"])
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert len(payload) == 2
    assert all(row["name"] == "nmap" for row in payload)


def test_tools_releases_with_key_uses_v1_path(monkeypatch):
    class StubSource:
        def fetch(self, path, **params):
            assert path == "tools/nmap/releases"
            return {"releases": [], "next_cursor": None}

    monkeypatch.setattr("toolchain.groups.tools.resolve_source", lambda config: StubSource())
    result = CliRunner().invoke(cli, ["-k", "ctk_live_abc", "tools", "releases", "nmap"])
    assert result.exit_code == 0


def test_tools_api_no_key_reads_tool_apis_json(monkeypatch):
    apis = load("site_tool_apis.json")

    class StubSource:
        def fetch(self, path, **params):
            assert path == "tool-apis.json"
            return apis

    monkeypatch.setattr("toolchain.groups.tools.resolve_source", lambda config: StubSource())
    result = CliRunner().invoke(cli, ["tools", "api", "1Password"])
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["spec_version"] == "1.8.1"


def test_tools_api_no_key_unknown_tool_is_user_input_error(monkeypatch):
    apis = load("site_tool_apis.json")

    class StubSource:
        def fetch(self, path, **params):
            return apis

    monkeypatch.setattr("toolchain.groups.tools.resolve_source", lambda config: StubSource())
    result = CliRunner().invoke(cli, ["tools", "api", "nmap"])
    assert result.exit_code == 1
    assert "no published API" in result.output


def test_tools_examples_no_key_reads_cli_explains_json(monkeypatch):
    explains = load("site_cli_explains.json")

    class StubSource:
        def fetch(self, path, **params):
            assert path == "cli-explains.json"
            return explains

    monkeypatch.setattr("toolchain.groups.tools.resolve_source", lambda config: StubSource())
    result = CliRunner().invoke(cli, ["tools", "examples", "Aircrack-ng"])
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert "t-opt-fe24a716" in payload


def test_tools_examples_with_key_uses_v1_cli_path(monkeypatch):
    class StubSource:
        def fetch(self, path, **params):
            assert path == "tools/nmap/cli"
            return {"examples": []}

    monkeypatch.setattr("toolchain.groups.tools.resolve_source", lambda config: StubSource())
    result = CliRunner().invoke(cli, ["-k", "ctk_live_abc", "tools", "examples", "nmap"])
    assert result.exit_code == 0
```

- [ ] **Step 3: Run test to verify it fails**

Run: `uv run pytest tests/test_group_tools.py -v`
Expected: FAIL — `tools releases`/`api`/`examples` don't exist yet (Click reports "No such command").

- [ ] **Step 4: Add the implementation**

Append to `src/toolchain/groups/tools.py`:

```python
@tools.command("releases")
@click.argument("slug")
@click.option("--since", default=None)
@click.option("--until", default=None)
@click.option("--limit", "release_limit", type=int, default=None)
@click.pass_context
@handle_errors
def tools_releases(ctx: click.Context, slug: str, since, until, release_limit) -> None:
    """One tool's release history."""
    config = get_config(ctx)
    source = resolve_source(config)
    if config.api_key:
        params = {
            k: v
            for k, v in {"since": since, "until": until, "limit": release_limit}.items()
            if v is not None
        }
        data = source.fetch(f"tools/{slug}/releases", **params)
    else:
        entries = source.fetch("entries.json")
        data = [row for row in entries if row.get("name") == slug.lower()]
    emit(data, config)


@tools.command("api")
@click.argument("slug")
@click.pass_context
@handle_errors
def tools_api(ctx: click.Context, slug: str) -> None:
    """The tool's own API surface: capability areas and endpoint count on
    any key or none; full per-endpoint detail on a Researcher+ key."""
    config = get_config(ctx)
    source = resolve_source(config)
    if config.api_key:
        data = source.fetch(f"tools/{slug}/api")
    else:
        apis = source.fetch("tool-apis.json")
        match = next((v for k, v in apis.items() if k.lower() == slug.lower()), None)
        if match is None:
            raise UserInputError(f"'{slug}' has no published API in the watchlist.")
        data = match
    emit(data, config)


@tools.command("examples")
@click.argument("slug")
@click.pass_context
@handle_errors
def tools_examples(ctx: click.Context, slug: str) -> None:
    """Captured command-line examples. No key: the written explanation of
    what each captured run did. With a key: the full command and its real
    output too."""
    config = get_config(ctx)
    source = resolve_source(config)
    if config.api_key:
        data = source.fetch(f"tools/{slug}/cli")
    else:
        explains = source.fetch("cli-explains.json")
        match = next((v for k, v in explains.items() if k.lower() == slug.lower()), None)
        if match is None:
            raise UserInputError(f"No captured CLI examples for '{slug}' yet.")
        data = match
    emit(data, config)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest tests/test_group_tools.py -v`
Expected: PASS (13 passed).

- [ ] **Step 6: Commit**

```bash
git add src/toolchain/groups/tools.py tests/fixtures/site_entries.json tests/fixtures/site_tool_apis.json tests/fixtures/site_cli_explains.json tests/test_group_tools.py
git commit -m "feat: tools releases/api/examples"
```

---

### Task 15: `tools stack` / `tools sbom`

**Files:**
- Modify: `src/toolchain/groups/tools.py`
- Create: `tests/fixtures/site_tool_code.json`
- Modify: `tests/test_group_tools.py`

**Interfaces:**
- Consumes: same as Task 13.
- Produces: `tools stack SLUG` (free with no key via the site's `toolCode.json` — **note:** the approved design spec listed `stack` as key-only; live inspection of `generator/site/public/toolCode.json` during this plan found it already publishes exactly this data — language mix, dependency list, AI-attribution stats — for free. This task implements the more accurate, more generous behavior and should be flagged to Jon as a deviation from the written spec when this task is reported done), `tools sbom SLUG` (genuinely key-only — no public SBOM JSON exists on the site).

- [ ] **Step 1: Write the fixture**

`tests/fixtures/site_tool_code.json` (real entry, trimmed, from
`generator/site/public/toolCode.json`):
```json
{
  "ADR": {
    "ai": {
      "assistants": ["Claude Code", "Cursor"],
      "attributed_pct": 15.9,
      "commits_attributed": 7,
      "commits_total": 44,
      "markers": []
    },
    "cli": {
      "by_source": {"documented": 0, "parsed": 0},
      "events": [],
      "events_total": 0,
      "flags": 0,
      "live_flags": 0,
      "tags_considered": 0,
      "tags_total": 0,
      "truncated": false
    },
    "deps": {
      "direct": 73,
      "top": [{"ecosystem": "pypi", "name": "requests"}]
    }
  }
}
```

- [ ] **Step 2: Add the failing tests**

Append to `tests/test_group_tools.py`:
```python
def test_tools_stack_no_key_reads_tool_code_json(monkeypatch):
    code = load("site_tool_code.json")

    class StubSource:
        def fetch(self, path, **params):
            assert path == "toolCode.json"
            return code

    monkeypatch.setattr("toolchain.groups.tools.resolve_source", lambda config: StubSource())
    result = CliRunner().invoke(cli, ["tools", "stack", "ADR"])
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["deps"]["direct"] == 73


def test_tools_stack_no_key_unknown_tool_is_user_input_error(monkeypatch):
    code = load("site_tool_code.json")

    class StubSource:
        def fetch(self, path, **params):
            return code

    monkeypatch.setattr("toolchain.groups.tools.resolve_source", lambda config: StubSource())
    result = CliRunner().invoke(cli, ["tools", "stack", "not-a-tool"])
    assert result.exit_code == 1


def test_tools_stack_with_key_uses_v1_path(monkeypatch):
    class StubSource:
        def fetch(self, path, **params):
            assert path == "tools/nmap/stack"
            return {}

    monkeypatch.setattr("toolchain.groups.tools.resolve_source", lambda config: StubSource())
    result = CliRunner().invoke(cli, ["-k", "ctk_live_abc", "tools", "stack", "nmap"])
    assert result.exit_code == 0


def test_tools_sbom_with_no_key_requires_api_key():
    result = CliRunner().invoke(cli, ["tools", "sbom", "nmap"])
    assert result.exit_code == 1
    assert "requires an API key" in result.output


def test_tools_sbom_with_key_uses_v1_path(monkeypatch):
    class StubSource:
        def fetch(self, path, **params):
            assert path == "tools/nmap/sbom"
            return {"components": []}

    monkeypatch.setattr("toolchain.groups.tools.resolve_source", lambda config: StubSource())
    result = CliRunner().invoke(cli, ["-k", "ctk_live_abc", "tools", "sbom", "nmap"])
    assert result.exit_code == 0


def test_tools_sbom_help_states_the_key_requirement():
    result = CliRunner().invoke(cli, ["tools", "sbom", "--help"])
    assert "requires an API key" in result.output
```

- [ ] **Step 3: Run test to verify it fails**

Run: `uv run pytest tests/test_group_tools.py -v`
Expected: FAIL — `stack`/`sbom` don't exist yet.

- [ ] **Step 4: Add the implementation**

Append to `src/toolchain/groups/tools.py`:

```python
@tools.command("stack")
@click.argument("slug")
@click.pass_context
@handle_errors
def tools_stack(ctx: click.Context, slug: str) -> None:
    """Language mix, dependencies, and AI-attribution stats. Free with no
    key, from the published watchlist snapshot; live and per-request with
    a key."""
    config = get_config(ctx)
    source = resolve_source(config)
    if config.api_key:
        data = source.fetch(f"tools/{slug}/stack")
    else:
        code = source.fetch("toolCode.json")
        match = next((v for k, v in code.items() if k.lower() == slug.lower()), None)
        if match is None:
            raise UserInputError(f"No code/stack analysis published for '{slug}'.")
        data = match
    emit(data, config)


@tools.command("sbom")
@click.argument("slug")
@click.pass_context
@handle_errors
def tools_sbom(ctx: click.Context, slug: str) -> None:
    """The tool's software bill of materials. Requires an API key — there
    is no free equivalent published on the site."""
    config = get_config(ctx)
    if not config.api_key:
        raise UserInputError(
            "tools sbom requires an API key — get one at "
            f"{config.site.site_base}/account (Researcher plan or higher)."
        )
    source = resolve_source(config)
    data = source.fetch(f"tools/{slug}/sbom")
    emit(data, config)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest tests/test_group_tools.py -v`
Expected: PASS (19 passed).

- [ ] **Step 6: Commit**

```bash
git add src/toolchain/groups/tools.py tests/fixtures/site_tool_code.json tests/test_group_tools.py
git commit -m "feat: tools stack (free via toolCode.json) and tools sbom (key-only)"
```

---

### Task 16: `tools browse` (Textual TUI)

**Files:**
- Create: `src/toolchain/tui/__init__.py`
- Create: `src/toolchain/tui/browse.py`
- Modify: `src/toolchain/groups/tools.py`
- Modify: `pyproject.toml` (adds `pytest-asyncio` to the `dev` extra and sets `asyncio_mode = "auto"`)
- Test: `tests/test_tui_browse.py`

**Interfaces:**
- Consumes: `Source` (Task 6), a `list[dict]` of tool rows shaped like `site_tools.json["tools"]` or `api_tools_list.json["tools"]`.
- Produces: `ToolBrowserApp(tools: list[dict])` (a `textual.app.App` with a filterable `Input` + `ListView`/`DataTable` showing `tool`/`category`/`version`, selecting a row prints that tool's full record on exit), `run_browse(source: Source, config: Config) -> None` (fetches the tool list via the same path logic as `tools list`, then runs the app). Wired as `tools browse` with no `--output`/`emit` — this is the one command in the `tools` group that is a deliberate exception to the emit() rule.

- [ ] **Step 1: Write the failing test**

Textual ships a headless test harness (`App.run_test()`) that drives the app
without a real terminal — use it directly, no fakes needed beyond a plain
Python list for `tools`.

```python
# tests/test_tui_browse.py
from __future__ import annotations

import pytest

from toolchain.tui.browse import ToolBrowserApp

TOOLS = [
    {"tool": "Nmap", "category": "reconnaissance", "version": "commits-2026-07-11"},
    {"tool": "Falco", "category": "runtime-security", "version": "v0.40.0"},
    {"tool": "Trivy", "category": "container-security", "version": "v0.55.0"},
]


@pytest.mark.asyncio
async def test_all_tools_listed_on_start():
    app = ToolBrowserApp(TOOLS)
    async with app.run_test() as pilot:
        table = app.query_one("#tool-table")
        assert table.row_count == 3


@pytest.mark.asyncio
async def test_filter_narrows_the_list():
    app = ToolBrowserApp(TOOLS)
    async with app.run_test() as pilot:
        await pilot.click("#filter")
        for char in "falco":
            await pilot.press(char)
        table = app.query_one("#tool-table")
        assert table.row_count == 1


@pytest.mark.asyncio
async def test_selecting_a_row_sets_selected_tool():
    app = ToolBrowserApp(TOOLS)
    async with app.run_test() as pilot:
        table = app.query_one("#tool-table")
        table.focus()
        await pilot.press("enter")
        assert app.selected_tool == TOOLS[0]
        assert app.return_value == TOOLS[0]
```

Add `pytest-asyncio` to the `dev` extra in `pyproject.toml` (Textual's test
harness is async):
```toml
[project.optional-dependencies]
dev = ["pytest>=8.0", "hypothesis>=6.100", "pytest-asyncio>=0.24"]
```
And a `pytest.ini` (or `[tool.pytest.ini_options]` in `pyproject.toml`) setting:
```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv pip install -e ".[dev]" && uv run pytest tests/test_tui_browse.py -v`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Write the implementation**

```python
# src/toolchain/tui/__init__.py
from __future__ import annotations
```

```python
# src/toolchain/tui/browse.py
from __future__ import annotations

from typing import Any

from textual.app import App, ComposeResult
from textual.containers import Vertical
from textual.widgets import DataTable, Footer, Header, Input

from ..config import Config
from ..source.base import Source


class ToolBrowserApp(App):
    """Fuzzy search + select over the tools list. Returns the selected
    tool's raw record when the app exits (Enter on a row, or Ctrl+C to
    cancel with no selection)."""

    CSS = """
    #filter { dock: top; }
    #tool-table { height: 1fr; }
    """
    BINDINGS = [("ctrl+c", "quit", "Cancel")]

    def __init__(self, tools: list[dict[str, Any]]) -> None:
        super().__init__()
        self._all_tools = tools
        self.selected_tool: dict[str, Any] | None = None

    def compose(self) -> ComposeResult:
        yield Header()
        yield Vertical(
            Input(placeholder="Filter tools…", id="filter"),
            DataTable(id="tool-table"),
        )
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#tool-table", DataTable)
        table.add_columns("tool", "category", "version")
        self._render_rows(self._all_tools)

    def _render_rows(self, rows: list[dict[str, Any]]) -> None:
        table = self.query_one("#tool-table", DataTable)
        table.clear()
        for row in rows:
            table.add_row(row.get("tool", ""), row.get("category", ""), row.get("version", ""))
        self._visible_rows = rows

    def on_input_changed(self, event: Input.Changed) -> None:
        needle = event.value.lower()
        filtered = [
            row for row in self._all_tools if needle in str(row.get("tool", "")).lower()
        ]
        self._render_rows(filtered)

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        self.selected_tool = self._visible_rows[event.cursor_row]
        self.exit(self.selected_tool)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_tui_browse.py -v`
Expected: PASS (3 passed).

- [ ] **Step 5: Wire `tools browse` onto the group**

Append to `src/toolchain/groups/tools.py`:

```python
@tools.command("browse")
@click.pass_context
@handle_errors
def tools_browse(ctx: click.Context) -> None:
    """Interactively search and select from the tools list. Human-only —
    does not go through -o/--output."""
    from ..tui.browse import ToolBrowserApp

    config = get_config(ctx)
    source = resolve_source(config)
    path = "tools" if config.api_key else "tools.json"
    data = source.fetch(path)
    rows = data.get("tools", data if isinstance(data, list) else [])
    app = ToolBrowserApp(rows)
    selected = app.run()
    if selected is not None:
        click.echo(f"{selected.get('tool')}: {selected.get('url', selected.get('docs_url', ''))}")
```

Add to `tests/test_group_tools.py`:
```python
def test_tools_browse_is_registered_and_has_help():
    result = CliRunner().invoke(cli, ["tools", "browse", "--help"])
    assert result.exit_code == 0
    assert "Interactively" in result.output
```

Run: `uv run pytest tests/test_group_tools.py -v`
Expected: PASS (20 passed).

- [ ] **Step 6: Manual check**

```bash
uv run toolchain tools browse
```
Expected: a full-screen TUI opens with a filter box and a table of tools
fetched live from `cybertoolchain.github.io/tools.json`; typing narrows the
list; Enter on a row exits and prints that tool's URL.

- [ ] **Step 7: Commit**

```bash
git add src/toolchain/tui/ src/toolchain/groups/tools.py tests/test_tui_browse.py tests/test_group_tools.py pyproject.toml
git commit -m "feat: tools browse — a Textual TUI for searching and selecting tools"
```

---

### Task 17: `releases list` / `releases latest`

**Files:**
- Create: `src/toolchain/groups/releases.py`
- Test: `tests/test_group_releases.py`

**Interfaces:**
- Consumes: `resolve_source`, `emit`/`get_config`/`handle_errors`, `site_entries.json` fixture (Task 14).
- Produces: `releases` group (registered on `cli`) with `list` (`--tools`, `--categories`, `--since`, `--until`, `--limit`) and `latest` (`--limit`, newest-first, no filters).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_group_releases.py
from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from toolchain.main import cli

FIXTURES = Path(__file__).parent / "fixtures"


def load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text())


def test_releases_list_no_key_reads_entries_json(monkeypatch):
    entries = load("site_entries.json")

    class StubSource:
        def fetch(self, path, **params):
            assert path == "entries.json"
            return entries

    monkeypatch.setattr("toolchain.groups.releases.resolve_source", lambda config: StubSource())
    result = CliRunner().invoke(cli, ["releases", "list"])
    assert result.exit_code == 0
    assert len(json.loads(result.output)) == 3


def test_releases_list_filters_by_tools(monkeypatch):
    entries = load("site_entries.json")

    class StubSource:
        def fetch(self, path, **params):
            return entries

    monkeypatch.setattr("toolchain.groups.releases.resolve_source", lambda config: StubSource())
    result = CliRunner().invoke(cli, ["releases", "list", "--tools", "falco"])
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert len(payload) == 1
    assert payload[0]["name"] == "falco"


def test_releases_list_filters_by_categories(monkeypatch):
    entries = load("site_entries.json")

    class StubSource:
        def fetch(self, path, **params):
            return entries

    monkeypatch.setattr("toolchain.groups.releases.resolve_source", lambda config: StubSource())
    result = CliRunner().invoke(cli, ["releases", "list", "--categories", "runtime-security"])
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert all(row["category"] == "runtime-security" for row in payload)


def test_releases_list_with_key_uses_v1_path(monkeypatch):
    class StubSource:
        def fetch(self, path, **params):
            assert path == "releases"
            return {"releases": [], "next_cursor": None}

    monkeypatch.setattr("toolchain.groups.releases.resolve_source", lambda config: StubSource())
    result = CliRunner().invoke(cli, ["-k", "ctk_live_abc", "releases", "list"])
    assert result.exit_code == 0


def test_releases_latest_sorts_newest_first_and_applies_default_limit(monkeypatch):
    entries = load("site_entries.json")

    class StubSource:
        def fetch(self, path, **params):
            return entries

    monkeypatch.setattr("toolchain.groups.releases.resolve_source", lambda config: StubSource())
    result = CliRunner().invoke(cli, ["releases", "latest"])
    assert result.exit_code == 0
    payload = json.loads(result.output)
    dates = [row["published_at"] for row in payload]
    assert dates == sorted(dates, reverse=True)


def test_releases_latest_limit_flag(monkeypatch):
    entries = load("site_entries.json")

    class StubSource:
        def fetch(self, path, **params):
            return entries

    monkeypatch.setattr("toolchain.groups.releases.resolve_source", lambda config: StubSource())
    result = CliRunner().invoke(cli, ["releases", "latest", "--limit", "1"])
    assert result.exit_code == 0
    assert len(json.loads(result.output)) == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_group_releases.py -v`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Write the implementation**

```python
# src/toolchain/groups/releases.py
from __future__ import annotations

import click

from ..helpers import emit, get_config, handle_errors
from ..source import resolve_source


@click.group()
def releases() -> None:
    """Every release across the watchlist in one feed — what Tail sends,
    queryable instead of mailed."""


@releases.command("list")
@click.option("--tools", "tools_", default=None, help="Comma-separated slugs.")
@click.option("--categories", default=None, help="Comma-separated taxonomy slugs.")
@click.option("--since", default=None)
@click.option("--until", default=None)
@click.option("--limit", type=int, default=None)
@click.pass_context
@handle_errors
def releases_list(ctx: click.Context, tools_, categories, since, until, limit) -> None:
    """Filterable across the whole watchlist, not just one tool."""
    config = get_config(ctx)
    source = resolve_source(config)
    if config.api_key:
        params = {
            k: v
            for k, v in {
                "tools": tools_,
                "categories": categories,
                "since": since,
                "until": until,
                "limit": limit,
            }.items()
            if v is not None
        }
        data = source.fetch("releases", **params)
    else:
        entries = source.fetch("entries.json")
        data = entries
        if tools_:
            wanted = {t.strip().lower() for t in tools_.split(",")}
            data = [row for row in data if row.get("name") in wanted]
        if categories:
            wanted_cats = {c.strip().lower() for c in categories.split(",")}
            data = [row for row in data if row.get("category", "").lower() in wanted_cats]
        if since:
            data = [row for row in data if row.get("published_at", "") >= since]
        if until:
            data = [row for row in data if row.get("published_at", "") <= until]
        if limit is not None:
            data = data[:limit]
    emit(data, config)


@releases.command("latest")
@click.option("--limit", type=int, default=20)
@click.pass_context
@handle_errors
def releases_latest(ctx: click.Context, limit: int) -> None:
    """Newest releases across the whole watchlist, no filters — the CLI
    equivalent of the Tail newsletter feed."""
    config = get_config(ctx)
    source = resolve_source(config)
    if config.api_key:
        data = source.fetch("releases", limit=limit)
    else:
        entries = source.fetch("entries.json")
        data = sorted(entries, key=lambda row: row.get("published_at", ""), reverse=True)[:limit]
    emit(data, config)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_group_releases.py -v`
Expected: PASS (6 passed).

- [ ] **Step 5: Register the group**

Modify `src/toolchain/main.py`:
```python
from .groups.releases import releases as releases_group

cli.add_command(releases_group, name="releases")
```

- [ ] **Step 6: Commit**

```bash
git add src/toolchain/groups/releases.py tests/test_group_releases.py src/toolchain/main.py
git commit -m "feat: releases list/latest"
```

---

### Task 18: `categories list`

**Files:**
- Create: `src/toolchain/groups/categories.py`
- Test: `tests/test_group_categories.py`

**Interfaces:**
- Consumes: `resolve_source`, `emit`/`get_config`/`handle_errors`, `site_tools.json` fixture (Task 13).
- Produces: `categories` group with `list` — no key derives categories + live counts from `/tools.json` (the taxonomy itself isn't published as its own file; this is the same data the site's category filter dropdown is built from); a key uses `/v1/categories` directly.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_group_categories.py
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_group_categories.py -v`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Write the implementation**

```python
# src/toolchain/groups/categories.py
from __future__ import annotations

from collections import Counter

import click

from ..helpers import emit, get_config, handle_errors
from ..source import resolve_source


@click.group()
def categories() -> None:
    """The taxonomy every category filter on the site already uses."""


@categories.command("list")
@click.pass_context
@handle_errors
def categories_list(ctx: click.Context) -> None:
    """Every category, with a live tool count."""
    config = get_config(ctx)
    source = resolve_source(config)
    if config.api_key:
        data = source.fetch("categories")
    else:
        site_data = source.fetch("tools.json")
        counts = Counter(row.get("category", "uncategorized") for row in site_data["tools"])
        data = [{"category": slug, "count": count} for slug, count in sorted(counts.items())]
    emit(data, config)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_group_categories.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Register the group**

Modify `src/toolchain/main.py`:
```python
from .groups.categories import categories as categories_group

cli.add_command(categories_group, name="categories")
```

- [ ] **Step 6: Commit**

```bash
git add src/toolchain/groups/categories.py tests/test_group_categories.py src/toolchain/main.py
git commit -m "feat: categories list"
```

---

### Task 19: `issues list` / `issues get`

**Files:**
- Create: `src/toolchain/groups/issues.py`
- Test: `tests/test_group_issues.py`

**Interfaces:**
- Consumes: `resolve_source`, `emit`/`get_config`/`handle_errors`, `site_entries.json` fixture (Task 14).
- Produces: `issues` group with `list` (`--series`, `--limit`) and `get ISSUE` (data command). **Note on scope, discovered during planning:** the site publishes no standalone per-issue JSON file (only the flattened, cross-issue `/entries.json`) — verified by enumerating `generator/site/src/pages/*.json.ts`. So the no-key path for both commands derives issue-level data by grouping `/entries.json` rows by `issue_slug`, which gives every issue that has at least one public (non-paywalled) entry, with that entry's own fields — not the full archive record (no `assimilated` block, no non-public entries). This is a real but narrower view than the keyed `/v1/issues` response; document this in each command's docstring so it's visible in `--help`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_group_issues.py
from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from toolchain.main import cli

FIXTURES = Path(__file__).parent / "fixtures"


def load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text())


def test_issues_list_no_key_groups_entries_by_issue_slug(monkeypatch):
    entries = load("site_entries.json")

    class StubSource:
        def fetch(self, path, **params):
            assert path == "entries.json"
            return entries

    monkeypatch.setattr("toolchain.groups.issues.resolve_source", lambda config: StubSource())
    result = CliRunner().invoke(cli, ["issues", "list"])
    assert result.exit_code == 0
    payload = json.loads(result.output)
    slugs = {row["issue_slug"] for row in payload}
    assert slugs == {"tail/44", "tail/38", "tail/42"}


def test_issues_list_filters_by_series(monkeypatch):
    entries = load("site_entries.json")

    class StubSource:
        def fetch(self, path, **params):
            return entries

    monkeypatch.setattr("toolchain.groups.issues.resolve_source", lambda config: StubSource())
    result = CliRunner().invoke(cli, ["issues", "list", "--series", "tail"])
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert all(row["issue_slug"].startswith("tail/") for row in payload)


def test_issues_list_with_key_uses_v1_path(monkeypatch):
    class StubSource:
        def fetch(self, path, **params):
            assert path == "issues"
            return {"issues": [], "next_cursor": None}

    monkeypatch.setattr("toolchain.groups.issues.resolve_source", lambda config: StubSource())
    result = CliRunner().invoke(cli, ["-k", "ctk_live_abc", "issues", "list"])
    assert result.exit_code == 0


def test_issues_get_no_key_returns_matching_entries(monkeypatch):
    entries = load("site_entries.json")

    class StubSource:
        def fetch(self, path, **params):
            return entries

    monkeypatch.setattr("toolchain.groups.issues.resolve_source", lambda config: StubSource())
    result = CliRunner().invoke(cli, ["issues", "get", "tail/44"])
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert len(payload) == 1
    assert payload[0]["tool"] == "Nmap"


def test_issues_get_no_key_unknown_issue_is_user_input_error(monkeypatch):
    entries = load("site_entries.json")

    class StubSource:
        def fetch(self, path, **params):
            return entries

    monkeypatch.setattr("toolchain.groups.issues.resolve_source", lambda config: StubSource())
    result = CliRunner().invoke(cli, ["issues", "get", "tail/999"])
    assert result.exit_code == 1


def test_issues_get_with_key_uses_v1_path(monkeypatch):
    class StubSource:
        def fetch(self, path, **params):
            assert path == "issues/044"
            return {"issue": "044", "entries": []}

    monkeypatch.setattr("toolchain.groups.issues.resolve_source", lambda config: StubSource())
    result = CliRunner().invoke(cli, ["-k", "ctk_live_abc", "issues", "get", "044"])
    assert result.exit_code == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_group_issues.py -v`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Write the implementation**

```python
# src/toolchain/groups/issues.py
from __future__ import annotations

import click

from ..helpers import emit, get_config, handle_errors
from ..models import UserInputError
from ..source import resolve_source


@click.group()
def issues() -> None:
    """The published archive — daily, highlights, and docs-weekly."""


@issues.command("list")
@click.option("--series", default=None, type=click.Choice(["tail", "head", "diff"]))
@click.option("--limit", type=int, default=None)
@click.pass_context
@handle_errors
def issues_list(ctx: click.Context, series, limit) -> None:
    """The issue index. No key: every entry that has run in a public
    issue, grouped by issue — narrower than the full archive (no
    paywalled entries, no assimilated summary block). With a key: the
    real issue index."""
    config = get_config(ctx)
    source = resolve_source(config)
    if config.api_key:
        params = {k: v for k, v in {"series": series, "limit": limit}.items() if v is not None}
        data = source.fetch("issues", **params)
    else:
        entries = source.fetch("entries.json")
        data = entries
        if series:
            data = [row for row in data if row.get("issue_slug", "").startswith(f"{series}/")]
        if limit is not None:
            data = data[:limit]
    emit(data, config)


@issues.command("get")
@click.argument("issue")
@click.pass_context
@handle_errors
def issues_get(ctx: click.Context, issue: str) -> None:
    """One issue's public entries. No key: derived from /entries.json,
    filtered to this issue_slug (e.g. tail/44) — a subset of the real
    issue, not the full archive record. With a key: the full issue."""
    config = get_config(ctx)
    source = resolve_source(config)
    if config.api_key:
        data = source.fetch(f"issues/{issue}")
    else:
        entries = source.fetch("entries.json")
        matches = [row for row in entries if row.get("issue_slug") == issue]
        if not matches:
            raise UserInputError(
                f"No public entries found for issue '{issue}'. Run 'toolchain issues list' "
                "to see available issue slugs."
            )
        data = matches
    emit(data, config)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_group_issues.py -v`
Expected: PASS (6 passed).

- [ ] **Step 5: Register the group**

Modify `src/toolchain/main.py`:
```python
from .groups.issues import issues as issues_group

cli.add_command(issues_group, name="issues")
```

- [ ] **Step 6: Commit**

```bash
git add src/toolchain/groups/issues.py tests/test_group_issues.py src/toolchain/main.py
git commit -m "feat: issues list/get"
```

---

### Task 20: `issues download`

**Files:**
- Modify: `src/toolchain/groups/issues.py`
- Modify: `tests/test_group_issues.py`

**Interfaces:**
- Consumes: same as Task 19.
- Produces: `issues download ISSUE --format json|html` added to the `issues` group. No key + `--format html`: fetches the real rendered page (`{site_base}/newsletter/{issue}` — `issue` is already the `series/number` slug the site itself links to; a bare number is rejected with a message pointing at `issues list`). No key + `--format json`: same derivation as `issues get`. With a key: `/v1/issues/{issue}/download?format=...` directly, whichever format the API returns raw.

- [ ] **Step 1: Add the failing tests**

Append to `tests/test_group_issues.py`:
```python
def test_issues_download_json_no_key_matches_issues_get(monkeypatch):
    entries = load("site_entries.json")

    class StubSource:
        def fetch(self, path, **params):
            return entries

    monkeypatch.setattr("toolchain.groups.issues.resolve_source", lambda config: StubSource())
    result = CliRunner().invoke(cli, ["issues", "download", "tail/44", "--format", "json"])
    assert result.exit_code == 0
    assert json.loads(result.output)[0]["tool"] == "Nmap"


def test_issues_download_html_no_key_fetches_the_rendered_page(monkeypatch):
    class StubSource:
        def fetch(self, path, **params):
            assert path == "newsletter/tail/44"
            return {"__raw_html__": "<html>issue 44</html>"}

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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_group_issues.py -v`
Expected: FAIL — `download` subcommand doesn't exist.

Note: `SiteSource.fetch` (Task 6) always calls `.json()` on the response,
which breaks on an HTML body. This task needs a raw-fetch path for HTML —
add it to `SiteSource` here rather than special-casing `issues download`
around the abstraction:

- [ ] **Step 3: Add `fetch_text` to `SiteSource` first (small, test-first sub-step)**

Add to `tests/test_source_site.py`:
```python
def test_fetch_text_returns_raw_body():
    client = FakeClient(
        responses={
            "https://cybertoolchain.github.io/newsletter/tail/44": FakeResponse(
                200, text="<html>issue 44</html>"
            )
        }
    )
    source = SiteSource("https://cybertoolchain.github.io", client=client)
    assert source.fetch_text("newsletter/tail/44") == "<html>issue 44</html>"
```

Update `tests/fakes.py`'s `FakeResponse` to carry a `text` field:
```python
@dataclass
class FakeResponse:
    status_code: int
    json_data: dict | None = None
    text: str = ""

    def json(self) -> dict:
        return self.json_data or {}
```

Run: `uv run pytest tests/test_source_site.py -v` — expect the new test to
fail (`AttributeError: 'SiteSource' object has no attribute 'fetch_text'`),
then add to `src/toolchain/source/site.py`:
```python
    def fetch_text(self, path: str, **params: Any) -> str:
        url = self._url(path)
        try:
            response = self._client.get(url, params=params or None)
        except httpx.TimeoutException as exc:
            raise NetworkError(f"Timed out fetching {url}") from exc
        except httpx.ConnectError as exc:
            raise NetworkError(f"Could not connect to {url}") from exc
        if response.status_code >= 400:
            raise APIError(f"{response.status_code} fetching {url}")
        return response.text
```
Run again: expect PASS (9 passed). Commit this sub-step on its own:
```bash
git add src/toolchain/source/site.py tests/test_source_site.py tests/fakes.py
git commit -m "feat: SiteSource.fetch_text for raw (non-JSON) responses"
```

- [ ] **Step 4: Write the `issues download` implementation**

Append to `src/toolchain/groups/issues.py`:

```python
@issues.command("download")
@click.argument("issue")
@click.option("--format", "fmt", required=True, type=click.Choice(["json", "html"]))
@click.pass_context
@handle_errors
def issues_download(ctx: click.Context, issue: str, fmt: str) -> None:
    """The same issue as a file — JSON, or the standalone rendered page."""
    config = get_config(ctx)
    source = resolve_source(config)
    if config.api_key:
        data = source.fetch(f"issues/{issue}/download", format=fmt)
        emit(data, config)
        return
    if fmt == "json":
        entries = source.fetch("entries.json")
        matches = [row for row in entries if row.get("issue_slug") == issue]
        if not matches:
            raise UserInputError(
                f"No public entries found for issue '{issue}'. Run 'toolchain issues list' "
                "to see available issue slugs."
            )
        emit(matches, config)
        return
    # fmt == "html"
    if "/" not in issue:
        raise UserInputError(
            f"'{issue}' isn't a full issue slug. Run 'toolchain issues list' to find one "
            "(e.g. tail/44)."
        )
    click.echo(source.fetch_text(f"newsletter/{issue}"))
```

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest tests/test_group_issues.py -v`
Expected: PASS (11 passed).

- [ ] **Step 6: Commit**

```bash
git add src/toolchain/groups/issues.py tests/test_group_issues.py
git commit -m "feat: issues download (json or the rendered html page)"
```

---

### Task 21: `issues read` (Rich reader)

**Files:**
- Create: `src/toolchain/tui/reader.py`
- Modify: `src/toolchain/groups/issues.py`
- Test: `tests/test_tui_reader.py`

**Interfaces:**
- Consumes: the `list[dict]` shape `issues get` already emits (entries with `tool`, `summary`, `feature_bullets`, `usage_examples`, `version`, `url`).
- Produces: `render_issue(entries: list[dict]) -> str` (pure function: builds a Markdown document — one section per tool with its summary, bullets, and any `usage_examples[].command` as a fenced code block — then renders it through `rich.console.Console` capture to get syntax-highlighted ANSI text back as a string, so it's independently testable without a live terminal). `issues read ISSUE` calls the same fetch logic as `issues get`, then prints `render_issue(...)` instead of calling `emit()`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_tui_reader.py
from __future__ import annotations

from toolchain.tui.reader import render_issue

ENTRIES = [
    {
        "tool": "Nmap",
        "category": "reconnaissance",
        "version": "commits-2026-07-11",
        "url": "https://github.com/nmap/nmap/compare/49a85f9c3c11...115af39aacf9",
        "summary": "Nmap gains TLS close_notify tolerance and signal propagation with `-k`.",
        "feature_bullets": ["Adds `-k` signal propagation."],
        "usage_examples": [
            {
                "description": "Bind an interface and source address.",
                "command": "nmap -e eth1 -S 192.168.1.50 <target>",
                "language": "",
                "kind": "shell",
            }
        ],
    }
]


def test_render_issue_includes_tool_name():
    assert "Nmap" in render_issue(ENTRIES)


def test_render_issue_includes_summary():
    assert "TLS close_notify tolerance" in render_issue(ENTRIES)


def test_render_issue_includes_feature_bullets():
    assert "signal propagation" in render_issue(ENTRIES)


def test_render_issue_includes_the_command_example():
    assert "nmap -e eth1 -S 192.168.1.50" in render_issue(ENTRIES)


def test_render_issue_handles_empty_list():
    assert render_issue([]) == "" or "no entries" in render_issue([]).lower()


def test_render_issue_handles_missing_optional_fields():
    minimal = [{"tool": "Falco", "summary": "Falco shipped something."}]
    out = render_issue(minimal)
    assert "Falco" in out
    assert "Falco shipped something." in out
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_tui_reader.py -v`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Write the implementation**

```python
# src/toolchain/tui/reader.py
from __future__ import annotations

from io import StringIO
from typing import Any

from rich.console import Console
from rich.markdown import Markdown


def _to_markdown(entries: list[dict[str, Any]]) -> str:
    if not entries:
        return "_No entries._\n"
    lines: list[str] = []
    for entry in entries:
        lines.append(f"## {entry.get('tool', 'Unknown tool')}")
        if entry.get("version"):
            lines.append(f"*{entry['version']}*")
        lines.append("")
        if entry.get("summary"):
            lines.append(entry["summary"])
            lines.append("")
        for bullet in entry.get("feature_bullets", []):
            lines.append(f"- {bullet}")
        if entry.get("feature_bullets"):
            lines.append("")
        for example in entry.get("usage_examples", []):
            if example.get("description"):
                lines.append(example["description"])
            lines.append("```shell")
            lines.append(example.get("command", ""))
            lines.append("```")
            lines.append("")
        if entry.get("url"):
            lines.append(f"[{entry['url']}]({entry['url']})")
        lines.append("")
    return "\n".join(lines)


def render_issue(entries: list[dict[str, Any]]) -> str:
    """Renders a list of issue entries (the same shape `issues get` emits)
    as syntax-highlighted, formatted text suitable for a terminal or a
    pager. Pure function — no I/O, so it's testable without a real
    terminal."""
    markdown_text = _to_markdown(entries)
    buffer = StringIO()
    console = Console(file=buffer, force_terminal=True, width=100)
    console.print(Markdown(markdown_text))
    return buffer.getvalue()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_tui_reader.py -v`
Expected: PASS (6 passed).

- [ ] **Step 5: Wire `issues read` onto the group**

Append to `src/toolchain/groups/issues.py`:

```python
@issues.command("read")
@click.argument("issue")
@click.pass_context
@handle_errors
def issues_read(ctx: click.Context, issue: str) -> None:
    """Read an issue as a rendered document — Markdown with syntax
    highlighting, not raw JSON. Human-only: does not go through
    -o/--output. Pipe to a pager, e.g. `toolchain issues read tail/44 | less -R`."""
    from ..tui.reader import render_issue

    config = get_config(ctx)
    source = resolve_source(config)
    if config.api_key:
        data = source.fetch(f"issues/{issue}")
        entries = data.get("entries", [])
    else:
        entries_data = source.fetch("entries.json")
        entries = [row for row in entries_data if row.get("issue_slug") == issue]
        if not entries:
            raise UserInputError(
                f"No public entries found for issue '{issue}'. Run 'toolchain issues list' "
                "to see available issue slugs."
            )
    click.echo(render_issue(entries))
```

Add to `tests/test_group_issues.py`:
```python
def test_issues_read_no_key_renders_markdown(monkeypatch):
    entries = load("site_entries.json")

    class StubSource:
        def fetch(self, path, **params):
            return entries

    monkeypatch.setattr("toolchain.groups.issues.resolve_source", lambda config: StubSource())
    result = CliRunner().invoke(cli, ["issues", "read", "tail/44"])
    assert result.exit_code == 0
    assert "Nmap" in result.output
```

- [ ] **Step 6: Run test to verify it passes**

Run: `uv run pytest tests/test_group_issues.py -v`
Expected: PASS (12 passed).

- [ ] **Step 7: Manual check**

```bash
uv run toolchain issues read tail/44 | cat
```
Expected: readable Markdown-rendered output (headers, bullets, a fenced
`nmap -e eth1 ...` code block) rather than raw JSON.

- [ ] **Step 8: Commit**

```bash
git add src/toolchain/tui/reader.py src/toolchain/groups/issues.py tests/test_tui_reader.py tests/test_group_issues.py
git commit -m "feat: issues read — Rich-rendered Markdown issue reader"
```

---

### Task 22: `analytics get`

**Files:**
- Create: `src/toolchain/groups/analytics.py`
- Create: `tests/fixtures/site_analytics_notes_quality.json`
- Create: `tests/fixtures/api_analytics_practitioner.json`
- Create: `tests/fixtures/api_analytics_researcher.json`
- Test: `tests/test_group_analytics.py`

**Interfaces:**
- Consumes: `resolve_source`, `emit`/`get_config`/`handle_errors`.
- Produces: `analytics` group with `get CHART` — no key or a practitioner-tier key both read the masked JSON already published at `{site_base}/analytics/{chart}.json`; a Researcher+ key calls `/v1/analytics/{chart}` for the unmasked response.

- [ ] **Step 1: Write the fixtures**

`tests/fixtures/site_analytics_notes_quality.json` (real, trimmed, from
`generator/site/public/analytics/notes_quality.json` — this file IS the
masked view, already public with no key):
```json
{
  "meta": {
    "chart": "notes_quality",
    "generated_at": "2026-08-17T16:09:34Z",
    "n": {"tools_ranked": 479, "ineligible_tools": 310, "zero_score_tools": 13}
  },
  "data": {
    "tools": [
      {
        "name": "▒▒▒▒▒▒▒",
        "display": "▒▒▒▒▒▒▒",
        "category": "container-security",
        "score": 87.0
      }
    ]
  }
}
```

`tests/fixtures/api_analytics_practitioner.json` (verbatim from `/api`'s
documented example, "masked" tier):
```json
{
  "chart": "notes_quality",
  "withheld": true,
  "data": {
    "tools": [
      {
        "name": "▒▒▒▒▒▒▒",
        "display": "▒▒▒▒▒▒▒",
        "category": "container-security",
        "score": 87.0
      }
    ]
  }
}
```

`tests/fixtures/api_analytics_researcher.json` (verbatim from `/api`'s
documented example, "full detail" tier):
```json
{
  "chart": "notes_quality",
  "withheld": false,
  "data": {
    "tools": [
      {"name": "dockerscan", "display": "dockerscan", "category": "container-security", "score": 87.0}
    ]
  }
}
```

- [ ] **Step 2: Write the failing test**

```python
# tests/test_group_analytics.py
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
```

- [ ] **Step 3: Run test to verify it fails**

Run: `uv run pytest tests/test_group_analytics.py -v`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 4: Write the implementation**

```python
# src/toolchain/groups/analytics.py
from __future__ import annotations

import click

from ..helpers import emit, get_config, handle_errors
from ..source import resolve_source


@click.group()
def analytics() -> None:
    """The charts behind /analytics, as data."""


@analytics.command("get")
@click.argument("chart")
@click.pass_context
@handle_errors
def analytics_get(ctx: click.Context, chart: str) -> None:
    """One chart. No key or a Practitioner key: the masked view already
    published on the site. Researcher+: full detail, names included."""
    config = get_config(ctx)
    source = resolve_source(config)
    if config.api_key:
        data = source.fetch(f"analytics/{chart}")
    else:
        data = source.fetch(f"analytics/{chart}.json")
    emit(data, config)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest tests/test_group_analytics.py -v`
Expected: PASS (3 passed).

- [ ] **Step 6: Register the group**

Modify `src/toolchain/main.py`:
```python
from .groups.analytics import analytics as analytics_group

cli.add_command(analytics_group, name="analytics")
```

- [ ] **Step 7: Commit**

```bash
git add src/toolchain/groups/analytics.py tests/fixtures/*.json tests/test_group_analytics.py src/toolchain/main.py
git commit -m "feat: analytics get (masked free view, full detail with a Researcher+ key)"
```

---

### Task 23: `search`

**Files:**
- Create: `src/toolchain/groups/search.py`
- Create: `tests/fixtures/site_search_index.json`
- Test: `tests/test_group_search.py`

**Interfaces:**
- Consumes: `resolve_source`, `emit`/`get_config`/`handle_errors`.
- Produces: a bare `search` command (not a group — matches `/api`'s single `search` endpoint, no sub-nouns) with `QUERY` argument and `--type tool|release`. No key: substring-matches `q` against `label`+`keywords` in `/search-index.json`. A key: `/v1/search`.

- [ ] **Step 1: Write the fixture**

`tests/fixtures/site_search_index.json` (shaped per `buildSearchIndex()`,
`generator/site/src/lib/searchIndex.ts`):
```json
[
  {"type": "tool", "label": "Nmap", "sub": "reconnaissance", "href": "/tools/nmap", "keywords": "nmap network scanning port scanner reconnaissance"},
  {"type": "tool", "label": "Falco", "sub": "runtime-security", "href": "/tools/falco", "keywords": "falco ebpf runtime detection kubernetes"},
  {"type": "issue", "label": "Issue 44", "sub": "issue", "href": "/newsletter/44", "keywords": "issue 44 nmap falco"}
]
```

- [ ] **Step 2: Write the failing test**

```python
# tests/test_group_search.py
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
```

- [ ] **Step 3: Run test to verify it fails**

Run: `uv run pytest tests/test_group_search.py -v`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 4: Write the implementation**

```python
# src/toolchain/groups/search.py
from __future__ import annotations

import click

from ..helpers import emit, get_config, handle_errors
from ..source import resolve_source


@click.command("search")
@click.argument("query")
@click.option("--type", "type_", default=None, type=click.Choice(["tool", "release"]))
@click.option("--limit", type=int, default=20)
@click.pass_context
@handle_errors
def search(ctx: click.Context, query: str, type_, limit: int) -> None:
    """Full-text over tool names, vendors, and release summaries."""
    config = get_config(ctx)
    source = resolve_source(config)
    if config.api_key:
        params = {"q": query, "limit": limit}
        if type_:
            params["type"] = type_
        data = source.fetch("search", **params)
    else:
        index = source.fetch("search-index.json")
        needle = query.lower()
        data = [row for row in index if needle in row.get("keywords", "").lower()]
        if type_:
            wanted = "tool" if type_ == "tool" else "issue"
            data = [row for row in data if row.get("type") == wanted]
        data = data[:limit]
    emit(data, config)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest tests/test_group_search.py -v`
Expected: PASS (4 passed).

- [ ] **Step 6: Register the command**

Modify `src/toolchain/main.py`:
```python
from .groups.search import search as search_command

cli.add_command(search_command, name="search")
```

- [ ] **Step 7: Commit**

```bash
git add src/toolchain/groups/search.py tests/fixtures/site_search_index.json tests/test_group_search.py src/toolchain/main.py
git commit -m "feat: search"
```

---

### Task 24: README, CLAUDE.md, and final integration smoke test

**Files:**
- Create: `README.md`
- Create: `CLAUDE.md`
- Create: `tests/test_integration_smoke.py`

**Interfaces:**
- No new production code — this task documents the finished tool and adds one end-to-end sanity test exercising the real `cli` object across every registered group without any per-command monkeypatching (each command's own `resolve_source` is still stubbed, since tests never touch the network — see Global Constraints).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_integration_smoke.py
from __future__ import annotations

from click.testing import CliRunner

from toolchain.main import cli


def test_help_lists_every_command_group():
    result = CliRunner().invoke(cli, ["--help"])
    assert result.exit_code == 0
    for name in ["tools", "releases", "categories", "issues", "analytics", "search", "tldr"]:
        assert name in result.output


def test_every_group_help_exits_zero():
    runner = CliRunner()
    for group in ["tools", "releases", "categories", "issues", "analytics"]:
        result = runner.invoke(cli, [group, "--help"])
        assert result.exit_code == 0, f"{group} --help failed: {result.output}"


def test_key_only_commands_all_state_the_requirement_in_help():
    runner = CliRunner()
    for args in (["tools", "sbom", "--help"],):
        result = runner.invoke(cli, args)
        assert "requires an API key" in result.output


def test_global_flag_after_subcommand_is_still_rejected_end_to_end():
    result = CliRunner().invoke(cli, ["tools", "list", "-k", "ctk_x"])
    assert result.exit_code != 0
    assert "global option" in result.output
```

- [ ] **Step 2: Run test to verify it fails or passes**

Run: `uv run pytest tests/test_integration_smoke.py -v`
Expected: this test should already PASS if Tasks 1–23 are all in place — it
adds no new behavior, only cross-cutting verification. If anything fails,
that's a real gap in an earlier task; fix the earlier task, don't special-case
this test.

- [ ] **Step 3: Write `README.md`**

```markdown
# toolchain

Command-line client for The Cyber Toolchain (and, once it has a data API,
aitoolchain).

## Install

    uv venv
    uv pip install -e ".[dev]"

## Usage

No API key: reads the free data already published on the site.

    toolchain tools list
    toolchain tools get nmap
    toolchain releases latest --limit 10
    toolchain issues read tail/44
    toolchain search "runtime security"

With an API key (`-k`/`--api-key`, or `TOOLCHAIN_API_KEY`): live filtering,
pagination, full analytics detail, SBOM, and per-endpoint API detail. Get a
key from your account page on the site. Commands that have no free
equivalent (`tools sbom`) say so in their own `--help`.

    export TOOLCHAIN_API_KEY=ctk_your_key_here
    toolchain analytics get notes_quality   # full detail instead of masked
    toolchain tools sbom nmap

## Targeting a different product

    toolchain --site aitoolchain tools list

`aitoolchain` has no data API yet — only free site commands work against it
until one ships.

## Global options

`-k/--api-key`, `--site`, `-o/--output` (json/table/csv/tsv), `-v/--verbose`,
`--debug`, `-c/--cache`, `-l/--limit`, `-s/--short`, `-t/--timeout`,
`--search-fields`. Must appear **before** the subcommand.

## Development

    uv run pytest

TDD throughout: every command's tests stub `resolve_source` with a fake
`Source`, so the suite never touches the network.
```

- [ ] **Step 4: Write `CLAUDE.md`**

```markdown
# CLAUDE.md — toolchain CLI

Command-line client for The Cyber Toolchain / aitoolchain. Design:
`docs/superpowers/specs/2026-08-18-toolchain-cli-design.md`. Implementation
plan: `docs/superpowers/plans/2026-08-18-toolchain-cli.md`.

## Two backends, picked once, centrally

`resolve_source(config)` (`src/toolchain/source/__init__.py`) is the only
place that decides `SiteSource` (no key, free static JSON on the product's
GitHub Pages site) vs. `ApiSource` (a key, live `/v1/*`). Every command
calls it and nothing else. A command with no free equivalent (`tools sbom`)
checks `config.api_key` itself and raises `UserInputError` naming where to
get one — do the same for any new key-only command; never let it fall
through to a raw 401 from `ApiSource`.

## Known deviation from the original design spec

The design spec listed `tools stack` as key-only. Implementation found
`generator/site/public/toolCode.json` already publishes exactly that data
(language mix, dependencies, AI-attribution) for free, so `tools stack`
reads it with no key and only calls `/v1/tools/{slug}/stack` with one. If
this surprises you, it's a real, deliberate correction — not a bug.

## `--debug` and the httpx/httpcore logging landmine

`ApiSource.curl()` is structurally leak-proof — it never references the raw
key attribute, only `$TOOLCHAIN_API_KEY`. But `redact()` (`src/toolchain/log.py`)
has no call site anywhere in this codebase yet, found during Task 7's review.
If a future `--debug` enhancement enables raw `httpx`/`httpcore` DEBUG-level
logging (e.g. `logging.getLogger("httpx").setLevel(logging.DEBUG)` or a bare
`logging.basicConfig(level=logging.DEBUG)` that httpx's loggers pick up),
those libraries log request headers independently of `ApiSource` — including
the real `x-api-key` value — straight to stderr, outside this class's
control entirely. `configure_logging()` (Task 5) only configures a logger
named `"toolchain"` with `propagate=False`, so it does NOT currently touch
httpx's own loggers — that's why this is a landmine and not a live bug.
**Before wiring any future feature that touches httpx/httpcore's own
logging, either keep it off entirely or run every line through `redact()`
first.**

## Adding a new product (a third `--site`)

Add one `Site(site_base=..., api_base=...)` entry to `SITES` in
`src/toolchain/config.py`. `api_base=None` until that product ships a data
API — every keyed command already handles that centrally.

## Testing

Every `Source` implementation accepts an injectable `client` (see
`tests/fakes.py`'s `FakeClient`/`FakeResponse`) — no HTTP mocking library,
no real network calls, ever, in the test suite. Command-group tests
monkeypatch `resolve_source` at the group module's import path (e.g.
`toolchain.groups.tools.resolve_source`), not the shared `toolchain.source`
module, since each group imports it by name.
```

- [ ] **Step 5: Run the full suite one last time**

```bash
uv run pytest -v
```
Expected: every test across all 24 tasks passes.

- [ ] **Step 6: Commit**

```bash
git add README.md CLAUDE.md tests/test_integration_smoke.py
git commit -m "docs: README, CLAUDE.md, and an end-to-end smoke test"
```

---

## Self-Review Notes

**Spec coverage:** Two-backend architecture (Tasks 6–8), every command group
from the design's grammar table (Tasks 13–23, including the renames
`examples`/`stack` and the new `releases latest`), config/site
registry/env vars (Task 3), output/DX rules (Tasks 9–11), TUI for both
`tools browse` and `issues read` (Tasks 16, 21), repo layout and packaging
(Task 1, `README.md`/`CLAUDE.md` in Task 24). One deviation from the spec
(`tools stack` free-with-no-key rather than key-only) is implemented as the
more accurate behavior and flagged inline in Task 15 and in `CLAUDE.md`
(Task 24) rather than silently diverging.

**Not implemented, matching the spec's explicit exclusions:** `doc-diffs`
and `corpus-export` (the design's "Coming later" endpoints — not live on
`/api` itself yet), publishing to PyPI/Homebrew, and any aitoolchain-specific
command (its `Site` entry exists so the plumbing is ready, but there is
nothing live to call).

**Placeholder scan:** no task contains "TBD"/"add error handling"/"similar to
Task N" — every step shows the actual code or fixture content.

**Type consistency:** `Source.fetch(path: str, **params) -> dict` is the one
signature every `SiteSource`/`ApiSource`/`StubSource`-in-tests implements,
unchanged from Task 6 through Task 23. `Config` (Task 3) fields are read the
same way (`config.api_key`, `config.site`, `config.output`, etc.) in every
later task with no renames.

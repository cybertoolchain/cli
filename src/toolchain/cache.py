from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


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

    def __init__(self, inner: Any, cache: Cache, *, namespace: str = "") -> None:
        self._inner = inner
        self._cache = cache
        self._namespace = namespace

    def _key(self, path: str, params: dict) -> str:
        return f"{self._namespace}:{path}:{sorted(params.items())}"

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

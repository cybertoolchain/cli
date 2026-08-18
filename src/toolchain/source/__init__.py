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

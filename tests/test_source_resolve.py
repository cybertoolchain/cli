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

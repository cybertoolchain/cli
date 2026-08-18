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


def test_cache_flag_namespaces_by_site_and_api_key(tmp_path, monkeypatch):
    monkeypatch.setattr("toolchain.source.CACHE_DIR", tmp_path)

    no_key_config = resolve_config(cache=True)
    keyed_config = resolve_config(cache=True, api_key="ctk_live_abc")

    no_key_source = resolve_source(no_key_config)
    keyed_source = resolve_source(keyed_config)

    assert no_key_source._namespace != keyed_source._namespace
    # The raw key never appears in the namespace, only a digest of it.
    assert "ctk_live_abc" not in keyed_source._namespace


def test_no_cache_flag_returns_the_source_directly():
    config = resolve_config(cache=False)
    source = resolve_source(config)
    assert isinstance(source, SiteSource)

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

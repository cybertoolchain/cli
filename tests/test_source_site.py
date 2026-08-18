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

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


def test_default_client_follows_redirects():
    source = ApiSource(BASE, "ctk_live_abc")
    assert source._client.follow_redirects is True


def test_fetch_with_non_json_2xx_body_raises_api_error():
    client = FakeClient(
        responses={f"{BASE}/v1/tools": FakeResponse(200, text="<html>oops</html>", invalid_json=True)}
    )
    source = ApiSource(BASE, "ctk_live_abc", client=client)
    with pytest.raises(APIError, match="did not return valid JSON"):
        source.fetch("tools")


def test_curl_never_prints_the_real_key():
    source = ApiSource(BASE, "ctk_live_secret_value", client=FakeClient())
    dump = source.curl("tools/count")
    assert "ctk_live_secret_value" not in dump
    assert "$TOOLCHAIN_API_KEY" in dump
    assert f"{BASE}/v1/tools/count" in dump

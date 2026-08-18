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

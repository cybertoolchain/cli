from __future__ import annotations

import json
from typing import Any
from urllib.parse import urlencode

import httpx

from ..models import APIError, NetworkError
from ..versioning import default_headers


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
        self._client = (
            client
            if client is not None
            else httpx.Client(timeout=timeout, follow_redirects=True, headers=default_headers())
        )

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
        try:
            return response.json()
        except json.JSONDecodeError as exc:
            raise APIError(f"{url} did not return valid JSON") from exc

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

    def curl(self, path: str, **params: Any) -> str:
        url = self._url(path)
        if params:
            url = f"{url}?{urlencode(params)}"
        return f"curl {url}"

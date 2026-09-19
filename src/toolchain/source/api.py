from __future__ import annotations

import json
from typing import Any
from urllib.parse import urlencode

import httpx

from ..models import APIError, NetworkError, UserInputError
from ..versioning import default_headers


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
        self._client = (
            client
            if client is not None
            else httpx.Client(timeout=timeout, follow_redirects=True, headers=default_headers())
        )

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
        if response.status_code == 403:
            raise self._forbidden(response, url)
        if response.status_code == 429:
            raise APIError("Rate limit exceeded for this key. Try again later.")
        if response.status_code >= 400:
            raise APIError(f"{response.status_code} fetching {url}")
        try:
            return response.json()
        except json.JSONDecodeError as exc:
            raise APIError(f"{url} did not return valid JSON") from exc

    @staticmethod
    def _forbidden(response: Any, url: str) -> Exception:
        # The key is valid but its owner's plan no longer includes the API
        # (a lapse or a downgrade). Only that code is blamed on the plan: a
        # 403 from the CDN or a WAF is not something a renewal fixes.
        try:
            body = response.json()
        except ValueError:
            body = {}
        if isinstance(body, dict) and body.get("error") == "requires-researcher":
            message = body.get("message") or (
                "API access needs a Researcher or Business subscription."
            )
            return UserInputError(
                f"{message} Renew or upgrade on your account page, "
                "then run the command again."
            )
        return APIError(f"Access to {url} was refused (HTTP 403).")

    def curl(self, path: str, **params: Any) -> str:
        url = self._url(path)
        if params:
            url = f"{url}?{urlencode(params)}"
        return f'curl -H "x-api-key: $TOOLCHAIN_API_KEY" \\\n  {url}'

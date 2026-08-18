# src/toolchain/config.py
from __future__ import annotations

import os
from dataclasses import dataclass

from .models import UserInputError

VALID_OUTPUTS: tuple[str, ...] = ("json", "table", "csv", "tsv")
VALID_MODES: tuple[str, ...] = ("dark", "light", "sepia", "contrast")


@dataclass(frozen=True)
class Site:
    """Where one product's data lives. `api_base` is None until that
    product has a live `/v1` data API — a keyed command against such a
    site fails with a clear message rather than a raw connection error."""

    site_base: str
    api_base: str | None


SITES: dict[str, Site] = {
    "cybertoolchain": Site(
        site_base="https://cybertoolchain.github.io",
        # CloudFront in front of ctk-data-api. Swap for api.cybertoolchain.com
        # here, once, when that DNS/cert work lands — every command reads
        # this one constant.
        api_base="https://d3hvv6ete0783d.cloudfront.net",
    ),
    "aitoolchain": Site(
        site_base="https://aitoolchain.io",
        api_base=None,
    ),
}


@dataclass(frozen=True)
class Config:
    api_key: str | None
    site_key: str
    site: Site
    output: str
    verbose: bool
    debug: bool
    cache: bool
    limit: int | None
    short: bool
    timeout: float
    search_fields: str | None
    mode: str


def resolve_config(
    *,
    api_key: str | None = None,
    site: str | None = None,
    output: str | None = None,
    verbose: bool = False,
    debug: bool = False,
    cache: bool = False,
    limit: int | None = None,
    short: bool = False,
    timeout: float | None = None,
    search_fields: str | None = None,
    mode: str | None = None,
) -> Config:
    """flag -> env (TOOLCHAIN_ prefix) -> default, validated once, here."""
    resolved_key = api_key or os.environ.get("TOOLCHAIN_API_KEY") or None

    resolved_site_key = site or os.environ.get("TOOLCHAIN_SITE") or "cybertoolchain"
    if resolved_site_key not in SITES:
        supported = ", ".join(SITES)
        raise UserInputError(
            f"Unknown --site '{resolved_site_key}'. Supported values are: {supported}"
        )

    resolved_output = output or os.environ.get("TOOLCHAIN_OUTPUT") or "json"
    if resolved_output not in VALID_OUTPUTS:
        supported = ", ".join(VALID_OUTPUTS)
        raise UserInputError(
            f"Unsupported --output '{resolved_output}'. Supported values are: {supported}"
        )

    if timeout is not None:
        resolved_timeout = timeout
    else:
        raw_timeout = os.environ.get("TOOLCHAIN_TIMEOUT", "30")
        try:
            resolved_timeout = float(raw_timeout)
        except ValueError as exc:
            raise UserInputError(
                f"TOOLCHAIN_TIMEOUT must be a number, got '{raw_timeout}'"
            ) from exc

    if resolved_timeout <= 0:
        raise UserInputError(f"--timeout must be greater than 0, got {resolved_timeout}")

    resolved_mode = mode or os.environ.get("TOOLCHAIN_MODE") or "dark"
    if resolved_mode not in VALID_MODES:
        supported = ", ".join(VALID_MODES)
        raise UserInputError(
            f"Unknown --mode '{resolved_mode}'. Supported values are: {supported}"
        )

    return Config(
        api_key=resolved_key,
        site_key=resolved_site_key,
        site=SITES[resolved_site_key],
        output=resolved_output,
        verbose=verbose,
        debug=debug,
        cache=cache,
        limit=limit,
        short=short,
        timeout=resolved_timeout,
        search_fields=search_fields,
        mode=resolved_mode,
    )

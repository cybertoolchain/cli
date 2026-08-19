# src/toolchain/versioning.py
from __future__ import annotations

from importlib import metadata

import httpx

_DIST_NAME = "toolchain-cli"
_LATEST_RELEASE_URL = "https://api.github.com/repos/cybertoolchain/cli/releases/latest"


def current_version() -> str:
    """The installed package version — pyproject.toml's [project] version
    is the one source of truth, read back via package metadata so this can
    never drift from what was actually installed."""
    try:
        return metadata.version(_DIST_NAME)
    except metadata.PackageNotFoundError:
        return "0.0.0+unknown"


def _version_tuple(value: str) -> tuple[int, ...]:
    parts = []
    for chunk in value.lstrip("v").split(".")[:3]:
        digits = "".join(c for c in chunk if c.isdigit())
        parts.append(int(digits) if digits else 0)
    while len(parts) < 3:
        parts.append(0)
    return tuple(parts)


def latest_version(*, timeout: float = 5.0) -> str | None:
    """The newest published GitHub release tag, or None if the check can't
    be made (offline, no releases yet, rate-limited, ...). This is a
    convenience lookup — nothing that calls it should ever fail because of
    it, which is why every failure mode collapses to None rather than
    raising."""
    try:
        response = httpx.get(_LATEST_RELEASE_URL, timeout=timeout, follow_redirects=True)
        response.raise_for_status()
        tag = response.json().get("tag_name", "")
    except Exception:
        return None
    return tag.lstrip("v") or None


def update_available(*, timeout: float = 5.0) -> str | None:
    """The latest version string if it's newer than what's installed, else
    None — covers both 'already current' and 'couldn't check'."""
    latest = latest_version(timeout=timeout)
    if latest is None:
        return None
    if _version_tuple(latest) > _version_tuple(current_version()):
        return latest
    return None
